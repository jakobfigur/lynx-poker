"""Push/Fold equilibrium (Nash) for short stacks.

Game: The first player to voluntarily bet can only go all-in (push) or fold.
Players behind can only call or fold. Evaluation is done in chips (chip EV),
not with ICM.

- k = 1 (Small Blind vs Big Blind, heads-up): exact equilibrium of this game.
- k >= 2 players behind: equilibrium of a simplified model. Assumptions:
  at most one caller (ignoring overcalls), callers decide independently,
  card blockers only considered between pusher and respective caller.

Calculation: Equity matrix of all 169x169 starting hand classes (Monte-Carlo, card
blockers weighted exactly), then fictitious play until equilibrium.
Quality is measured by exploitability: how many BB does a perfect
counter-strategy win? In exact equilibrium this is 0.
"""

from __future__ import annotations

import itertools
import json
import random
from functools import lru_cache
from importlib import resources
from pathlib import Path

import numpy as np

from ..poker import FULL_DECK, RANKS, SUITS, evaluate
from .tables import all_classes, hand_class

PUSHFOLD_VERSION = "pushfold-1"
MATRIX_FILE = "hand_vs_hand.json"
TABLE_FILE = "pushfold_nash.json"
CLASSES = all_classes()
IDX = {c: i for i, c in enumerate(CLASSES)}
STACKS = [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 25]
MAX_BEHIND = 8


# ---- Combinations and Blockers ---------------------------------------------

@lru_cache(maxsize=None)
def class_combos_concrete(cls: str) -> tuple[tuple[str, str], ...]:
    r1, r2 = cls[0], cls[1]
    out = []
    if len(cls) == 2:
        for s1, s2 in itertools.combinations(SUITS, 2):
            out.append((r1 + s1, r2 + s2))
    elif cls[2] == "s":
        out = [(r1 + s, r2 + s) for s in SUITS]
    else:
        out = [(r1 + s1, r2 + s2) for s1 in SUITS for s2 in SUITS if s1 != s2]
    return tuple(out)


def combo_weights() -> np.ndarray:
    """W[a, b] = number of compatible (card-independent) combination pairs of class a and b."""
    n = len(CLASSES)
    W = np.zeros((n, n))
    for i, a in enumerate(CLASSES):
        ca = class_combos_concrete(a)
        for j, b in enumerate(CLASSES):
            cb = class_combos_concrete(b)
            W[i, j] = sum(1 for x in ca for y in cb if not (set(x) & set(y)))
    return W


# ---- Equity Matrix -----------------------------------------------------------

def _equity_row(args) -> list[float]:
    i, samples, seed = args
    rng = random.Random(seed * 1000 + i)
    a = CLASSES[i]
    ca = class_combos_concrete(a)
    row = []
    for j, b in enumerate(CLASSES):
        if j < i:
            row.append(None)            # complemented by symmetry
            continue
        pairs = [(x, y) for x in ca for y in class_combos_concrete(b) if not (set(x) & set(y))]
        total = 0.0
        for _ in range(samples):
            x, y = pairs[rng.randrange(len(pairs))]
            rest = [c for c in FULL_DECK if c not in x and c not in y]
            board = rng.sample(rest, 5)
            va, vb = evaluate(list(x) + board), evaluate(list(y) + board)
            total += 1.0 if va > vb else (0.5 if va == vb else 0.0)
        row.append(total / samples)
    return row


def build_matrix(samples: int = 3000, seed: int = 11, processes: int | None = None, progress=None) -> dict:
    from multiprocessing import Pool

    n = len(CLASSES)
    E = np.full((n, n), np.nan)
    with Pool(processes) as pool:
        for k, (i, row) in enumerate(zip(range(n), pool.imap(_equity_row, [(i, samples, seed) for i in range(n)]))):
            for j, v in enumerate(row):
                if v is not None:
                    E[i, j] = v
                    E[j, i] = 1.0 - v
            if progress:
                progress(k + 1, n)
    np.fill_diagonal(E, 0.5)            # same class against each other: exactly 0.5 by symmetry
    W = combo_weights()
    return {"version": PUSHFOLD_VERSION, "samples_per_pair": samples, "seed": seed,
            "std_error_per_pair": round(0.5 / samples ** 0.5, 4), "classes": CLASSES,
            "equity": np.round(E, 4).tolist(), "weights": W.astype(int).tolist()}


@lru_cache(maxsize=1)
def matrix() -> tuple[np.ndarray, np.ndarray]:
    d = json.loads(resources.files("pokercollector.ai").joinpath(MATRIX_FILE).read_text("utf-8"))
    return np.array(d["equity"]), np.array(d["weights"], dtype=float)


# ---- Equilibrium -----------------------------------------------------------

def _blinds(k: int) -> tuple[float, list[float]]:
    """Posted blinds of pusher and callers (in BB). k callers, the last ones are SB/BB."""
    if k == 1:
        return 0.5, [1.0]                       # Pusher = SB, Caller = BB
    callers = [0.0] * (k - 2) + [0.5, 1.0]
    return 0.0, callers


class PushFoldGame:
    """Pusher + k callers, all with effective stack S (in BB)."""

    def __init__(self, S: float, k: int, E: np.ndarray, W: np.ndarray):
        self.S, self.k, self.E, self.W = S, k, E, W
        self.prior = np.array([len(class_combos_concrete(c)) for c in CLASSES], dtype=float) / 1326.0
        self.bp, self.bc = _blinds(k)
        self.dead = 1.5
        self.pot = [2 * S + self.dead - self.bp - b for b in self.bc]

    def pusher_ev(self, calls: list[np.ndarray]) -> np.ndarray:
        """EV (net, BB) of pushing per pusher hand against call probabilities per caller."""
        W, E, S = self.W, self.E, self.S
        wsum = W.sum(axis=1)
        none_call = np.ones(len(CLASSES))
        ev = np.zeros(len(CLASSES))
        for i, c in enumerate(calls):
            wc = W @ c                                   # Weight of calling hands per pusher hand
            p_call = wc / wsum
            eq = np.divide((W * E) @ c, wc, out=np.zeros_like(wc), where=wc > 0)
            ev += none_call * p_call * (eq * self.pot[i] - S)
            none_call *= (1 - p_call)
        ev += none_call * (self.dead - self.bp)
        return ev

    def caller_ev(self, push: np.ndarray, i: int) -> np.ndarray:
        """EV (net) of calling per caller hand against the push range (earlier caller folded)."""
        W, E, S = self.W, self.E, self.S
        wp = W.T @ push                                  # Weight of pushing hands per caller hand
        eq_c = np.divide((W.T * (1 - E.T)) @ push, wp, out=np.zeros_like(wp), where=wp > 0)
        return eq_c * self.pot[i] - S

    def solve(self, iterations: int = 600) -> dict:
        n = len(CLASSES)
        push_avg = np.full(n, 0.5)
        calls_avg = [np.full(n, 0.5) for _ in range(self.k)]
        for t in range(1, iterations + 1):
            br_push = (self.pusher_ev(calls_avg) > -self.bp).astype(float)
            br_calls = [(self.caller_ev(push_avg, i) > -self.bc[i]).astype(float) for i in range(self.k)]
            a = 1.0 / (t + 1)
            push_avg = (1 - a) * push_avg + a * br_push
            calls_avg = [(1 - a) * c + a * b for c, b in zip(calls_avg, br_calls)]
        return {"push": push_avg, "calls": calls_avg}

    def exploitability(self, push: np.ndarray, calls: list[np.ndarray]) -> dict:
        """Gain (BB per hand of the respective player) of a perfect counter-strategy per role."""
        ev_push = self.pusher_ev(calls)
        cur = push * ev_push + (1 - push) * (-self.bp)
        best = np.maximum(ev_push, -self.bp)
        out = {"pusher": float(self.prior @ (best - cur))}
        for i in range(self.k):
            ev_c = self.caller_ev(push, i)
            cur_c = calls[i] * ev_c + (1 - calls[i]) * (-self.bc[i])
            best_c = np.maximum(ev_c, -self.bc[i])
            # Weighted by the probability of facing a push at all
            reach = (self.W.T @ push) / self.W.sum(axis=0)
            out[f"caller{i + 1}"] = float(self.prior @ (reach * (best_c - cur_c)))
        out["total"] = sum(out.values())
        return out

    def range_pct(self, strat: np.ndarray) -> float:
        return float(self.prior @ strat)


_ENC = "0123456789X"


def _encode(p: np.ndarray) -> str:
    return "".join(_ENC[int(round(x * 10))] for x in p)


def _decode(s: str) -> np.ndarray:
    return np.array([_ENC.index(ch) / 10 for ch in s])


def build_table(iterations: int = 600, progress=None) -> dict:
    E, W = matrix()
    entries = {}
    total = MAX_BEHIND * len(STACKS)
    done = 0
    for k in range(1, MAX_BEHIND + 1):
        for S in STACKS:
            g = PushFoldGame(S, k, E, W)
            sol = g.solve(iterations)
            pure_push = (sol["push"] >= 0.5).astype(float)
            pure_calls = [(c >= 0.5).astype(float) for c in sol["calls"]]
            ex_mixed = g.exploitability(sol["push"], sol["calls"])
            ex_pure = g.exploitability(pure_push, pure_calls)
            entries[f"{k}|{S:g}"] = {
                "push": _encode(sol["push"]), "calls": [_encode(c) for c in sol["calls"]],
                "push_pct": round(100 * g.range_pct(sol["push"]), 1),
                "call_pct": [round(100 * g.range_pct(c), 1) for c in sol["calls"]],
                "exploitability_bb": round(ex_mixed["total"], 4),
                "exploitability_pure_bb": round(ex_pure["total"], 4),
            }
            done += 1
            if progress:
                progress(done, total)
    return {"version": PUSHFOLD_VERSION, "iterations": iterations, "stacks_bb": STACKS,
            "max_behind": MAX_BEHIND, "classes": CLASSES, "model": __doc__.strip().splitlines()[0],
            "entries": entries}


@lru_cache(maxsize=1)
def nash_table() -> dict:
    return json.loads(resources.files("pokercollector.ai").joinpath(TABLE_FILE).read_text("utf-8"))


def _entry(stack_bb: float, behind: int) -> dict | None:
    t = nash_table()
    if stack_bb > t["stacks_bb"][-1] or behind < 1:
        return None
    behind = min(behind, t["max_behind"])
    # nearest tabulated stack size
    S = min(t["stacks_bb"], key=lambda s: abs(s - stack_bb))
    return t["entries"][f"{behind}|{S:g}"]


def push_probability(hole: list[str], stack_bb: float, behind: int) -> float | None:
    """Equilibrium probability for push as first player with `behind` players behind.
    None if the stack is larger than the table."""
    e = _entry(stack_bb, behind)
    if e is None:
        return None
    return _ENC.index(e["push"][IDX[hand_class(hole)]]) / 10


def call_probability(hole: list[str], stack_bb: float, behind_at_push: int, my_index: int) -> float | None:
    """Equilibrium call against a push. behind_at_push = player behind the pusher,
    my_index = 0 for the first of them."""
    e = _entry(stack_bb, behind_at_push)
    if e is None:
        return None
    i = min(my_index, len(e["calls"]) - 1)
    return _ENC.index(e["calls"][i][IDX[hand_class(hole)]]) / 10


def range_classes(stack_bb: float, behind: int, role: str = "push", caller: int = 0) -> list[str]:
    e = _entry(stack_bb, behind)
    if e is None:
        return []
    s = e["push"] if role == "push" else e["calls"][caller]
    return [c for c, ch in zip(CLASSES, s) if _ENC.index(ch) >= 5]

def grid_text(stack_bb: float, behind: int, role: str = "push", caller: int = 0) -> str:
    """13x13 grid: top right suited, bottom left offsuit, diagonal pairs.
    '#' = always, '+' = mixed (probability 0.5-0.9), '.' = rare, ' ' = never."""
    e = _entry(stack_bb, behind)
    if e is None:
        return f"No table for {stack_bb} BB (table up to {nash_table()['stacks_bb'][-1]} BB)"
    s = e["push"] if role == "push" else e["calls"][caller]
    probs = {c: _ENC.index(ch) / 10 for c, ch in zip(CLASSES, s)}
    order = RANKS[::-1]
    lines = ["    " + "  ".join(order)]
    for i, r1 in enumerate(order):
        row = []
        for j, r2 in enumerate(order):
            if i == j:
                cls = r1 + r2
            elif i < j:
                cls = r1 + r2 + "s"
            else:
                cls = r2 + r1 + "o"
            p = probs[cls]
            row.append("#" if p >= 0.95 else "+" if p >= 0.5 else "." if p > 0 else " ")
        lines.append(f" {r1}  " + "  ".join(row))
    pct = e["push_pct"] if role == "push" else e["call_pct"][caller]
    who = 'Push (first player)' if role == "push" else f"Call (player {caller + 1} after the pusher)"
    lines.append(f"{who}, {stack_bb:g} BB effective, {behind} players behind: {pct}% of hands; "
                 f"Exploitability {e['exploitability_bb']} BB")
    return "\n".join(lines)

# ---- Evaluation of individual decisions ---------------------------------------

@lru_cache(maxsize=512)
def _game_and_nash(S: float, k: int):
    E, W = matrix()
    e = nash_table()["entries"][f"{k}|{S:g}"]
    return PushFoldGame(S, k, E, W), _decode(e["push"]), [_decode(c) for c in e["calls"]]


def decision_ev(hole: list[str], spot: dict, chose: str) -> dict | None:
    """Evaluates a push/fold decision against opponents playing Nash.
    spot: result from agents.push_fold_spot(); chose: 'push' | 'call' | 'fold'.
    Return: EVs (BB), Nash probability and EV loss of the chosen action."""
    if spot.get("kind") not in ("first_in", "facing_push"):
        return None
    t = nash_table()
    if spot["stack_bb"] > t["stacks_bb"][-1] or spot["behind"] < 1:
        return None
    S = min(t["stacks_bb"], key=lambda s: abs(s - spot["stack_bb"]))
    k = min(spot["behind"], t["max_behind"])
    g, push, calls = _game_and_nash(S, k)
    h = IDX[hand_class(hole)]
    if spot["kind"] == "first_in":
        ev_act = float(g.pusher_ev(calls)[h])
        ev_fold = -g.bp
        nash_p = float(push[h])
        act_name = "push"
    else:
        i = min(spot["index"], k - 1)
        ev_act = float(g.caller_ev(push, i)[h])
        ev_fold = -g.bc[i]
        nash_p = float(calls[i][h])
        act_name = "call"
    best = max(ev_act, ev_fold)
    chosen_ev = ev_act if chose == act_name else ev_fold
    return {"kind": spot["kind"], "stack_bb": S, "behind": k, "hand": CLASSES[h], "action": act_name,
            "chose": chose, "nash_prob": nash_p, "ev_action": round(ev_act, 3), "ev_fold": round(ev_fold, 3),
            "ev_loss": round(best - chosen_ev, 3), "best": act_name if ev_act > ev_fold else "fold"}