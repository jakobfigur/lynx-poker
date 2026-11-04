import pytest
from helpers import EventStream, standard_hand, table

from pokercollector.ai.agents import REGISTRY, make_agent
from pokercollector.ai.engine import Hand
from pokercollector.ai.evaluate import run_match
from pokercollector.ai.replay import decision_points, observation_from_table_state, review_hands
from pokercollector.ai.tables import hand_class, preflop_equity, preflop_percentile
from pokercollector.reconstruct import reconstruct


def test_tables():
    assert hand_class(["As", "Kd"]) == "AKo" and hand_class(["Kd", "As"]) == "AKo"
    assert hand_class(["9c", "8c"]) == "98s" and hand_class(["Th", "Ts"]) == "TT"
    assert preflop_percentile(["As", "Ah"]) < 0.01
    assert preflop_percentile(["7d", "2c"]) > 0.95
    assert preflop_equity(["As", "Ah"], 1) > preflop_equity(["As", "Ah"], 5)


@pytest.mark.parametrize("kind", sorted(REGISTRY))
def test_agents_always_choose_legal_actions(kind):
    """ Without correction (on_illegal='raise'), each agent must only provide allowed actions."""
    from pokercollector.ai.engine import play_hand
    agents = [make_agent(f"{kind}:{kind}{i}", i) if i == 0 else make_agent(f"maniac:m{i}", i) for i in range(4)]
    for k in range(40):
        play_hand(agents, [2000, 300, 2000, 900], k % 4, 10, 20, seed=k, hand_id=str(k), on_illegal="raise")


def test_agents_are_deterministic():
    a, b = make_agent("lag", 5), make_agent("lag", 5)
    h = Hand([2000] * 3, 0, 10, 20, seed=3, hand_id="x")
    assert a.act(h.observation(0)) == b.act(h.observation(0))


def test_duplicate_identical_agents_break_even():
    agents = [make_agent(f"caller:c{i}") for i in range(4)]
    res = run_match(agents, hands=30, seed=2, duplicate=True)
    assert all(r["net_bb"] == 0 for r in res["results"])


def test_match_is_reproducible_and_random_loses():
    mk = lambda: [make_agent("tag", 1), make_agent("random", 1), make_agent("station", 1)]
    r1 = run_match(mk(), hands=150, seed=9)
    r2 = run_match(mk(), hands=150, seed=9)
    assert r1["results"] == r2["results"]
    res = {r["agent"]: r for r in r1["results"]}
    assert res["random"]["ci95"][1] < 0          # Random player statistically loses reliably
    assert res["tag"]["bb_per_100"] > res["random"]["bb_per_100"]
    assert sum(r["net_bb"] for r in r1["results"]) == pytest.approx(0, abs=0.01)


def test_style_stats_differ():
    agents = [make_agent(s, 1) for s in ("rock", "station", "maniac")]
    res = {r["agent"]: r for r in run_match(agents, hands=80, seed=4)["results"]}
    assert res["rock"]["vpip"] < res["station"]["vpip"]
    assert res["maniac"]["pfr"] > res["station"]["pfr"]


def test_replay_decision_points_from_reconstruction():
    es = table(EventStream())
    standard_hand(es)
    es.at(10.5, seat__0__cards=["6s", "9h"])
    es.at(12.0, info__game_hand=[1, 2])
    hand = reconstruct(es.events)[0].to_dict()
    pts = decision_points(hand)
    assert [(o.street, a["type"]) for o, a in pts] == [("preflop", "call"), ("preflop", "call"), ("flop", "bet")]
    o, _ = pts[0]
    assert o.hole_cards == ["6s", "9h"] and o.to_call == 20 and o.pot == 30 and o.source == "replay"
    o2, _ = pts[1]
    assert o2.to_call == 40 and o2.pot == 100 and o2.stacks[0] == 2980
    o3, _ = pts[2]
    assert o3.board == ["Ah", "7c", "2d"] and o3.can_check and o3.pot == 140
    rows = review_hands([hand], make_agent("equity", 0))
    assert len(rows) == 3 and all(r["suggested"] for r in rows)


def test_observation_from_live_state():
    st = {"seat.0.cards": ["6s", "9h"], "seat.0.present": True, "seat.0.stack": 3000, "seat.0.bet": 0,
          "seat.1.present": True, "seat.1.cards_state": "backs", "seat.1.stack": 2990, "seat.1.bet": 10,
          "seat.2.present": True, "seat.2.cards_state": "backs", "seat.2.stack": 2980, "seat.2.bet": 20,
          "pot.total": 30, "info.blinds": [10, 20], "info.street": "preflop", "marker.D": 0,
          "hero.buttons": [{"action": "fold", "amount": None}, {"action": "call", "amount": 20},
                           {"action": "raise", "amount": 40}]}
    o = observation_from_table_state(st)
    assert (o.to_call, o.min_raise_to, o.pot, o.opponents_in_hand) == (20, 40, 30, 2)
    assert make_agent("equity").act(o).kind in ("fold", "call", "raise")
