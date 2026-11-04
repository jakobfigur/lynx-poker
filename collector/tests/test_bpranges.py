import numpy as np

from pokercollector.ai.agents import make_agent
from pokercollector.ai.bpranges import COMBO_CLASS, blueprint_ranges, forward_batch
from pokercollector.ai.engine import Hand
from pokercollector.ai.nn_agent import forward_np
from pokercollector.ai.observation import Action, PublicAction
from pokercollector.ai.ranges import COMBO_PCT, dead_mask


def _bp():
    return make_agent("hus?bp=lynx-3-300&iters=10&iters_river=20:hus", 1).bp


def _turn_obs():
    h = Hand([5000, 5000], 0, 50, 100, seed=11, hand_id="bpr")
    h.apply(0, Action.raise_to(250))        # Button opens
    h.apply(1, Action.call())               # BB calls
    h.apply(1, Action.check())
    h.apply(0, Action.check())
    return h, h.observation(h.to_act)


def test_forward_batch_wie_einzeln():
    w = _bp().w
    rng = np.random.default_rng(0)
    x = rng.random((5, w["w1"].shape[1])).astype(np.float32)
    mask = np.array([True, True, False, True, True, True] + [True] * (w["n_actions"] - 6))
    p = forward_batch(w, x, mask)
    for i in range(5):
        assert np.allclose(p[i], forward_np(w, x[i], mask)[0], atol=1e-5)


def test_blueprint_ranges_form_und_blocker():
    h, obs = _turn_obs()
    hero, opp = obs.seat, 1 - obs.seat
    r_hero, r_opp = blueprint_ranges(obs, hero, opp, _bp())
    for r in (r_hero, r_opp):
        assert r.shape == (1326,) and abs(r.sum() - 1) < 1e-9
        assert np.all(r[dead_mask(obs.board)] == 0)             # No one can hold board cards
        assert np.all(r >= 0)
    # Button raised, BB only called: opener holds more strong hands than caller
    top = COMBO_PCT <= 0.15
    raiser, caller = (r_hero, r_opp) if hero == 0 else (r_opp, r_hero)
    assert raiser[top].sum() > caller[top].sum()
    # Classes stay together: all combinations of a hand class without board cards have the same weight
    live = ~dead_mask(obs.board)
    for cls in range(169):
        vals = r_opp[(COMBO_CLASS == cls) & live]
        assert vals.size == 0 or np.allclose(vals, vals[0])


def test_blueprint_ranges_cache_und_fallback():
    h, obs = _turn_obs()
    hero, opp = obs.seat, 1 - obs.seat
    bp = _bp()
    a = blueprint_ranges(obs, hero, opp, bp)
    b = blueprint_ranges(obs, hero, opp, bp)
    assert np.array_equal(a[0], b[0]) and a[0] is not b[0]      # Copy from cache
    # No network as blueprint -> None
    assert blueprint_ranges(obs, hero, opp, make_agent("station", 0)) is None
    # History does not fit engine (action by a seat not to act) -> None
    from dataclasses import replace
    hist = list(obs.history)
    hist.insert(2, PublicAction("preflop", 1, "raise", 250, 150))
    assert blueprint_ranges(replace(obs, history=hist), hero, opp, bp) is None


def test_flop_modellierung_aendert_gewichte_nur_auf_lebenden_kombos():
    h, obs = _turn_obs()
    hero, opp = obs.seat, 1 - obs.seat
    bp = _bp()
    r_pre = blueprint_ranges(obs, hero, opp, bp, ("preflop",))
    r_all = blueprint_ranges(obs, hero, opp, bp, ("preflop", "flop"))
    assert not np.allclose(r_pre[0], r_all[0])
    assert np.all(r_all[0][dead_mask(obs.board)] == 0) and abs(r_all[0].sum() - 1) < 1e-9


def test_agent_nutzt_blueprint_ranges_und_heuristik_per_spec():
    h, obs = _turn_obs()
    a = make_agent("hus?bp=lynx-3-300&iters=10&iters_river=20:hus", 1)
    a.act(obs)
    assert a.last is not None and a.last["ranges"] == "bp"
    b = make_agent("hus?bp=lynx-3-300&iters=10&iters_river=20&ranges=heur:hus", 1)
    b.act(obs)
    assert b.last is not None and b.last["ranges"] == "heur"
    assert "preflop" not in a.streets                           # Preflop solver no longer standard


def test_gleichgewichts_ranges_preflop_fuer_cash():
    ' ranges=eq: preflop ranges from hupreflop.path_ranges. SB opens 2.5x, BB calls (200 BB): opener\n    has more strong hands than caller (3-bets take top hands from caller), ranges normalized, board cards removed.'
    from pokercollector.ai.hupreflop import equilibrium_ranges, path_ranges
    h = Hand([20000, 20000], 0, 50, 100, seed=11, hand_id="eq")
    h.apply(0, Action.raise_to(250))
    h.apply(1, Action.call())
    obs = h.observation(h.to_act)                     # Flop, BB acts first
    r_sb, r_bb = equilibrium_ranges(obs)
    assert r_sb.shape == (169,) and r_bb.shape == (169,) and r_sb.max() <= 1.0 + 1e-9
    assert path_ranges(400, (("raise", 2.5), ("call", 0.0))) is not None
    assert path_ranges(400, (("call", 0.0), ("check", 0.0), ("call", 0.0))) is None   # after limp/check preflop is closed
    bp = _bp()
    a_sb, a_bb = blueprint_ranges(obs, 0, 1, bp, ("eq",))
    for r in (a_sb, a_bb):
        assert abs(r.sum() - 1) < 1e-9 and np.all(r[dead_mask(obs.board)] == 0)
    top = COMBO_PCT <= 0.15
    assert a_sb[top].sum() > a_bb[top].sum()
    # eq,flop: flop actions additionally from network; at turn ranges differ from eq alone
    h.apply(1, Action.check()); h.apply(0, Action.raise_to(300)); h.apply(1, Action.call())
    obs2 = h.observation(h.to_act)
    e1 = blueprint_ranges(obs2, 1, 0, bp, ("eq",))
    e2 = blueprint_ranges(obs2, 1, 0, bp, ("eq", "flop"))
    assert e1 is not None and e2 is not None and not np.allclose(e1[0], e2[0])
    # Specification
    a = make_agent("hus?bp=lynx-3-300&iters=10&iters_river=20&ranges=eq,flop:hus", 1)
    a.act(obs2)
    assert a.last is not None and a.last["ranges"] == "bp"


def test_gegnermodell_und_auto_format():
    'opp_weights: own network for opponent actions (H11 human model); auto=1 selects the configuration per hand.'
    import copy
    h, obs = _turn_obs()
    hero, opp = obs.seat, 1 - obs.seat
    bp = _bp()
    same = blueprint_ranges(obs, hero, opp, bp, ("preflop",), opp_weights=bp.w)
    base = blueprint_ranges(obs, hero, opp, bp, ("preflop",))
    assert np.allclose(same[0], base[0]) and np.allclose(same[1], base[1])
    other = copy.deepcopy(bp.w)
    other["bp"] = other["bp"] + np.array([0, 0, 0, 0, 0, 3.0, 0, 0][:len(other["bp"])], np.float32)  # goes all-in much more often (always allowed)
    diff = blueprint_ranges(obs, hero, opp, bp, ("preflop",), opp_weights=other)
    assert np.allclose(diff[0], base[0])                        # own range unchanged
    assert not np.allclose(diff[1], base[1])                    # opponent range from the other model
    # auto: tournament (tournament set) -> tournament configuration; deep cash -> preflop solver + eq
    a = make_agent("hus?bp=lynx-3-300&iters=10&iters_river=20&auto=1:hus", 1)
    from dataclasses import replace
    a.choose_format(replace(obs, tournament={"level": 1}))
    assert a.streets == ("turn", "river") and a.bp_streets == ("preflop", "flop")
    deep = Hand([20000, 20000], 0, 50, 100, seed=3, hand_id="deep").observation(0)
    a.choose_format(deep)
    assert a.streets == ("preflop", "turn", "river") and a.bp_streets == ("eq", "flop")
    short = Hand([3000, 3000], 0, 50, 100, seed=3, hand_id="short").observation(0)
    a.choose_format(short)
    assert a.streets == ("turn", "river")
