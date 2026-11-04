"""Deep CFR: CFR mit neuronalen Netzen statt Tabelle (Brown, Lerer, Gross, Sandholm 2019).

Wie das Tabellen-CFR (cfr.py) spielt der Bot gegen sich selbst und probiert an jeder eigenen
Entscheidung alle Aktionen durch. Statt das Bedauern je grober Situationsklasse in einer Tabelle zu
fuehren, lernt ein Netz (Vorteils-Netz), es aus den 46 Merkmalen vorherzusagen. Aehnliche Situationen
teilen so ihr Wissen - das Tabellen-CFR brauchte fuer jede der ~77 000 Klassen hunderte Besuche.

Je Iteration t:
  1. Durchlaeufe (External Sampling) mit der aktuellen Strategie = Regret Matching auf den
     Vorhersagen des Vorteils-Netzes. An eigenen Knoten: alle Aktionen durchspielen, das
     gemessene Bedauern (Wert der Aktion - Wert der Mischung) mit Gewicht t speichern.
     An fremden Knoten: die gespielte Mischung mit Gewicht t fuer die Durchschnittsstrategie speichern.
  2. Vorteils-Netz auf allen bisher gesammelten Bedauernswerten trainieren (gewichteter MSE).
Am Ende (und zwischendurch): Strategie-Netz auf den gespeicherten Mischungen trainieren. Das ist
die Durchschnittsstrategie, die sich dem Gleichgewicht naehert. Sie hat genau das Format unserer
anderen Netze (nn_agent) und spielt deshalb direkt in Liga und Pruefstand: 'nn?run=<lauf>@<it>'.

Speicher: Reservoir-Stichprobe fester Groesse (wie im Original) - alte und neue Daten bleiben
gleichmaessig vertreten, der Speicherbedarf waechst nicht.
Ablage: data\\rl\\<lauf>\\ mit deepcfr.json, log.jsonl, adv.pt (Vorteils-Netz + Puffer-Stand),
buffers.npz, ckpt_<it>.pt (Strategie-Netze).
"""

from __future__ import annotations

import json
import random
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .cfr import abstract_mask, random_hand
from .engine import Hand
from .features import N_ACTIONS, N_FEATURES, action_mask, features, to_action
from .nn_agent import build_net, numpy_weights, save_checkpoint
from .observation import clamp_action

DEEPCFR_VERSION = "deepcfr-1"


@dataclass
class DeepCFRConfig:
    hidden: int = 128
    traversals: int = 600          # je Prozess und Iteration
    adv_capacity: int = 1_500_000  # Reservoir Vorteils-Daten
    strat_capacity: int = 1_500_000
    adv_steps: int = 600           # Trainingsschritte Vorteils-Netz je Iteration (warm gestartet)
    strat_steps: int = 3000        # Trainingsschritte Strategie-Netz bei jedem Schnappschuss
    batch: int = 4096
    lr: float = 1e-3
    value_scale: float = 0.05      # Bedauern in BB * value_scale (Netz-Ziele um 1 statt um 20)
    snapshot_every: int = 10
    seed: int = 1


def _adv_np(w: dict, x: np.ndarray) -> np.ndarray:
    h = np.maximum(w["w1"] @ x + w["b1"], 0)
    h = np.maximum(w["w2"] @ h + w["b2"], 0)
    return w["wp"] @ h + w["bp"]


def strategy_from_adv(adv: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Regret Matching auf vorhergesagten Vorteilen. Alles <= 0: bestes erlaubtes Aktion (Deep-CFR-Regel)."""
    pos = np.where(mask, np.maximum(adv, 0.0), 0.0)
    s = pos.sum()
    if s > 0:
        return pos / s
    out = np.zeros(N_ACTIONS)
    out[int(np.argmax(np.where(mask, adv, -np.inf)))] = 1.0
    return out


class _Traverser:
    def __init__(self, w: dict | None, rng: random.Random, t: int, scale: float):
        self.w, self.rng, self.t, self.scale = w, rng, t, scale
        self.adv: list[tuple] = []        # (x, legal_mask, regret*scale)
        self.strat: list[tuple] = []      # (x, legal_mask, sigma)
        self.nodes = 0

    def policy(self, x, amask):
        if self.w is None:
            return amask / amask.sum()
        return strategy_from_adv(_adv_np(self.w, x), amask)

    def traverse(self, h: Hand, p: int) -> float:
        if h.done:
            return h.record.results[p].net / h.bb
        s = h.to_act
        obs = h.observation(s)
        x = features(obs)
        legal = action_mask(obs)
        amask = abstract_mask(obs)
        sigma = self.policy(x, amask)
        self.nodes += 1
        if s == p:
            vals = np.zeros(N_ACTIONS)
            for a in np.flatnonzero(amask):
                h2 = h.clone()
                h2.apply(s, clamp_action(obs, to_action(obs, int(a))))
                vals[a] = self.traverse(h2, p)
            ev = float(sigma @ vals)
            self.adv.append((x, legal, np.where(amask, vals - ev, 0.0) * self.scale))
            return ev
        self.strat.append((x, legal, sigma))
        a = self.rng.choices(range(N_ACTIONS), weights=sigma)[0]
        h.apply(s, clamp_action(obs, to_action(obs, a)))
        return self.traverse(h, p)


def _job(args):
    w, n, t, scale, seed = args
    rng = random.Random(seed)
    tr = _Traverser(w, rng, t, scale)
    for _ in range(n):
        h = random_hand(rng)
        tr.traverse(h, rng.randrange(h.n))

    def pack(rows):
        if not rows:
            return np.zeros((0, N_FEATURES), np.float32), np.zeros((0, N_ACTIONS), bool), np.zeros((0, N_ACTIONS), np.float32)
        return (np.stack([r[0] for r in rows]).astype(np.float32), np.stack([r[1] for r in rows]),
                np.stack([r[2] for r in rows]).astype(np.float32))
    return pack(tr.adv), pack(tr.strat), tr.nodes


class Reservoir:
    """Gleichmaessige Stichprobe ueber alle je gesehenen Datenpunkte (Algorithmus R), feste Groesse."""

    def __init__(self, capacity: int, rng: np.random.Generator):
        self.cap = capacity
        self.x = np.zeros((capacity, N_FEATURES), np.float32)
        self.m = np.zeros((capacity, N_ACTIONS), bool)
        self.y = np.zeros((capacity, N_ACTIONS), np.float32)
        self.t = np.zeros(capacity, np.float32)
        self.n = 0          # gefuellt
        self.seen = 0       # insgesamt gesehen
        self.rng = rng

    def add(self, x, m, y, t: int):
        k = len(x)
        if k == 0:
            return
        free = min(k, self.cap - self.n)
        if free:
            sl = slice(self.n, self.n + free)
            self.x[sl], self.m[sl], self.y[sl], self.t[sl] = x[:free], m[:free], y[:free], t
            self.n += free
        rest = k - free
        if rest:
            # Platz j fuer den i-ten neuen Punkt mit Wahrscheinlichkeit cap/(seen+i+1)
            idx = self.seen + free + np.arange(rest)
            r = (self.rng.random(rest) * (idx + 1)).astype(np.int64)
            keep = r < self.cap
            src = free + np.flatnonzero(keep)
            dst = r[keep]
            self.x[dst], self.m[dst], self.y[dst], self.t[dst] = x[src], m[src], y[src], t
        self.seen += k

    def state(self) -> dict:
        return {"x": self.x[:self.n], "m": self.m[:self.n], "y": self.y[:self.n], "t": self.t[:self.n],
                "seen": np.array(self.seen)}

    def load(self, d: dict, prefix: str):
        n = len(d[prefix + "t"])
        self.x[:n], self.m[:n], self.y[:n], self.t[:n] = d[prefix + "x"], d[prefix + "m"], d[prefix + "y"], d[prefix + "t"]
        self.n = n
        self.seen = int(d[prefix + "seen"])


def _train_adv(net, buf: Reservoir, cfg: DeepCFRConfig, gen) -> float:
    import torch
    opt = torch.optim.Adam(net.parameters(), lr=cfg.lr)
    X, M, Y, T = (torch.from_numpy(a[:buf.n]) for a in (buf.x, buf.m, buf.y, buf.t))
    w_all = T / T.mean()
    total = 0.0
    for _ in range(cfg.adv_steps):
        idx = torch.randint(0, buf.n, (min(cfg.batch, buf.n),), generator=gen)
        h = net.body(X[idx])
        pred = net.pi(h)
        err = torch.where(M[idx], (pred - Y[idx]) ** 2, torch.zeros_like(pred)).sum(-1)
        loss = (err * w_all[idx]).mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
        total += float(loss.detach())
    return total / cfg.adv_steps


def train_strategy(buf: Reservoir, cfg: DeepCFRConfig, gen):
    """Durchschnittsstrategie: Netz lernt die gespeicherten Mischungen (gewichtet mit t, Linear CFR)."""
    import torch
    net = build_net(cfg.hidden)
    opt = torch.optim.Adam(net.parameters(), lr=cfg.lr)
    X, M, Y, T = (torch.from_numpy(a[:buf.n]) for a in (buf.x, buf.m, buf.y, buf.t))
    w_all = T / T.mean()
    loss_sum = 0.0
    for _ in range(cfg.strat_steps):
        idx = torch.randint(0, buf.n, (min(cfg.batch, buf.n),), generator=gen)
        logits, _ = net(X[idx], M[idx])
        logp = torch.log_softmax(logits, -1)
        ce = -(Y[idx] * torch.where(M[idx], logp, torch.zeros_like(logp))).sum(-1)
        loss = (ce * w_all[idx]).mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
        loss_sum += float(loss.detach())
    return net, loss_sum / cfg.strat_steps


def train_deepcfr(run_dir: Path, iterations: int, cfg: DeepCFRConfig | None = None, workers: int | None = None,
                  progress=None, on_snapshot=None) -> dict:
    import os
    import torch
    run_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = run_dir / "deepcfr.json"
    if cfg_path.exists():
        saved = json.loads(cfg_path.read_text("utf-8"))["config"]
        cfg = DeepCFRConfig(**{k: v for k, v in saved.items() if k in DeepCFRConfig.__dataclass_fields__})
    else:
        cfg = cfg or DeepCFRConfig()
        cfg_path.write_text(json.dumps({"version": DEEPCFR_VERSION, "config": asdict(cfg)}, indent=2), "utf-8")
    torch.manual_seed(cfg.seed)
    gen = torch.Generator().manual_seed(cfg.seed)
    nrng = np.random.default_rng(cfg.seed)
    adv_buf = Reservoir(cfg.adv_capacity, nrng)
    strat_buf = Reservoir(cfg.strat_capacity, nrng)
    adv_net = build_net(cfg.hidden)
    start = 0
    if (run_dir / "adv.pt").exists() and (run_dir / "buffers.npz").exists():
        st = torch.load(run_dir / "adv.pt", map_location="cpu", weights_only=True)
        adv_net.load_state_dict(st["state_dict"])
        start = st["iteration"]
        with np.load(run_dir / "buffers.npz") as z:      # Datei schliessen: Windows ersetzt sonst nicht
            d = {k: z[k] for k in z.files}
        adv_buf.load(d, "a_")
        strat_buf.load(d, "s_")
    n_jobs = workers or os.cpu_count() or 4
    t0 = time.perf_counter()
    last = {}
    with ProcessPoolExecutor(n_jobs) as ex:
        for t in range(start + 1, iterations + 1):
            w = numpy_weights(adv_net) if t > 1 else None
            t_r = time.perf_counter()
            res = list(ex.map(_job, [(w, cfg.traversals, t, cfg.value_scale, cfg.seed * 1_000_003 + t * 7919 + j)
                                     for j in range(n_jobs)]))
            nodes = 0
            for (ax, am, ay), (sx, sm, sy), nd in res:
                adv_buf.add(ax, am, ay, t)
                strat_buf.add(sx, sm, sy, t)
                nodes += nd
            t_roll = time.perf_counter() - t_r
            t_tr = time.perf_counter()
            adv_loss = _train_adv(adv_net, adv_buf, cfg, gen)
            t_tr = time.perf_counter() - t_tr
            last = {"iteration": t, "nodes": nodes, "traversals": n_jobs * cfg.traversals,
                    "adv_samples": adv_buf.n, "adv_seen": adv_buf.seen, "strat_samples": strat_buf.n,
                    "adv_loss": round(adv_loss, 5), "rollout_s": round(t_roll, 1), "train_s": round(t_tr, 1),
                    "elapsed_s": round(time.perf_counter() - t0, 1)}
            if t % cfg.snapshot_every == 0 or t == iterations:
                snet, sloss = train_strategy(strat_buf, cfg, gen)
                save_checkpoint(run_dir / f"ckpt_{t:06d}.pt", snet, {"phase": "deepcfr", "iteration": t,
                                                                     "strategy_loss": round(sloss, 5)})
                last["strategy_loss"] = round(sloss, 5)
                torch.save({"state_dict": adv_net.state_dict(), "iteration": t}, run_dir / "adv.tmp")
                (run_dir / "adv.tmp").replace(run_dir / "adv.pt")
                a, s = adv_buf.state(), strat_buf.state()
                tmp = run_dir / "buffers.tmp.npz"
                np.savez(tmp, **{"a_" + k: v for k, v in a.items()}, **{"s_" + k: v for k, v in s.items()})
                tmp.replace(run_dir / "buffers.npz")
                if on_snapshot:
                    on_snapshot(t, last, ex)
            with open(run_dir / "log.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(last) + "\n")
            if progress:
                progress(last)
    return last
