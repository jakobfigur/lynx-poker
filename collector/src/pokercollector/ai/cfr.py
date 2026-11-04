"""Gleichgewicht statt Ausbeutung: Monte-Carlo-CFR wie beim Blueprint von Pluribus.

Idee (Counterfactual Regret Minimization): Der Bot spielt immer wieder Haende gegen sich selbst.
An jeder eigenen Entscheidung probiert er ALLE Aktionen durch (Kopie des Spielstands) und merkt
sich, wie viel besser oder schlechter jede gewesen waere als seine aktuelle Mischung ("Bedauern",
regret). Kuenftig spielt er Aktionen mit positivem Bedauern entsprechend oefter. Der Durchschnitt
aller Strategien naehert sich einem Gleichgewicht: einer Strategie, die sich kaum ausnutzen laesst -
egal gegen wen. Das ist das Gegenteil von PPO, das die aktuellen Gegner bestmoeglich ausbeutet.

Wie bei Pluribus:
- External Sampling: eigene Aktionen werden alle durchgespielt, Gegner/Karten zufaellig gezogen.
- Linear CFR: spaetere Runden zaehlen staerker (Gewicht = Rundennummer).
- Abstraktion: aehnliche Situationen teilen sich einen Eintrag ("Infoset"):
  Strasse, Handstaerke-Klasse, Position, Spielerzahl, Pot Odds, eff. Stack, Raises, Aggressor.
  Aktionen: Fold, Check/Call, Raise 1/2, 1, 2 Pot, All-in; ab 2 Raises je Strasse nur Fold/Call/All-in.
Jede Hand wird mit zufaelliger Spielerzahl (2-6) und zufaelligen Stacks (3-150 BB) gespielt, damit
sowohl Turnier-Kurzstacks als auch tiefe Stacks abgedeckt sind. Wert = Chip-Ergebnis in BB.

Grenzen: Tabellen-CFR mit grober Abstraktion (Pluribus: viel feiner, C++, 64 Kerne, 8 Tage). Ob das
Ergebnis stark ist, entscheidet der Pruefstand. Spaeter: Durchschnittsstrategie ins Netz uebertragen
und als Anker/Leine fuer PPO nutzen.

Ablage: data\\rl\\<lauf>\\cfr_state.npz (Fortsetzen), cfr_avg.npz (Strategie zum Spielen), log.jsonl.
Liga: 'cfr?run=<lauf>'.
"""

from __future__ import annotations

import json
import math
import random
import time
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from .agents import BaseAgent, mc_equity
from .engine import Hand
from .features import N_ACTIONS, action_mask, to_action
from .observation import Observation, clamp_action
from .tables import preflop_percentile

CFR_VERSION = "mccfr-1"
HAND_BUCKETS_PRE = 20
HAND_BUCKETS_POST = 12
_RADIX = (4, 20, 6, 5, 5, 5, 4, 2)         # Strasse, Hand, Position, Spieler, Pot Odds, Stack, Raises, Aggressor


def abstract_mask(obs: Observation) -> np.ndarray:
    m = action_mask(obs)
    if obs.raises_this_street() >= 2:
        m[2:5] = False
    return m


def _bucket(x: float, edges) -> int:
    for i, e in enumerate(edges):
        if x < e:
            return i
    return len(edges)


def infokey(obs: Observation, cache: dict | None = None) -> int:
    st = ("preflop", "flop", "turn", "river").index(obs.street)
    opp = max(1, obs.opponents_in_hand)
    if st == 0:
        hb = min(HAND_BUCKETS_PRE - 1, int(preflop_percentile(obs.hole_cards) * HAND_BUCKETS_PRE))
    else:
        ck = (obs.hole_cards[0], obs.hole_cards[1], tuple(obs.board), opp)
        eq = cache.get(ck) if cache is not None else None
        if eq is None:
            seed = zlib.crc32(repr(ck).encode())     # stabil ueber Prozesse (hash() ist zufaellig gesalzen)
            eq = mc_equity(obs.hole_cards, obs.board, opp, 200, random.Random(seed))
            if cache is not None:
                cache[ck] = eq
        hb = min(HAND_BUCKETS_POST - 1, int(eq * HAND_BUCKETS_POST))
    pos = max(0, min(5, obs.position()))
    players = min(6, opp + 1) - 2
    po = 0 if obs.to_call == 0 else 1 + _bucket(obs.to_call / (obs.pot + obs.to_call), (0.15, 0.25, 0.35))
    others = [obs.stacks[s] + obs.bets[s] for s in range(obs.num_seats)
              if s != obs.seat and obs.in_hand[s] and not obs.folded[s]]
    eff = min(obs.my_stack + obs.my_bet, max(others)) / obs.big_blind if others else 0
    sb = _bucket(eff, (8, 15, 25, 50))
    raises = min(3, obs.raises_this_street())
    aggr = [a.seat for a in obs.history if a.kind in ("bet", "raise")]
    ag = 1 if aggr and aggr[-1] == obs.seat else 0
    code = 0
    for v, r in zip((st, hb, pos, players, po, sb, raises, ag), _RADIX):
        code = code * r + v
    return code


def decode(code: int) -> dict:
    out = []
    for r in reversed(_RADIX):
        out.append(code % r)
        code //= r
    names = ("street", "hand", "position", "players_minus2", "pot_odds", "stack", "raises", "aggressor")
    return dict(zip(names, reversed(out)))


def regret_matching(reg: np.ndarray | None, mask: np.ndarray) -> np.ndarray:
    if reg is None:
        p = mask.astype(np.float64)
    else:
        p = np.where(mask, np.maximum(reg, 0.0), 0.0)
        if p.sum() <= 0:
            p = mask.astype(np.float64)
    return p / p.sum()


# ---- Traversierung (laeuft in den Arbeitsprozessen) ---------------------------------------

class _Worker:
    def __init__(self, regrets: dict, rng: random.Random):
        self.regrets = regrets
        self.rng = rng
        self.d_regret: dict[int, np.ndarray] = {}
        self.d_strategy: dict[int, np.ndarray] = {}
        self.eq_cache: dict = {}
        self.nodes = 0

    def traverse(self, h: Hand, p: int) -> float:
        if h.done:
            return h.record.results[p].net / h.bb
        s = h.to_act
        obs = h.observation(s)
        key = infokey(obs, self.eq_cache)
        mask = abstract_mask(obs)
        sigma = regret_matching(self.regrets.get(key), mask)
        self.nodes += 1
        if s == p:
            vals = np.zeros(N_ACTIONS)
            for a in np.flatnonzero(mask):
                h2 = h.clone()
                h2.apply(s, clamp_action(obs, to_action(obs, int(a))))
                vals[a] = self.traverse(h2, p)
            ev = float(sigma @ vals)
            d = self.d_regret.get(key)
            delta = np.where(mask, vals - ev, 0.0)
            self.d_regret[key] = delta if d is None else d + delta
            return ev
        d = self.d_strategy.get(key)
        self.d_strategy[key] = sigma.copy() if d is None else d + sigma
        a = self.rng.choices(range(N_ACTIONS), weights=sigma)[0]
        h.apply(s, clamp_action(obs, to_action(obs, a)))
        return self.traverse(h, p)


def random_hand(rng: random.Random) -> Hand:
    n = rng.choices([2, 3, 4, 5, 6], weights=[1, 1, 1, 1, 2])[0]
    bb = 20
    stacks = [int(bb * math.exp(rng.uniform(math.log(3), math.log(150)))) for _ in range(n)]
    return Hand(stacks, rng.randrange(n), bb // 2, bb, seed=rng.randrange(1 << 30), hand_id="cfr")


def _job(args):
    regrets, n_traversals, seed = args
    rng = random.Random(seed)
    w = _Worker(regrets, rng)
    t0 = time.perf_counter()
    for _ in range(n_traversals):
        h = random_hand(rng)
        w.traverse(h, rng.randrange(h.n))
    return w.d_regret, w.d_strategy, w.nodes, time.perf_counter() - t0


# ---- Steuerung ---------------------------------------------------------------------------

def _save_state(path: Path, regrets: dict, strategy: dict, rnd: int):
    keys = np.array(sorted(regrets.keys() | strategy.keys()), np.int64)
    R = np.stack([regrets.get(int(k), np.zeros(N_ACTIONS)) for k in keys]).astype(np.float32) if len(keys) else \
        np.zeros((0, N_ACTIONS), np.float32)
    S = np.stack([strategy.get(int(k), np.zeros(N_ACTIONS)) for k in keys]).astype(np.float32) if len(keys) else \
        np.zeros((0, N_ACTIONS), np.float32)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, keys=keys, regrets=R, strategy=S, round=np.array(rnd))
    tmp.replace(path)


def _load_state(path: Path) -> tuple[dict, dict, int]:
    # Jedes z[...] entpackt das GANZE Array neu - also je Array genau einmal lesen; Datei danach schliessen
    with np.load(path) as z:
        keys, R, S, rnd = z["keys"], z["regrets"].astype(np.float64), z["strategy"].astype(np.float64), int(z["round"])
    regrets = {int(k): R[i].copy() for i, k in enumerate(keys) if R[i].any()}
    strategy = {int(k): S[i].copy() for i, k in enumerate(keys) if S[i].any()}
    return regrets, strategy, rnd


def save_average(path: Path, strategy: dict):
    keys = np.array(sorted(strategy), np.int64)
    P = np.stack([strategy[int(k)] / strategy[int(k)].sum() for k in keys]).astype(np.float32) if len(keys) else \
        np.zeros((0, N_ACTIONS), np.float32)
    visits = np.array([strategy[int(k)].sum() for k in keys], np.float32)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, keys=keys, probs=P, weight=visits)
    tmp.replace(path)


def train_cfr(run_dir: Path, rounds: int, traversals: int = 400, workers: int | None = None, seed: int = 1,
              progress=None) -> dict:
    """rounds: Zielrunde (Gesamtzahl). Je Runde: workers x traversals Durchlaeufe mit der Strategie vom
    Rundenbeginn, dann Bedauern/Strategie mit Gewicht = Runde (Linear CFR) addieren."""
    run_dir.mkdir(parents=True, exist_ok=True)
    state = run_dir / "cfr_state.npz"
    regrets, strategy, start = ({}, {}, 0)
    if state.exists():
        regrets, strategy, start = _load_state(state)
    import os
    n_jobs = workers or os.cpu_count() or 4
    t0 = time.perf_counter()
    last = {}
    with ProcessPoolExecutor(n_jobs) as ex:
        for rnd in range(start + 1, rounds + 1):
            snap = {k: v.astype(np.float32) for k, v in regrets.items()}
            t_r = time.perf_counter()
            results = list(ex.map(_job, [(snap, traversals, seed * 1_000_003 + rnd * 1009 + j) for j in range(n_jobs)]))
            nodes = 0
            for d_reg, d_str, nd, _ in results:
                nodes += nd
                for k, v in d_reg.items():
                    r = regrets.get(k)
                    regrets[k] = v * rnd if r is None else r + v * rnd
                for k, v in d_str.items():
                    s = strategy.get(k)
                    strategy[k] = v * rnd if s is None else s + v * rnd
            el = time.perf_counter() - t_r
            last = {"round": rnd, "infosets": len(regrets), "avg_infosets": len(strategy), "nodes": nodes,
                    "traversals": n_jobs * traversals, "round_s": round(el, 1),
                    "traversals_per_s": round(n_jobs * traversals / el, 1),
                    "elapsed_s": round(time.perf_counter() - t0, 1)}
            with open(run_dir / "log.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(last) + "\n")
            if rnd % 5 == 0 or rnd == rounds:
                _save_state(state, regrets, strategy, rnd)
                save_average(run_dir / "cfr_avg.npz", strategy)
            if progress:
                progress(last)
    return last


# ---- Spielen mit der Durchschnittsstrategie ----------------------------------------------------

_POLICY_CACHE: dict = {}


def load_policy(run: str) -> dict:
    from .nn_agent import rl_root
    p = rl_root() / run / "cfr_avg.npz"
    key = (str(p), p.stat().st_mtime)
    if key not in _POLICY_CACHE:
        with np.load(p) as z:                         # je Array einmal entpacken (sonst Speicher x Eintraege)
            keys, probs = z["keys"], z["probs"]
        _POLICY_CACHE[key] = {int(k): probs[i] for i, k in enumerate(keys)}
    return _POLICY_CACHE[key]


class CFRAgent(BaseAgent):
    """Spielt die Durchschnittsstrategie. Unbekannte Situation: einfache Equity-Regel (gezaehlt)."""
    name = "cfr"

    def __init__(self, policy: dict, seed: int = 0, name: str | None = None):
        super().__init__(seed, name)
        self.policy = policy
        self.cache: dict = {}
        self.hits = 0
        self.misses = 0

    def act(self, obs: Observation):
        if len(obs.hole_cards) != 2:
            return self.passive(obs)
        mask = abstract_mask(obs)
        p = self.policy.get(infokey(obs, self.cache))
        r = self.rng(obs)
        if p is None or not (p * mask).any():
            self.misses += 1
            eq = mc_equity(obs.hole_cards, obs.board, max(1, obs.opponents_in_hand), 100, r)
            po = obs.to_call / (obs.pot + obs.to_call) if obs.to_call else 0.0
            return self.passive(obs) if eq < po else to_action(obs, 1)
        self.hits += 1
        p = np.where(mask, p, 0.0)
        p = p / p.sum()
        idx = int(min(np.searchsorted(np.cumsum(p), r.random(), side="right"), N_ACTIONS - 1))
        while not mask[idx]:
            idx -= 1
        return to_action(obs, idx)


def make_cfr_agent(params: str, seed: int = 0) -> CFRAgent:
    kv = dict(p.partition("=")[::2] for p in params.split("&") if p)
    if "run" not in kv:
        raise ValueError("cfr-Bot: 'cfr?run=<Lauf>'")
    return CFRAgent(load_policy(kv["run"]), seed)
