"""Preflop equity table: 169 starting hand classes against 1-9 random opponents.

Computed once by Monte Carlo (`build_preflop_table`) and stored as JSON in package.
The values are estimates with sampling error (stored).
"""

from __future__ import annotations

import json
import random
from functools import lru_cache
from importlib import resources
from pathlib import Path

from ..poker import FULL_DECK, RANKS, evaluate

TABLE_FILE = "preflop_equity.json"


def hand_class(cards: list[str]) -> str:
    """['As','Kd'] -> 'AKo', ['Th','Ts'] -> 'TT', ['9c','8c'] -> '98s'."""
    r1, r2 = cards[0][0], cards[1][0]
    if RANKS.index(r1) < RANKS.index(r2):
        r1, r2 = r2, r1
    if r1 == r2:
        return r1 + r2
    return r1 + r2 + ("s" if cards[0][1] == cards[1][1] else "o")


def all_classes() -> list[str]:
    out = []
    for i in range(12, -1, -1):
        for j in range(i, -1, -1):
            a, b = RANKS[i], RANKS[j]
            if i == j:
                out.append(a + b)
            else:
                out += [a + b + "s", a + b + "o"]
    return out


def class_combos(cls: str) -> int:
    return 6 if len(cls) == 2 else (4 if cls.endswith("s") else 12)


def example_cards(cls: str) -> list[str]:
    if len(cls) == 2:
        return [cls[0] + "s", cls[1] + "h"]
    return [cls[0] + "s", cls[1] + ("s" if cls[2] == "s" else "h")]


def _equity(hero: list[str], opponents: int, iterations: int, rng: random.Random) -> float:
    deck = [c for c in FULL_DECK if c not in hero]
    total = 0.0
    for _ in range(iterations):
        draw = rng.sample(deck, 5 + 2 * opponents)
        board = draw[:5]
        hv = evaluate(hero + board)
        n_eq, lost = 0, False
        for i in range(opponents):
            ov = evaluate(draw[5 + 2 * i: 7 + 2 * i] + board)
            if ov > hv:
                lost = True
                break
            if ov == hv:
                n_eq += 1
        if not lost:
            total += 1.0 / (n_eq + 1)
    return total / iterations


def build_preflop_table(iterations: int = 1500, heads_up_iterations: int = 8000, seed: int = 7,
                        max_opponents: int = 9, progress=None) -> dict:
    """Column '1 opponent' more precise as it determines the ranking of starting hands."""
    rng = random.Random(seed)
    eq = {}
    for i, cls in enumerate(all_classes()):
        eq[cls] = [round(_equity(example_cards(cls), k, heads_up_iterations if k == 1 else iterations, rng), 4)
                   for k in range(1, max_opponents + 1)]
        if progress:
            progress(i + 1, 169)
    return {"iterations": iterations, "heads_up_iterations": heads_up_iterations, "seed": seed,
            "std_error_max": round(0.5 / iterations ** 0.5, 4),
            "std_error_max_heads_up": round(0.5 / heads_up_iterations ** 0.5, 4),
            "note": 'Equity against k random hands, k=1..9 (index 0 = 1 opponent)', "equity": eq}


def save_table(table: dict, path: Path):
    path.write_text(json.dumps(table, indent=1), "utf-8")


@lru_cache(maxsize=1)
def preflop_table() -> dict:
    text = resources.files("pokercollector.ai").joinpath(TABLE_FILE).read_text("utf-8")
    return json.loads(text)


def preflop_equity(cards: list[str], opponents: int) -> float:
    k = max(1, min(9, opponents))
    return preflop_table()["equity"][hand_class(cards)][k - 1]


@lru_cache(maxsize=1)
def _percentiles() -> dict[str, float]:
    """Proportion of all starting hands (by combinations) that are at least this strong.
    0.0 = best hand (AA), 1.0 = worst. Ranking by equity against 1 opponent."""
    eq = preflop_table()["equity"]
    order = sorted(eq, key=lambda c: eq[c][0], reverse=True)
    out, cum = {}, 0
    for c in order:
        cum += class_combos(c)
        out[c] = cum / 1326
    return out


def preflop_percentile(cards: list[str]) -> float:
    return _percentiles()[hand_class(cards)]
