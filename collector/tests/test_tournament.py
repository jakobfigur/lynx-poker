import pytest

from pokercollector.ai.agents import make_agent
from pokercollector.ai.engine import Hand
from pokercollector.ai.evaluate import t95
from pokercollector.ai.tournament import (BlindSchedule, TournamentConfig, _assign_places, play_tournament,
                                          run_tournaments)


def test_blind_schedule_double_and_list():
    b = BlindSchedule(10, 20, hands_per_level=8)
    assert b.at(0) == {"level": 0, "sb": 10, "bb": 20, "hands_to_next_level": 8}
    assert b.at(7)["hands_to_next_level"] == 1 and b.at(7)["bb"] == 20
    assert b.at(8)["bb"] == 40 and b.at(17)["bb"] == 80
    lst = BlindSchedule(hands_per_level=5, mode="list", levels=((10, 20), (15, 30), (25, 50)))
    assert [lst.at(h)["bb"] for h in (0, 5, 10, 15, 20)] == [20, 30, 50, 100, 200]


def test_simultaneous_bust_bigger_stack_places_better():
    places = {}
    cfg = TournamentConfig(payouts=(0.5, 0.3, 0.2))
    # 6 Spieler, zwei scheiden gleichzeitig aus, 2 bleiben -> Plaetze 3 und 4
    pays = _assign_places([1, 4], [0, 500, 0, 0, 900, 0], next_place=4, places=places,
                          payout_of=lambda p: cfg.payout_for_place(p, 6))
    assert places == {4: 3.0, 1: 4.0}
    assert pays[4] == pytest.approx(0.2 * 6) and pays[1] == 0
    # Gleicher Stack -> Platz und Auszahlung geteilt
    places = {}
    pays = _assign_places([1, 4], [0, 500, 0, 0, 500, 0], next_place=4, places=places,
                          payout_of=lambda p: cfg.payout_for_place(p, 6))
    assert places == {1: 3.5, 4: 3.5} and pays[1] == pytest.approx(0.6)


def test_tournament_runs_to_single_winner():
    agents = [make_agent(f"{k}:{k}{i}", i) for i, k in enumerate(["tag", "maniac", "station", "lag"])]
    res = play_tournament(agents, TournamentConfig(start_stack=1000), seed=3)
    assert res.finished
    assert sorted(res.places) == [1, 2, 3, 4]
    assert sum(res.payouts) == pytest.approx(4.0)            # Preisgeld = 4 Buy-ins
    assert [e["place"] for e in res.eliminations] == sorted((e["place"] for e in res.eliminations), reverse=True)
    assert len(res.eliminations) == 3


def test_emergency_brake_ranks_by_chips():
    agents = [make_agent(f"caller:c{i}") for i in range(3)]
    cfg = TournamentConfig(start_stack=100000, blinds=BlindSchedule(1, 2, hands_per_level=10_000), max_hands=5)
    res = play_tournament(agents, cfg, seed=1)
    assert not res.finished and res.hands == 5 and sorted(res.places) == [1, 2, 3]


def test_tournament_info_reaches_observation():
    h = Hand([1000] * 3, 0, 10, 20, seed=1, tournament={"level": 2, "players_left": 3})
    o = h.observation(h.to_act)
    assert o.tournament["level"] == 2 and o.stack_bb == 50


def test_short_stack_pushes_or_folds():
    bot = make_agent("tag", 0)
    from pokercollector.poker import FULL_DECK
    deck = ["As", "Ah"] + [c for c in FULL_DECK if c not in ("As", "Ah")]
    # Button 1 -> SB 2, BB 3, Platz 0 (8 BB, AA) handelt zuerst
    h2 = Hand([160, 3000, 3000, 3000], button=1, small_blind=10, big_blind=20, deck=deck)
    o = h2.observation(h2.to_act)
    assert h2.to_act == 0 and o.stack_bb == 8
    a = bot.act(o)
    assert a.kind == "raise" and a.amount == 160            # All-in, kein Mini-Raise
    deck = ["7c", "2d"] + [c for c in FULL_DECK if c not in ("7c", "2d")]
    h3 = Hand([160, 3000, 3000, 3000], button=1, small_blind=10, big_blind=20, deck=deck)
    assert bot.act(h3.observation(0)).kind == "fold"


def test_duplicate_identical_agents_break_even_in_tournaments():
    agents = [make_agent(f"caller:c{i}") for i in range(3)]
    res = run_tournaments(agents, 3, TournamentConfig(start_stack=600), seed=2)
    assert all(r["roi_pct"] == 0 for r in res["results"])


def test_tag_beats_random_in_tournaments():
    agents = [make_agent("tag", 1), make_agent("random", 1), make_agent("random:random2", 2)]
    res = run_tournaments(agents, 12, TournamentConfig(start_stack=1500), seed=5)
    r = {x["agent"]: x for x in res["results"]}
    assert r["tag"]["ci95"][0] > 0
    assert sum(x["roi_pct"] for x in res["results"]) == pytest.approx(0, abs=0.5)


def test_t95():
    assert t95(2) == 12.71 and t95(31) == 2.04 and t95(500) == 1.96
