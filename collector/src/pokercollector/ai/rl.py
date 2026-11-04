"""Wie der Bot lernt: erst Nachahmung (Behavior Cloning), dann Selbstspiel mit PPO.

1. Nachahmung: Ein Lehrer-Bot (z. B. rock) spielt Sit&Gos; jede seiner Entscheidungen wird
   als (Merkmale, erlaubte Aktionen, gewaehlte Aktion) gespeichert. Das Netz lernt, ihn
   nachzuspielen, und sein Wertkopf lernt, was solche Haende im Schnitt einbringen.
   Ergebnis: Checkpoint 0 - ein vernuenftiger Startpunkt statt Zufall.

2. PPO (Proximal Policy Optimization): Je Iteration spielt der aktuelle Bot viele Sit&Gos
   (parallel in Prozessen) gegen Tische aus der Liga und gegen eingefrorene fruehere
   Versionen von sich. Belohnung je Hand = Chip-Aenderung / Startstack * reward_scale,
   vergeben bei seiner letzten Entscheidung in der Hand (eine Hand = eine Episode).
   Danach wird das Netz in kleinen, begrenzten Schritten (clip) in Richtung der Aktionen
   verschoben, die besser liefen als vom Wertkopf erwartet (Vorteil, GAE).

Optimiert wird Chip-Gewinn; mit RLConfig.icm > 0 anteilig die Aenderung des ICM-Eigenkapitals
   (icm.py, Preise aus der Auszahlungsstruktur des Turniers): Belohnung = (1-icm)*Chips + icm*dICM.
Ob der Bot wirklich besser ist, entscheidet wie immer die Aufnahmepruefung (optimize.gate).

Ablage je Lauf: data\\rl\\<lauf>\\ mit config.json, bc.json, log.jsonl, eval.jsonl,
ckpt_000000.pt (nach Nachahmung), ckpt_<Iteration>.pt (Schnappschuesse), state.pt (Fortsetzen).
"""

from __future__ import annotations

import json
import math
import random
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .agents import make_agent
from .features import (EFF_STACK_INDEX, FEATURE_SIZES, PLAYERS_INDEX, N_ACTIONS, N_FEATURES, action_mask, features, from_action,
                       to_action, version_for_width)
from .nn_agent import (build_net, checkpoint_path, forward_np, load_checkpoint, net_from_checkpoint, numpy_weights,
                       rl_root, save_checkpoint)
from .observation import clamp_action
from .optimize import DEFAULT_CONFIG, DEFAULT_POOL, LeaguePool, matchup_payouts
from .tournament import TournamentConfig, play_tournament, random_config, random_players

RL_VERSION = "ppo-1"


@dataclass
class RLConfig:
    hidden: int = 128
    tournaments: int = 96          # Sit&Gos je Iteration
    lr: float = 3e-4
    epochs: int = 4
    minibatch: int = 2048
    clip: float = 0.2
    vf_coef: float = 0.5
    ent_coef: float = 0.01
    lam: float = 0.95
    max_grad_norm: float = 0.5
    reward_scale: float = 10.0
    self_play: float = 0.3         # Anteil Tische mit einer frueheren Version als Gegner
    snapshot_every: int = 10
    eval_every: int = 10
    eval_schemes: int = 12
    seed: int = 1
    # Leine (piKL): Strafe fuer Abweichung von einer Ankerstrategie, z. B. dem Pluribus-Nachahmer.
    # 0 = aus. anchor = '<lauf>:<ckpt>', leer = eigener Checkpoint 0.
    anchor_coef: float = 0.0
    anchor: str = ""
    anchor_min_bb: float = 25.0    # Leine nur ab diesem effektiven Stack (Kurzstack lernt der Bot frei)
    anchor_min_players: int = 0    # Leine nur bei mindestens so vielen Spielern (Pluribus kennt nur 6er)
    table_weights: str = ""        # mit random_formats: Gewichte der Tischgroessen, z. B. "2:4,3:3,6:2"
    self_play_seats: float = 0.0   # je Gegnerplatz: Wahrscheinlichkeit fuer eine fruehere eigene Version
    bench_every: int = 50          # alle N Iterationen auf den Pruefstand (feste Testsets), 0 = nie
    bench_sets: str = "fest48,mix96,pluribus"   # Testsets ("praezise" = grosse Sets, ca. 4 min)
    bench_ref: str = ""            # Vergleichsbot auf dem Pruefstand (Name): gepaarte Differenz, bester -> best.json
    random_share: float = 0.0      # Anteil Tischplaetze mit Zufalls-Stilbots (unendlich viele Spielweisen)
    human_share: float = 0.0       # Anteil Tischplaetze mit Mensch-Bots (echte Spielertypen aus HandHQ)
    random_formats: bool = False   # je Turnier zufaellig: 2-10 Spieler, 20-200 BB, Blind-Tempo, Auszahlung
    exploit_every: int = 0         # alle N Iterationen: Ausbeuter gegen den aktuellen Stand trainieren und
    exploit_iters: int = 30        #   als Gegner in den Pool aufnehmen (0 = aus)
    exploit_tournaments: int = 256
    icm: float = 0.0               # Anteil ICM-Belohnung (0 = Chip-EV, 1 = reine Aenderung des Turnier-Eigenkapitals)


# ---- Sammeln von Entscheidungen ---------------------------------------------------------

class _Collector:
    """Gemeinsame Buchfuehrung: Entscheidungen je Hand, Belohnung bei Handende."""

    def __init__(self, scale: float, start_stack: int, icm: float = 0.0):
        self.scale = scale
        self.start_stack = start_stack
        self.icm = icm
        self.prizes: list[float] = []      # Preise in Buy-ins je Platz (aus obs.tournament)
        self.steps: list[list] = []        # [x, mask, action, logp, value, reward, done]
        self.cur_hand = None
        self.hand_start = 0
        self.hands = 0
        self.net_bb = 0.0

    def _begin(self, obs):
        if obs.hand_id != self.cur_hand:
            self.cur_hand = obs.hand_id
            self.hand_start = len(self.steps)
            t = obs.tournament
            if self.icm > 0 and t and t.get("payouts"):
                from .icm import prizes_from
                self.prizes = prizes_from(t["payouts"], t.get("start_players") or obs.num_seats)

    def _reward(self, rec, seat) -> float:
        res = rec.results[seat]
        chips = res.net / self.start_stack
        if self.icm <= 0 or not self.prizes:
            return chips * self.scale
        from .icm import icm_equity
        before = [r.start_stack for r in rec.results]
        after = [r.end_stack for r in rec.results]
        eq0 = icm_equity(before, self.prizes, seat)
        if after[seat] > 0:
            eq1 = icm_equity(after, self.prizes, seat)
        else:
            # ausgeschieden: Auszahlung fuer diesen Platz; bei mehreren Ausgeschiedenen derselben Hand ist der
            # groessere Startstack besser platziert (wie tournament._assign_places)
            busted_above = sum(1 for s in range(len(after)) if s != seat and before[s] > 0 and after[s] == 0
                               and before[s] > before[seat])
            place = sum(1 for s in after if s > 0) + 1 + busted_above
            eq1 = self.prizes[place - 1] if place - 1 < len(self.prizes) else 0.0
        return ((1 - self.icm) * chips + self.icm * (eq1 - eq0)) * self.scale

    def hand_over(self, rec, seat):
        res = rec.results[seat]
        self.hands += 1
        self.net_bb += res.net / rec.blinds[1]
        if rec.hand_id == self.cur_hand and len(self.steps) > self.hand_start:
            r = self._reward(rec, seat)
            for st in self.steps[self.hand_start:]:
                st[5] = r if st is self.steps[-1] else 0.0
            self.steps[-1][6] = True


class _Learner(_Collector):
    def __init__(self, w: dict, rng: random.Random, scale: float, start_stack: int, name: str = "learner",
                 icm: float = 0.0):
        super().__init__(scale, start_stack, icm)
        self.w, self.rng, self.name = w, rng, name
        self.tracker = None
        if w["features"] == "feat-3":
            from .opponents import OpponentTracker
            self.tracker = OpponentTracker()

    def hand_over(self, rec, seat):
        super().hand_over(rec, seat)
        if self.tracker is not None:
            self.tracker.update(rec, seat)

    def act(self, obs):
        self._begin(obs)
        na = self.w.get("n_actions", N_ACTIONS)
        mask = action_mask(obs, na)
        opp = self.tracker.features(obs) if self.tracker is not None else None
        x = features(obs, version=self.w["features"], opp=opp)
        p, v = forward_np(self.w, x, mask)
        idx = self.rng.choices(range(na), weights=p)[0]
        self.steps.append([x, mask, idx, math.log(max(p[idx], 1e-12)), v, 0.0, False])
        return to_action(obs, idx)


class _Teacher(_Collector):
    def __init__(self, agent, scale: float, start_stack: int):
        super().__init__(scale, start_stack)
        self.agent = agent
        self.name = agent.name

    def act(self, obs):
        self._begin(obs)
        a = clamp_action(obs, self.agent.act(obs))
        self.steps.append([features(obs), action_mask(obs), from_action(obs, a), 0.0, 0.0, 0.0, False])
        return a

    def hand_over(self, rec, seat):
        super().hand_over(rec, seat)
        # Nachahmung: Wertziel = Ergebnis der Hand fuer ALLE Entscheidungen darin
        if self.steps and self.steps[-1][6]:
            r = self.steps[-1][5]
            for st in self.steps[self.hand_start:]:
                st[5] = r


def _pack(steps: list[list], n_features: int = N_FEATURES, n_actions: int = N_ACTIONS) -> dict:
    if steps:
        steps[-1][6] = True
    n = len(steps)
    return {"x": np.stack([s[0] for s in steps]) if n else np.zeros((0, n_features), np.float32),
            "mask": np.stack([s[1] for s in steps]) if n else np.zeros((0, n_actions), bool),
            "a": np.array([s[2] for s in steps], np.int64), "logp": np.array([s[3] for s in steps], np.float32),
            "v": np.array([s[4] for s in steps], np.float32), "r": np.array([s[5] for s in steps], np.float32),
            "done": np.array([s[6] for s in steps], bool)}


def _concat(parts: list[dict]) -> dict:
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def _rollout_job(args) -> tuple[dict, dict]:
    w, tables, seeds, config, scale, rng_seed, *rest = args
    icm = rest[0] if rest else 0.0
    rng = random.Random(rng_seed)
    packs, hands, net_bb, survived, decisions = [], 0, 0.0, 0, 0
    configs = config if isinstance(config, list) else [config] * len(seeds)   # je Turnier eigenes Format
    for opp_specs, sd, config in zip(tables, seeds, configs):
        learner = _Learner(w, rng, scale, config.start_stack, icm=icm)
        opps = [make_agent(f"{s}:opp{i}", 99) for i, s in enumerate(opp_specs)]
        seat = rng.randrange(len(opps) + 1)
        agents = opps[:seat] + [learner] + opps[seat:]
        play_tournament(agents, config, seed=sd, stop=lambda st, seat=seat: st[seat] == 0)
        packs.append(_pack(learner.steps, FEATURE_SIZES[w["features"]], w.get("n_actions", N_ACTIONS)))
        hands += learner.hands
        net_bb += learner.net_bb
        decisions += len(learner.steps)
    stats = {"hands": hands, "net_bb": net_bb, "decisions": decisions, "tournaments": len(seeds)}
    return _concat(packs), stats


def _bc_job(args) -> dict:
    teacher, pool, seeds, config, scale, rng_seed = args
    rng = random.Random(rng_seed)
    packs = []
    for sd in seeds:
        teachers = [_Teacher(make_agent(f"{teacher}:t{i}", sd + i), scale, config.start_stack) for i in range(3)]
        opps = [make_agent(f"{s}:o{i}", 99) for i, s in enumerate(rng.sample(pool, 3))]
        agents = teachers + opps
        rng.shuffle(agents)
        play_tournament(agents, config, seed=sd)
        packs += [_pack(t.steps) for t in teachers if t.steps]
    return _concat(packs)


# ---- Nachahmung --------------------------------------------------------------------------

def behavior_clone(run_dir: Path, teacher: str = "rock", tournaments: int = 600, epochs: int = 10,
                   hidden: int = 128, config: TournamentConfig = DEFAULT_CONFIG, seed: int = 1,
                   workers: int | None = None, progress=None, label_smoothing: float = 0.05) -> dict:
    t0 = time.perf_counter()
    pool = [p for p in DEFAULT_POOL + ["equity"] if p != teacher] or DEFAULT_POOL
    seeds = [seed * 1_000_033 + i for i in range(tournaments)]
    chunks = [seeds[i::24] for i in range(24) if seeds[i::24]]
    with ProcessPoolExecutor(workers) as ex:
        parts = list(ex.map(_bc_job, [(teacher, pool, c, config, RLConfig.reward_scale, seed + i)
                                      for i, c in enumerate(chunks)]))
    data = _concat(parts)
    if progress:
        progress(f"{len(data['a'])} Entscheidungen von '{teacher}' gesammelt ({time.perf_counter() - t0:.0f}s)")
    return fit_bc(run_dir, data, {"teacher": teacher, "tournaments": tournaments}, epochs=epochs, hidden=hidden,
                  seed=seed, progress=progress, label_smoothing=label_smoothing, t0=t0)


def fit_bc(run_dir: Path, data: dict, source: dict, epochs: int = 10, hidden: int = 128, seed: int = 1,
           progress=None, label_smoothing: float = 0.05, t0: float | None = None) -> dict:
    """Netz auf gesammelte Entscheidungen trainieren (x, mask, a, r) -> ckpt_000000.pt."""
    import torch
    torch.manual_seed(seed)
    run_dir.mkdir(parents=True, exist_ok=True)
    t0 = t0 or time.perf_counter()
    n = len(data["a"])
    version = version_for_width(data["x"].shape[1])
    perm = np.random.default_rng(seed).permutation(n)
    hold = perm[: n // 10]
    train = perm[n // 10:]
    X = torch.from_numpy(data["x"])
    M = torch.from_numpy(data["mask"])
    A = torch.from_numpy(data["a"])
    R = torch.from_numpy(data["r"])
    net = build_net(hidden, version)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    for ep in range(epochs):
        net.train()
        order = torch.from_numpy(train[np.random.default_rng([seed, ep]).permutation(len(train))])
        for i in range(0, len(order), 512):
            idx = order[i:i + 512]
            logits, v = net(X[idx], M[idx])
            logp = torch.log_softmax(logits, -1)
            m = M[idx].float()
            target = torch.nn.functional.one_hot(A[idx], N_ACTIONS).float() * (1 - label_smoothing) \
                + label_smoothing * m / m.sum(-1, keepdim=True)
            loss = -(target * torch.where(M[idx], logp, torch.zeros_like(logp))).sum(-1).mean() \
                + 0.5 * ((v - R[idx]) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
        acc = _accuracy(net, X, M, A, hold)
        if progress:
            progress(f"  Epoche {ep + 1}/{epochs}: Trefferquote auf zurueckgehaltenen Daten {acc:.1%}")
    hold_t = torch.from_numpy(hold)
    with torch.no_grad():
        logits, _ = net(X[hold_t], M[hold_t])
        pred = logits.argmax(-1).numpy()
    truth = data["a"][hold]
    per_action = {name: {"n": int((truth == k).sum()),
                         "hit": round(float((pred[truth == k] == k).mean()), 3) if (truth == k).any() else None}
                  for k, name in enumerate(("fold", "call", "raise_half", "raise_pot", "raise_2pot", "allin"))}
    meta = {"phase": "bc", **source, "features": version, "decisions": n, "epochs": epochs,
            "holdout_accuracy": round(acc, 4), "per_action": per_action,
            "elapsed_s": round(time.perf_counter() - t0, 1), "seed": seed}
    save_checkpoint(run_dir / "ckpt_000000.pt", net, meta)
    (run_dir / "bc.json").write_text(json.dumps(meta, indent=2), "utf-8")
    return meta


def _accuracy(net, X, M, A, idx) -> float:
    import torch
    with torch.no_grad():
        t = torch.from_numpy(idx)
        logits, _ = net(X[t], M[t])
        return float((logits.argmax(-1) == A[t]).float().mean())


# ---- PPO --------------------------------------------------------------------------------

def gae(r: np.ndarray, v: np.ndarray, done: np.ndarray, lam: float) -> tuple[np.ndarray, np.ndarray]:
    """Vorteile und Zielwerte, gamma = 1 innerhalb einer Hand, Episodenende bei done."""
    adv = np.zeros_like(r)
    last = 0.0
    for t in range(len(r) - 1, -1, -1):
        next_v = 0.0 if done[t] else v[t + 1]
        delta = r[t] + next_v - v[t]
        last = delta + (0.0 if done[t] else lam * last)
        adv[t] = last
    return adv, adv + v


def _write_jsonl(path: Path, entry: dict):
    for attempt in range(5):
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            return
        except OSError:
            time.sleep(2 * (attempt + 1))


def snapshot_spec(run: str, it: int) -> str:
    return f"nn?run={run}@{it}"


def eval_fixed(spec: str, cfg: RLConfig, config: TournamentConfig, ex) -> float:
    """ROI gegen den festen Pool auf immer denselben Kartenschemata (Lernkurve, kein Gate)."""
    seeds = [555_000 + i for i in range(cfg.eval_schemes)]
    mus = [(sd, list(DEFAULT_POOL)) for sd in seeds]
    parts = list(ex.map(_eval_chunk, [(spec, mus[i::6], config) for i in range(6) if mus[i::6]]))
    vals = [x for p in parts for x in p]
    return 100 * sum(vals) / len(vals)


def _eval_chunk(args):
    spec, mus, config = args
    return matchup_payouts(spec, mus, config)


def _run_name(run_dir: Path) -> str:
    """Laufname relativ zu data\\rl (auch Unterordner wie 'pros-3/expl-100')."""
    try:
        return run_dir.resolve().relative_to(rl_root().resolve()).as_posix()
    except ValueError:
        return run_dir.name


def train_ppo(run_dir: Path, iterations: int, pool: LeaguePool | list[str], cfg: RLConfig | None = None,
              config: TournamentConfig = DEFAULT_CONFIG, workers: int | None = None, progress=None,
              ex=None) -> dict:
    """ex: vorhandener Prozess-Pool (z. B. fuer Ausbeuter innerhalb eines Laufs) - spart RAM."""
    import torch
    from contextlib import nullcontext
    torch.set_num_threads(max(1, min(8, (workers or 8))))
    run = _run_name(run_dir)
    cfg_path = run_dir / "config.json"
    if cfg_path.exists():
        saved = json.loads(cfg_path.read_text("utf-8"))
        base = RLConfig(**{k: v for k, v in saved["rl"].items() if k in RLConfig.__dataclass_fields__})
        if cfg is not None:
            diff = {k: (getattr(base, k), getattr(cfg, k)) for k in RLConfig.__dataclass_fields__
                    if getattr(cfg, k) != getattr(base, k)}
            if diff:
                msg = f"Hinweis: config.json des Laufs gilt, abweichende Aufrufwerte werden ignoriert: {diff}"
                print(msg, flush=True)
                if progress:
                    progress({"warnung": msg})
        cfg = base
    else:
        cfg = cfg or RLConfig()
        run_dir.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps({"rl_version": RL_VERSION, "rl": asdict(cfg),
                                        "tournament": {"start_stack": config.start_stack,
                                                       "blinds": asdict(config.blinds)}}, indent=2), "utf-8")
    torch.manual_seed(cfg.seed)
    state_path = run_dir / "state.pt"
    start_it = 0
    if state_path.exists():
        st = torch.load(state_path, map_location="cpu", weights_only=True)
        net = build_net(st["hidden"], st.get("features", "feat-1"), st.get("n_actions", N_ACTIONS))
        net.load_state_dict(st["state_dict"])
        opt = torch.optim.Adam(net.parameters(), lr=cfg.lr)
        opt.load_state_dict(st["optimizer"])
        for g in opt.param_groups:
            g["lr"] = cfg.lr              # gespeicherte Lernrate nicht uebernehmen
        start_it = st["iteration"]
    else:
        ck0 = run_dir / "ckpt_000000.pt"
        net = net_from_checkpoint(load_checkpoint(ck0)) if ck0.exists() else build_net(cfg.hidden)
        if not ck0.exists():
            save_checkpoint(ck0, net, {"phase": "random_init"})
        opt = torch.optim.Adam(net.parameters(), lr=cfg.lr)
    snapshots = sorted(int(p.stem.split("_")[1]) for p in run_dir.glob("ckpt_*.pt"))
    anchor_net = None
    if cfg.anchor_coef > 0:
        a_run, _, a_ck = (cfg.anchor or f"{run}:0").partition(":")
        anchor_net = net_from_checkpoint(load_checkpoint(checkpoint_path(a_run, a_ck or 0)))
        anchor_net.eval()
        if FEATURE_SIZES[anchor_net.features_version] > FEATURE_SIZES[net.features_version]:
            raise ValueError(f"Anker {cfg.anchor} nutzt {anchor_net.features_version}, das Netz "
                             f"{net.features_version} - Anker mit derselben oder kleinerer Merkmalsversion waehlen")
        anchor_net.n_in = FEATURE_SIZES[anchor_net.features_version]   # kleinere Version = vordere Merkmale
    ref_data = None
    try:
        from .phh import load_dataset
        ref_data = load_dataset("pluribus", ["Pluribus"], version=net.features_version)
    except (FileNotFoundError, OSError):
        pass
    exploiters_path = run_dir / "exploiters.json"
    exploiters = json.loads(exploiters_path.read_text("utf-8")) if exploiters_path.exists() else []
    if isinstance(pool, LeaguePool):
        pool.self_play = cfg.self_play
        pool.random_share = cfg.random_share
        if cfg.human_share:
            from .humanbots import load_bots
            pool.human_bots = [(b["spec"], b["share"]) for b in load_bots()]
            if not pool.human_bots:
                raise ValueError("--human-share: keine Mensch-Bots (pc.cmd train humans-fit)")
            pool.human_share = cfg.human_share
        for x in exploiters:
            pool.add(x["name"], x["spec"])
    t0 = time.perf_counter()
    last = {}
    with (nullcontext(ex) if ex is not None else ProcessPoolExecutor(workers)) as ex:
        for it in range(start_it + 1, iterations + 1):
            rng = random.Random(cfg.seed * 1_000_003 + it)
            seeds = [rng.randrange(1 << 30) for _ in range(cfg.tournaments)]
            tw = {int(k): float(v) for k, v in (x.split(":") for x in cfg.table_weights.split(",") if x)} or None
            sizes = [random_players(rng, tw) - 1 for _ in seeds] if cfg.random_formats else [None] * len(seeds)
            configs = [random_config(rng, k + 1) for k in sizes] if cfg.random_formats else [config] * len(seeds)
            if isinstance(pool, LeaguePool):
                tables = [pool.sample(rng, snapshot_spec(run, rng.choice(snapshots)) if snapshots else None, size=k)
                          for k in sizes]
            else:
                tables = [list(pool) for _ in seeds]
            if cfg.self_play_seats and snapshots:
                tables = [[snapshot_spec(run, rng.choice(snapshots)) if rng.random() < cfg.self_play_seats else s
                           for s in t] for t in tables]
            w = numpy_weights(net)
            n_jobs = min(len(seeds), 24)
            # grosse Tische dauern laenger: Turniere reihum verteilen, damit alle Prozesse aehnlich lange rechnen
            jobs = [(w, tables[i::n_jobs], seeds[i::n_jobs], configs[i::n_jobs], cfg.reward_scale,
                     rng.randrange(1 << 30), cfg.icm) for i in range(n_jobs)]
            t_roll = time.perf_counter()
            results = list(ex.map(_rollout_job, jobs))
            data = _concat([r[0] for r in results])
            hands = sum(r[1]["hands"] for r in results)
            net_bb = sum(r[1]["net_bb"] for r in results)
            t_roll = time.perf_counter() - t_roll
            adv, ret = gae(data["r"], data["v"], data["done"], cfg.lam)
            upd = _ppo_update(net, opt, data, adv, ret, cfg, anchor_net)
            counts = np.bincount(data["a"], minlength=data["mask"].shape[1]) / max(1, len(data["a"]))
            entry = {"iteration": it, "decisions": int(len(data["a"])), "hands": hands,
                     "bb_per_hand": round(net_bb / max(1, hands), 3),
                     "reward_per_decision": round(float(data["r"].mean()), 4),
                     "actions": [round(float(c), 3) for c in counts], **upd,
                     "rollout_s": round(t_roll, 1), "elapsed_s": round(time.perf_counter() - t0, 1)}
            exploit_now = bool(cfg.exploit_every) and it % cfg.exploit_every == 0 and isinstance(pool, LeaguePool)
            snap = it % cfg.snapshot_every == 0 or it == iterations or exploit_now
            if snap:
                save_checkpoint(run_dir / f"ckpt_{it:06d}.pt", net, {"phase": "ppo", "iteration": it})
                snapshots.append(it)
            torch.save({"hidden": net.pi.in_features, "features": net.features_version,
                        "n_actions": net.pi.out_features, "state_dict": net.state_dict(),
                        "optimizer": opt.state_dict(), "iteration": it}, run_dir / "state.tmp")
            (run_dir / "state.tmp").replace(state_path)
            _write_jsonl(run_dir / "log.jsonl", entry)
            if snap and (it % cfg.eval_every == 0 or it == iterations):
                roi = eval_fixed(snapshot_spec(run, it), cfg, config, ex)
                entry["eval_roi"] = round(roi, 1)
                ev = {"iteration": it, "roi_vs_fixed_pool": round(roi, 1), "schemes": cfg.eval_schemes}
                if ref_data is not None:
                    from .phh import agreement
                    ev["pluribus_top1"] = entry["pluribus_top1"] = agreement(numpy_weights(net), ref_data)["top1"]
                _write_jsonl(run_dir / "eval.jsonl", ev)
            if cfg.bench_every and it % cfg.bench_every == 0:
                from .bench import PRECISE_SETS, compare, is_tournament_set, run_bench
                sets = tuple(x for p in cfg.bench_sets.split(",") for x in (PRECISE_SETS if p == "praezise" else [p]))
                b = run_bench(snapshot_spec(run, it), f"{run}@{it}", sets=sets, ex=ex)
                entry["bench"] = {k: b[k]["roi"] for k in sets if is_tournament_set(k) and k in b}
                if cfg.bench_ref:
                    diffs = {s: d for s, _, _, d in compare(f"{run}@{it}", cfg.bench_ref) if s in sets}
                    if diffs:
                        mean = sum(d["roi"] for d in diffs.values()) / len(diffs)
                        entry["vs_ref"] = {s: [d["roi"], *d["ci95"]] for s, d in diffs.items()}
                        entry["vs_ref_mean"] = round(mean, 2)
                        best_path = run_dir / "best.json"
                        best = json.loads(best_path.read_text("utf-8")) if best_path.exists() else None
                        if best is None or mean > best["vs_ref_mean"]:
                            best_path.write_text(json.dumps({"iteration": it, "ref": cfg.bench_ref,
                                                             "vs_ref_mean": round(mean, 2),
                                                             "vs_ref": entry["vs_ref"]}, indent=2), "utf-8")
            if exploit_now:
                # Ausbeuter: startet beim aktuellen Stand und lernt nur gegen 5 Kopien davon. Wie stark er
                # gewinnt, misst die Ausnutzbarkeit; danach ist er Gegner, dessen Luecken der Bot schliessen muss.
                xr = exploit_test(snapshot_spec(run, it), run_dir / f"ckpt_{it:06d}.pt", iterations=cfg.exploit_iters,
                                  schemes=24, seed=cfg.seed * 1000 + it, config=config, ex=ex,
                                  run_dir=run_dir / f"expl-{it:06d}", tournaments=cfg.exploit_tournaments)
                exploiters.append({"name": f"expl-{it}", "spec": xr["exploiter"], "iteration": it,
                                   "exploiter_roi": xr["exploiter_roi"], "ci95": xr["ci95"]})
                exploiters_path.write_text(json.dumps(exploiters, indent=2), "utf-8")
                pool.add(f"expl-{it}", xr["exploiter"])
                entry["exploitability"] = xr["exploiter_roi"]
                _write_jsonl(run_dir / "eval.jsonl", {"iteration": it, "exploitability": xr["exploiter_roi"],
                                                     "ci95": xr["ci95"]})
            last = entry
            if progress:
                progress(entry)
    return {"run": run, "iterations": iterations, "last": last, "snapshots": snapshots,
            "elapsed_s": round(time.perf_counter() - t0, 1)}


def _ppo_update(net, opt, data: dict, adv: np.ndarray, ret: np.ndarray, cfg: RLConfig, anchor_net=None) -> dict:
    import torch
    n = len(adv)
    if n == 0:
        return {}
    X = torch.from_numpy(data["x"])
    M = torch.from_numpy(data["mask"])
    A = torch.from_numpy(data["a"])
    old = torch.from_numpy(data["logp"])
    adv_t = torch.from_numpy((adv - adv.mean()) / (adv.std() + 1e-8)).float()
    ret_t = torch.from_numpy(ret).float()
    stats = {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0, "approx_kl": 0.0, "clipfrac": 0.0}
    k = 0
    gen = torch.Generator().manual_seed(int(n))
    for _ in range(cfg.epochs):
        perm = torch.randperm(n, generator=gen)
        for i in range(0, n, cfg.minibatch):
            idx = perm[i:i + cfg.minibatch]
            logits, v = net(X[idx], M[idx])
            logp_all = torch.log_softmax(logits, -1)
            logp = logp_all.gather(1, A[idx].unsqueeze(1)).squeeze(1)
            ratio = torch.exp(logp - old[idx])
            a = adv_t[idx]
            pl = -torch.min(ratio * a, torch.clamp(ratio, 1 - cfg.clip, 1 + cfg.clip) * a).mean()
            vl = ((v - ret_t[idx]) ** 2).mean()
            p = logp_all.exp()
            ent = -torch.where(M[idx], p * logp_all, torch.zeros_like(p)).sum(-1).mean()
            loss = pl + cfg.vf_coef * vl - cfg.ent_coef * ent
            if anchor_net is not None:
                with torch.no_grad():
                    xa = X[idx][:, :getattr(anchor_net, "n_in", X.shape[1])]
                    na = anchor_net.pi.out_features
                    ma = M[idx][:, :na]
                    anchor_logp = torch.log_softmax(anchor_net(xa, ma)[0], -1)
                if na == p.shape[1]:
                    kl_each = torch.where(M[idx], p * (logp_all - anchor_logp), torch.zeros_like(p)).sum(-1)
                else:
                    # Anker kennt weniger Aktionen (act-1): die Masse der neuen Aktionen (1/3 Pot, Min-Raise) auf
                    # 'Raise 1/2 Pot' (Index 2) falten, sonst waere sie leinenfrei und das Netz koennte beliebig
                    # viel auf Mini-Bets legen, ohne dass die Leine reagiert (Review 29.10., B3)
                    pf = p[:, :na].clone()
                    extra = p[:, na:].sum(-1)
                    tgt = torch.where(ma[:, 2], torch.full_like(extra, 2, dtype=torch.long),
                                      torch.full_like(extra, na - 1, dtype=torch.long))
                    pf.scatter_add_(1, tgt.unsqueeze(1), extra.unsqueeze(1))
                    lpf = torch.log(pf.clamp_min(1e-9))
                    kl_each = torch.where(ma, pf * (lpf - anchor_logp), torch.zeros_like(pf)).sum(-1)
                # Leine nur, wo der Anker Erfahrung hat (Pluribus: tiefe Stacks, Cash 100 BB, 6 Spieler)
                deep = (torch.expm1(2 * X[idx][:, EFF_STACK_INDEX]) >= cfg.anchor_min_bb).float()
                if cfg.anchor_min_players:
                    deep = deep * (X[idx][:, PLAYERS_INDEX] * 10 >= cfg.anchor_min_players - 0.01).float()
                kl_a = (kl_each * deep).sum() / deep.sum().clamp(min=1.0)
                loss = loss + cfg.anchor_coef * kl_a
                stats["kl_anchor"] = stats.get("kl_anchor", 0.0) + float(kl_a.detach())
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), cfg.max_grad_norm)
            opt.step()
            with torch.no_grad():
                stats["policy_loss"] += float(pl)
                stats["value_loss"] += float(vl)
                stats["entropy"] += float(ent)
                stats["approx_kl"] += float((old[idx] - logp).mean())
                stats["clipfrac"] += float(((ratio - 1).abs() > cfg.clip).float().mean())
            k += 1
    return {key: round(val / k, 4) for key, val in stats.items()}


def exploit_test(target: str, init_ckpt: Path, iterations: int = 40, schemes: int = 48, seed: int = 9,
                 config: TournamentConfig = DEFAULT_CONFIG, workers: int | None = None, progress=None,
                 run_dir: Path | None = None, ex=None, tournaments: int = 96) -> dict:
    """Ausnutzbarkeit: ein Ausbeuter lernt nur gegen 5 Kopien des Pruflings (PPO, ohne Leine).
    Danach spielt er auf frischen Karten gegen diese 5 Kopien. Der Prufling gegen sich selbst hat
    genau 0 % ROI, also ist der ROI des Ausbeuters direkt das Mass: je hoeher, desto ausnutzbarer."""
    import shutil
    from contextlib import nullcontext
    run_dir = run_dir or new_run_dir("exploit")
    run_dir.mkdir(parents=True, exist_ok=True)
    if not (run_dir / "ckpt_000000.pt").exists():
        shutil.copyfile(init_ckpt, run_dir / "ckpt_000000.pt")
    cfg = RLConfig(self_play=0.0, eval_every=10 ** 9, snapshot_every=10 ** 9, seed=seed, bench_every=0,
                   tournaments=tournaments)
    res = train_ppo(run_dir, iterations, [target] * 5, cfg, config=config, workers=workers, progress=progress, ex=ex)
    name = _run_name(run_dir)
    spec = snapshot_spec(name, res["snapshots"][-1])
    mus = [(seed * 7_000_001 + i, [target] * 5) for i in range(schemes)]
    with (nullcontext(ex) if ex is not None else ProcessPoolExecutor(workers)) as ex:
        parts = list(ex.map(_eval_chunk, [(spec, mus[i::12], config) for i in range(12) if mus[i::12]]))
        start = list(ex.map(_eval_chunk, [(snapshot_spec(name, 0), mus[i::12], config)
                                          for i in range(12) if mus[i::12]]))
    vals = [x for p in parts for x in p]
    base = [x for p in start for x in p]
    n = len(vals)
    m = sum(vals) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in vals) / (n - 1)) if n > 1 else float("nan")
    from .evaluate import t95
    half = t95(n) * sd / math.sqrt(n) * 100
    out = {"target": target, "exploiter": spec, "iterations": iterations, "schemes": n,
           "exploiter_roi": round(100 * m, 1), "ci95": [round(100 * m - half, 1), round(100 * m + half, 1)],
           "start_roi": round(100 * sum(base) / n, 1)}
    (run_dir / "exploit.json").write_text(json.dumps(out, indent=2), "utf-8")
    return out


def new_run_dir(prefix: str = "nn") -> Path:
    return rl_root() / f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}"
