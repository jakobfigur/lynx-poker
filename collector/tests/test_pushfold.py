import numpy as np
import pytest

from pokercollector.ai.agents import make_agent, push_fold_spot
from pokercollector.ai.engine import Hand
from pokercollector.ai.pushfold import (CLASSES, IDX, call_probability, combo_weights, matrix, nash_table,
                                        push_probability)
from pokercollector.poker import FULL_DECK


def test_combo_weights_blockers():
    W = combo_weights()
    assert W[IDX["AA"], IDX["AA"]] == 6          # jede AA-Kombi hat genau eine kartenfremde AA-Kombi
    assert W[IDX["AKs"], IDX["KK"]] == 4 * 3     # AKs blockt pro Kombi einen K -> 3 KK-Kombis
    assert W[IDX["72o"], IDX["AA"]] == 12 * 6


def test_matrix_sane():
    E, W = matrix()
    assert not np.isnan(E).any()
    assert np.allclose(E + E.T, 1.0, atol=1e-3)
    assert 0.80 < E[IDX["AA"], IDX["KK"]] < 0.84      # AA vs KK ~82 %
    assert 0.45 < E[IDX["22"], IDX["AKo"]] < 0.56     # Muenzwurf-Klassiker
    assert 0.05 < E[IDX["AKo"], IDX["AA"]] < 0.10     # AKo vs AA ~7 %


def test_heads_up_is_near_equilibrium():
    t = nash_table()
    for S in (2, 5, 10, 15, 20):
        e = t["entries"][f"1|{S:g}"]
        assert e["exploitability_bb"] < 0.01, (S, e["exploitability_bb"])


def test_monotonic_ranges():
    t = nash_table()
    hu = [t["entries"][f"1|{S:g}"]["push_pct"] for S in t["stacks_bb"]]
    assert all(a >= b - 1.0 for a, b in zip(hu, hu[1:]))           # kleiner Stack -> mehr pushen
    at10 = [t["entries"][f"{k}|10"]["push_pct"] for k in range(1, 9)]
    assert all(a >= b - 1.0 for a, b in zip(at10, at10[1:]))       # mehr Spieler dahinter -> enger
    assert hu[0] > 95


def test_specific_hands():
    assert push_probability(["As", "Ah"], 20, 8) == 1.0
    assert call_probability(["As", "Ah"], 20, 8, 7) == 1.0
    assert push_probability(["7c", "2d"], 10, 1) == 0.0
    assert push_probability(["7c", "2d"], 1, 1) == 1.0
    assert push_probability(["As", "Ah"], 40, 1) is None             # ausserhalb der Tabelle


def test_spot_detection_and_bot_uses_table():
    deck = ["Ks", "Kh"] + [c for c in FULL_DECK if c not in ("Ks", "Kh")]
    h = Hand([200, 3000, 3000, 3000], button=1, small_blind=10, big_blind=20, deck=deck)
    o = h.observation(0)
    spot = push_fold_spot(o)
    assert spot == {"kind": "first_in", "behind": 3, "stack_bb": 10.0}
    a = make_agent("tag").act(o)
    assert a.kind == "raise" and a.amount == 200
    h.apply(0, a)
    o1 = h.observation(h.to_act)
    s1 = push_fold_spot(o1)
    assert s1["kind"] == "facing_push" and s1["index"] == 0 and s1["behind"] == 3 and s1["stack_bb"] == 10.0
