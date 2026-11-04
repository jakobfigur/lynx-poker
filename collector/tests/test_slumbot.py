from pokercollector.ai.bench import bench_set, parse_set
from pokercollector.ai.slumbot import CLIENT, allin_ev, parse_action, replay, to_incr


def test_parse_action():
    assert parse_action("b200c/kb300") == [[("b", 200), ("c", None)], [("k", None), ("b", 300)]]
    assert parse_action("") == [[]]


def test_replay_matches_slumbot_result():
    # real Slumbot hand: we are BB, call to the river, result according to Slumbot -3600
    act = "b200c/kb200c/kb800c/kb2400c"
    h = replay(act, 0, ["Ac", "4h"], ["Qs", "8c", "6h", "2h", "Js"], ["Qc", "8s"])
    assert h.done and h.record.results[CLIENT].net == -3600


def test_replay_to_act_and_incr():
    h = replay("b200", 0, ["6d", "3d"], [])
    assert h.to_act == CLIENT
    obs = h.observation(CLIENT)
    from pokercollector.ai.observation import Action
    assert to_incr(obs, Action.call()) == "c"
    assert to_incr(obs, Action.raise_to(600)) == "b600"
    h = replay("", 1, ["Qd", "2h"], [])            # we are SB, first to act: check is not allowed
    assert to_incr(h.observation(CLIENT), Action.check()) == "c"


def test_allin_ev_preflop():
    h = replay("b20000c", 1, ["As", "Ad"], ["2c", "7d", "9h", "Js", "3c"], ["Kc", "Kd"])
    ev = allin_ev(h, ["As", "Ad"], ["Kc", "Kd"])
    assert ev is not None and 0.6 * 20000 < ev < 0.7 * 20000    # AA vs KK ~ 82 % -> (2*0.82-1)*20000


def test_sized_sets_extend_small_ones():
    assert parse_set("mix960") == ("mix96", 960)
    assert parse_set("10max240") == ("10max48", 240)
    assert bench_set("mix960")[:96] == bench_set("mix96")
    assert bench_set("pokerth100")[:48] == bench_set("pokerth48")
