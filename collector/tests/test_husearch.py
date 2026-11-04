import numpy as np

from pokercollector.ai.agents import make_agent
from pokercollector.ai.evaluate import run_match
from pokercollector.ai.husearch import (COMBOS, N_COMBOS, State, _fold_sums, _showdown, board_tables, build_tree,
                                        hand_index, solve)
from pokercollector.ai.ranges import dead_mask
from pokercollector.fastpoker import CARD_INDEX


def _uniform(board):
    r = (~dead_mask(board)).astype(float)
    return r / r.sum()


def _river_state(board, to_act=0, bets=(0, 0), acted=(False, False)):
    return State(board=tuple(CARD_INDEX[c] for c in board), committed=(500 + bets[0], 500 + bets[1]), bets=bets,
                 stacks=(2000 - bets[0], 2000 - bets[1]), to_act=to_act, last_inc=100, raises=int(any(bets)),
                 acted=acted, oop=0, bb=100)


def _conflict():
    a = COMBOS[:, None, :]
    b = COMBOS[None, :, :]
    return (a[..., 0] == b[..., 0]) | (a[..., 0] == b[..., 1]) | (a[..., 1] == b[..., 0]) | (a[..., 1] == b[..., 1])


def test_showdown_und_fold_wie_brute_force():
    board = ["Ah", "Kd", "7c", "2s", "9h"]
    vals, order, nvalid = board_tables([tuple(CARD_INDEX[c] for c in board)])
    rng = np.random.default_rng(1)
    r = rng.random(N_COMBOS) * (vals[0] >= 0)
    clash = _conflict()
    v = vals[0]
    sign = np.sign(v[:, None] - v[None, :]) * ~clash * (v[:, None] >= 0) * (v[None, :] >= 0)
    out = np.zeros(N_COMBOS)
    _showdown(r, v, order[0], nvalid[0], COMBOS, out)
    ok = v >= 0
    assert np.allclose(out[ok], (sign @ r)[ok])
    _fold_sums(r, COMBOS, out)
    assert np.allclose(out, (~clash).astype(float) @ r)


def test_river_nullsumme_und_nuts_setzen():
    board = ["Ah", "Kd", "7c", "2s", "9h"]
    r = _uniform(board)
    tree, strat, v = solve(_river_state(board), r, r, 300)
    assert abs(float(r @ v[0]) + float(r @ v[1])) < 5          # zero sum (except for convergence)
    assert tree.root_actions[0] == ("check", None)
    aa = hand_index(["As", "Ad"])                                # set aces: almost the nuts
    assert strat[1:, aa].sum() > 0.5                             # usually bets
    assert np.allclose(strat.sum(0), 1)


def test_gegen_einsatz_fold_call_raise():
    board = ["Ah", "Kd", "7c", "2s", "9h"]
    r = _uniform(board)
    tree, strat, _ = solve(_river_state(board, to_act=0, bets=(0, 750), acted=(False, True)), r, r, 200)
    kinds = [k for k, _ in tree.root_actions]
    assert kinds[:2] == ["fold", "call"] and "raise" in kinds
    trash = hand_index(["4c", "3d"])                             # nothing, no blocker: usually folds
    assert strat[0, trash] > 0.5
    aa = hand_index(["As", "Ad"])
    assert strat[0, aa] < 0.05


def test_turn_baum_alle_rivercards():
    board = ["Ah", "Kd", "7c", "2s"]
    st = State(board=tuple(CARD_INDEX[c] for c in board), committed=(500, 500), bets=(0, 0), stacks=(9500, 9500),
               to_act=0, last_inc=100, raises=0, acted=(False, False), oop=0, bb=100)
    tree = build_tree(st)
    assert tree.div == 44.0
    chance = np.nonzero(tree.kind == 3)[0]
    assert len(chance) > 0 and all(tree.n_children[c] == 48 for c in chance)
    assert all(len(b) == 5 for b in tree.boards)


def test_agent_spielt_regelkonform_heads_up():
    a = make_agent("hus?bp=lynx-3-300&iters=10&iters_river=20:hus", 1)
    b = make_agent("station", 1)
    searched = []
    orig = a.act

    def act(obs):
        r = orig(obs)
        if a.last is not None:
            searched.append(r)
        return r
    a.act = act
    res = run_match([a, b], 10, seed=3, small_blind=50, big_blind=100, stack_bb=200)
    assert res["config"]["hands_played"] == 20
    assert searched                                              # search was applied at least once


def test_loesen_ab_strassenbeginn_mit_echter_groesse():
    board = ["Ah", "Kd", "7c", "2s", "9h"]
    r = _uniform(board)
    st = _river_state(board, to_act=1, acted=(False, False))      # opponent acts first
    st = State(**{**st.__dict__, "oop": 1})
    tree, strat, _ = solve(st, r, r, 150, path=(("raise", 610),))  # he bets 610 (not standard size)
    assert tree.player[tree.current] == 0
    kinds = [k for k, _ in tree.root_actions]
    assert kinds[:2] == ["fold", "call"]
    assert strat.shape[0] == len(tree.root_actions) and np.allclose(strat.sum(0), 1)
    trash = hand_index(["4c", "3d"])
    aa = hand_index(["As", "Ad"])
    assert strat[0, aa] < 0.05 and strat[0, trash] > 0.3


def test_preflop_am_vollen_tisch_bleibt_beim_netz():
    from pokercollector.ai.engine import Hand
    from pokercollector.ai.observation import Action
    a = make_agent("hus?bp=lynx-3-300&iters=10&iters_river=20:hus", 1)
    h = Hand([2000] * 4, 0, 10, 20, seed=2, hand_id="v")
    for _ in range(2):                                  # two fold -> preflop heads-up at 4-player table
        h.apply(h.to_act, Action.fold())
    act = a.act(h.observation(h.to_act))
    assert a.last is None and act.kind in ("fold", "call", "check", "raise")


def _flop_state(board=("Ah", "Kd", "7c"), stacks=(9500, 9500), committed=(500, 500)):
    return State(board=tuple(CARD_INDEX[c] for c in board), committed=committed, bets=(0, 0), stacks=stacks,
                 to_act=0, last_inc=100, raises=0, acted=(False, False), oop=0, bb=100)


def test_flop_baum_zieht_karten_und_teiler_stimmt():
    ' hus-2: from flop on k turn and k river cards are drawn; divisor = (available-4)*k/available.'
    tree = build_tree(_flop_state(), k_turn=5, k_river=4, seed=3)
    chance = np.nonzero(tree.kind == 3)[0]
    assert len(chance) > 0
    turn_nodes = [c for c in chance if tree.n_children[c] == 5]
    river_nodes = [c for c in chance if tree.n_children[c] == 4]
    assert turn_nodes and river_nodes and len(turn_nodes) + len(river_nodes) == len(chance)
    assert all(abs(tree.cdiv[c] - 45 * 5 / 49) < 1e-9 for c in turn_nodes)
    assert all(abs(tree.cdiv[c] - 44 * 4 / 48) < 1e-9 for c in river_nodes)
    assert all(len(b) == 5 for b in tree.boards)
    # full turn tree as before: 48 children, divisor 44
    t4 = build_tree(State(**{**_flop_state().__dict__, "board": tuple(CARD_INDEX[c] for c in ["Ah", "Kd", "7c", "2s"])}))
    assert t4.div == 44.0 and all(abs(t4.cdiv[c] - 44) < 1e-9 for c in np.nonzero(t4.kind == 3)[0])
    # same situation, same seed -> same tree
    t2 = build_tree(_flop_state(), k_turn=5, k_river=4, seed=3)
    assert np.array_equal(tree.card, t2.card)


def test_flop_allin_vor_dem_river_laeuft_bis_zum_showdown():
    ' All-in on flop: chance node turn -> chance node river -> showdown (no showdown on 4 cards).'
    tree = build_tree(_flop_state(stacks=(300, 9500)), k_turn=3, k_river=3, seed=1)
    chance = np.nonzero(tree.kind == 3)[0]
    sd = np.nonzero(tree.kind == 2)[0]
    assert len(sd) > 0 and all(len(tree.boards[tree.board_id[s]]) == 5 for s in sd)
    # each showdown node is attached to a chance node with 5-card boards
    assert all(tree.n_children[c] == 3 for c in chance)


def test_flop_loesung_nullsumme_und_breite_groessen():
    board = ["Ah", "Kd", "7c"]
    r = _uniform(board)
    tree, strat, v, ex1 = solve(_flop_state(), r, r, 12, exploit=True, k_turn=3, k_river=3, seed=5)
    _, strat2, v2, ex2 = solve(_flop_state(), r, r, 60, exploit=True, k_turn=3, k_river=3, seed=5)
    assert abs(float(r @ v2[0]) + float(r @ v2[1])) < 15                # zero sum (except for convergence)
    assert tree.root_actions[0] == ("check", None) and np.allclose(strat.sum(0), 1)
    assert ex2 < ex1 * 0.6                                               # CFR+ also converges in the flop tree
    wide = build_tree(_flop_state(), k_turn=2, k_river=2, preset="wide", seed=5)
    assert len(wide.root_actions) > len(tree.root_actions)       # more bet sizes at the root


def test_agent_mit_flop_spielt_regelkonform():
    a = make_agent("hus?bp=lynx-3-300&iters=8&iters_river=10&iters_flop=6&k_turn=3&k_river=3"
                   "&streets=preflop,flop,turn,river:hus", 2)
    b = make_agent("station", 1)
    flop_searched = []
    orig = a.act

    def act(obs):
        r = orig(obs)
        if a.last is not None and obs.street == "flop":
            flop_searched.append(r)
        return r
    a.act = act
    res = run_match([a, b], 8, seed=4, small_blind=50, big_blind=100, stack_bb=200)
    assert res["config"]["hands_played"] == 16
    assert flop_searched


def test_root_state_reihenfolge_und_totes_geld_am_vollen_tisch():
    ' Review 29.10. B1/B2: button (seat 0) has folded, opponent seat 1 sits before us (seat 3) -> he acts\n    first (oop = opponent); blinds/bets of folded players are dead money in the pot.'
    from pokercollector.ai.husearch import root_state
    from pokercollector.ai.observation import Observation
    n = 6
    obs = Observation(seat=3, num_seats=n, hole_cards=["As", "Kd"], board=["7c", "2d", "Th", "9s"], street="turn",
                      button=0, sb_seat=1, bb_seat=2, big_blind=20, small_blind=10,
                      stacks=[900, 800, 950, 850, 1000, 1000], bets=[0] * n,
                      committed=[60, 150, 20, 150, 0, 60], folded=[True, False, True, False, True, True],
                      allin=[False] * n, in_hand=[True] * n, history=[], to_call=0, can_check=True,
                      can_raise=True, min_raise_to=20, max_raise_to=850, hand_id="x")
    st, opp, path = root_state(obs)
    assert opp == 1 and st.oop == 1 and st.to_act == 1          # opponent (closer to button) first
    assert sum(st.committed) == sum(obs.committed)              # dead money 140 in pot
    assert path == ()
    obs2 = Observation(**{**obs.__dict__, "button": 2})          # button directly in front of us: we act first
    st2, _, _ = root_state(obs2)
    assert st2.oop == 0 and st2.to_act == 0


def test_leaf_option_wird_geparst():
    ' leaf=4: flop subtrees end at turn starts (level 2); only 4 or 5 allowed.'
    import pytest
    from pokercollector.ai.husearch import make_husearch_agent
    a = make_husearch_agent("bp=run:lynx-4@300&leaf=4&streets=turn,river", 1)
    assert a.leaf == 4
    assert make_husearch_agent("bp=run:lynx-4@300&streets=turn,river", 1).leaf == 5
    with pytest.raises(ValueError):
        make_husearch_agent("bp=run:lynx-4@300&leaf=3&streets=turn,river", 1)


def test_leaf4_mit_k_turn_zieht_turncards():
    ' leaf=4 takes all 47 turns except when k_turn is explicitly set (31.10.).'
    from pokercollector.ai.husearch import make_husearch_agent
    a = make_husearch_agent("bp=rock&leaf=4", 0)
    b = make_husearch_agent("bp=rock&leaf=4&k_turn=8", 0)
    assert a.leaf == 4 and not a.k_turn_leaf
    assert b.leaf == 4 and b.k_turn_leaf and b.k_turn == 8


def test_greedy_optionen_der_suche():
    ' bpgreedy=1 switches neural net blueprint to greedy, greedy=1 the search itself (31.10.).'
    from pokercollector.ai.husearch import make_husearch_agent
    a = make_husearch_agent("bp=run:lynx-4@300&bpgreedy=1&greedy=1", 0)
    assert a.bp.greedy and a.greedy
    b = make_husearch_agent("bp=run:lynx-4@300", 0)
    assert not b.bp.greedy and not b.greedy


def test_make_agent_name_hinter_run_doppelpunkt():
    " 31.10.: 'hus?bp=run:<run>@<ckpt>&...:name' - the name is after the last colon,\n    'run:' in the parameter must not be considered a name separator (crash bench_humanopp3 C-5t-bpg)."
    from pokercollector.ai.agents import make_agent
    a = make_agent("hus?bp=run:lynx-4@300&streets=turn,river:kand", 1)
    assert a.name == "kand"
    b = make_agent("hus?bp=run:lynx-4@300&streets=turn,river", 1)
    assert b.name == "hus?bp=run:lynx-4@300&streets=turn,river"
    c = make_agent("nn?run=lynx-4@300&greedy=1:netz", 1)
    assert c.name == "netz"
    assert make_agent("tag:Name", 1).name == "Name"
