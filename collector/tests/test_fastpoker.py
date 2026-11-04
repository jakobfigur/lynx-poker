import random

import pytest

from pokercollector.fastpoker import HAVE_NUMBA, evaluate_fast, mc_stats
from pokercollector.poker import FULL_DECK, equity_vs_random, evaluate

pytestmark = pytest.mark.skipif(not HAVE_NUMBA, reason="numba nicht installiert")


def _cmp(a, b):
    return (a > b) - (a < b)


def test_same_ordering_as_python_evaluator():
    rng = random.Random(5)
    hands = [rng.sample(FULL_DECK, 7) for _ in range(6000)]
    # gezielt seltene Kategorien beimischen
    hands += [["As", "Ks", "Qs", "Js", "Ts", "2d", "3c"], ["5h", "4h", "3h", "2h", "Ah", "Kd", "Kc"],
              ["9c", "9d", "9h", "9s", "2c", "3d", "4h"], ["8c", "8d", "8h", "7s", "7c", "7d", "2h"],
              ["Ac", "2d", "3h", "4s", "5c", "9d", "Kh"], ["Ac", "Ad", "Kh", "Ks", "Qc", "Qd", "2h"]]
    py = [evaluate(h) for h in hands]
    fa = [evaluate_fast(h) for h in hands]
    for p, f in zip(py, fa):
        assert p[0] == f >> 20                         # gleiche Kategorie
    for _ in range(40000):
        i, j = rng.randrange(len(hands)), rng.randrange(len(hands))
        assert _cmp(py[i], py[j]) == _cmp(fa[i], fa[j])


def test_mc_equity_matches_known_values():
    # AA gegen eine Zufallshand ~85 %, 72o ~35 %
    s, _, _, _ = mc_stats(["As", "Ad"], [], 1, 20000, seed=3)
    assert abs(s / 20000 - 0.852) < 0.01
    s, _, _, _ = mc_stats(["7c", "2d"], [], 1, 20000, seed=3)
    assert abs(s / 20000 - 0.346) < 0.012
    r = equity_vs_random(["Ah", "Kh"], ["Qh", "Jh", "2c"], 2, iterations=5000, seed=1)
    assert 0.6 < r.equity < 0.75 and r.std_error > 0
