import random

import numpy as np

from pokercollector.ai.agents import make_agent, mc_equity
from pokercollector.ai.engine import Hand
from pokercollector.ai.features import FEATURE_SIZES, features
from pokercollector.ai.observation import Action
from pokercollector.ai.ranges import (COMBO_PCT, board_strength, dead_mask, equity_vs_ranges, opponent_ranges,
                                      range_summary, sample_hands)
from pokercollector.ai.tournament import BlindSchedule, TournamentConfig, play_tournament
from pokercollector.poker import FULL_DECK


def _deck(seat, cards, board):
    rest = [c for c in FULL_DECK if c not in cards + board]
    random.Random(1).shuffle(rest)
    deck = [None] * 52
    for i, c in enumerate(cards):
        deck[2 * seat + i] = c
    for i, c in enumerate(board):
        deck[20 + i] = c
    it = iter(rest)
    return [c if c else next(it) for c in deck]


def _three_bet_spot(hero):
    h = Hand([4000] * 6, 5, 10, 20, deck=_deck(1, hero, ["Kd", "8s", "3c", "2h", "9d"]), hand_id="t")
    h.apply(2, Action.raise_to(60))
    h.apply(3, Action.raise_to(180))
    for s in (4, 5, 0):
        h.apply(s, Action.fold())
    return h.observation(1)


def test_ranges_narrow_with_aggression():
    obs = _three_bet_spot(["Qs", "Jh"])
    r = opponent_ranges(obs)
    assert set(r) == {2, 3} and all(abs(x.sum() - 1) < 1e-9 for x in r.values())
    assert range_summary(r[3])["top10"] > range_summary(r[2])["top10"] > 0.2      # 3-Bet enger als Open
    dead = dead_mask(obs.hole_cards)
    assert r[2][dead].sum() == 0                                                 # eigene Karten unmoeglich
    eq_r = equity_vs_ranges(obs, 2000, 1)
    eq_z = mc_equity(obs.hole_cards, [], 2, 4000, random.Random(2))
    assert eq_r < eq_z - 0.1                                                     # QJ schlecht gegen 3-Bet-Range


def test_board_strength_and_postflop_update():
    s = board_strength(("Ah", "Ad", "7c"))
    assert 0.0 <= s.min() and s.max() <= 1.0
    h = Hand([4000] * 6, 5, 10, 20, deck=_deck(1, ["Qs", "Qh"], ["Kd", "8s", "3c", "2h", "9d"]), hand_id="t2")
    h.apply(2, Action.raise_to(60))
    for x in (3, 4, 5, 0):
        h.apply(x, Action.fold())
    h.apply(1, Action.call())
    h.apply(1, Action.check())
    before = equity_vs_ranges(h.observation(1), 2000, 3)
    h.apply(2, Action.raise_to(80))
    after = equity_vs_ranges(h.observation(1), 2000, 3)
    assert after < before - 0.03                                                 # Bet zeigt Staerke


def test_sample_hands_consistent():
    obs = _three_bet_spot(["Qs", "Jh"])
    hands = sample_hands(opponent_ranges(obs), obs.hole_cards + obs.board, np.random.default_rng(4))
    cards = [c for h in hands.values() for c in h] + obs.hole_cards
    assert set(hands) == {2, 3} and len(cards) == len(set(cards))


def test_feature_versions_and_old_nets(tmp_path, monkeypatch):
    obs = _three_bet_spot(["Qs", "Jh"])
    f1, f2 = features(obs, version="feat-1"), features(obs, version="feat-2")
    assert len(f1) == FEATURE_SIZES["feat-1"] and len(f2) == FEATURE_SIZES["feat-2"]
    assert np.allclose(f1, f2[:len(f1)]) and f2[-3] < f1[4]                      # Range-Equity < Zufalls-Equity
    monkeypatch.setenv("POKERCOLLECTOR_DATA", str(tmp_path))
    from pokercollector.ai.nn_agent import build_net, load_weights, rl_root, save_checkpoint
    for v in ("feat-1", "feat-2"):                                               # alte und neue Netze spielen
        save_checkpoint(rl_root() / f"n-{v}" / "ckpt_000000.pt", build_net(8, v), {"phase": "test"})
        assert load_weights(f"n-{v}", 0)["features"] == v
        tiny = TournamentConfig(start_stack=300, blinds=BlindSchedule(10, 20, 4))
        play_tournament([make_agent(f"nn?run=n-{v}@0:a", 1), make_agent("rock:r", 1)], tiny, seed=1)
