"""hus-3: Blattknoten mit Wertnetz. Ein Orakel-Netz (loest den River exakt) muss den vollen Turn-Baum
naeherungsweise reproduzieren; ein Null-Netz macht Blaetter wertlos."""
import numpy as np

from pokercollector.ai.husearch import LEAF, State, build_tree, solve
from pokercollector.ai.ranges import dead_mask
from pokercollector.fastpoker import CARD_INDEX
from pokercollector.poker import FULL_DECK


def _uniform(board):
    r = (~dead_mask(board)).astype(float)
    return r / r.sum()


def _turn_state(board=("Ah", "Kd", "7c", "2s"), stacks=(3000, 3000), committed=(600, 600)):
    return State(board=tuple(CARD_INDEX[c] for c in board), committed=committed, bets=(0, 0), stacks=stacks,
                 to_act=0, last_inc=100, raises=0, acted=(False, False), oop=0, bb=100)


class Oracle:
    """'Wertnetz', das jede Blattsituation exakt loest (langsam, nur fuer den Test)."""

    def __init__(self, iters=40):
        self.iters = iters
        self.calls = 0

    def predict(self, board, pot_bb, stack_bb, oop, r0, r1):
        v0 = np.zeros_like(r0)
        v1 = np.zeros_like(r1)
        for i in range(board.shape[0]):
            cards = tuple(int(c) for c in board[i] if c >= 0)
            pot = int(round(pot_bb[i] * 100))
            stack = int(round(stack_bb[i] * 100))
            st = State(board=cards, committed=(pot // 2, pot - pot // 2), bets=(0, 0), stacks=(stack, stack),
                       to_act=int(oop[i]), last_inc=100, raises=0, acted=(False, False), oop=int(oop[i]), bb=100)
            _, _, v = solve(st, r0[i], r1[i], self.iters)
            v0[i], v1[i] = v[0] / pot, v[1] / pot
            self.calls += 1
        return v0, v1


class Zero:
    def predict(self, board, pot_bb, stack_bb, oop, r0, r1):
        return np.zeros_like(r0), np.zeros_like(r1)


def test_blattbaum_ist_klein_und_blaetter_haben_zustand():
    st = _turn_state()
    full = build_tree(st, k_river=6, seed=2)
    leafy = build_tree(st, k_river=6, seed=2, leaf_street=5)
    n_leaf = int((leafy.kind == LEAF).sum())
    assert n_leaf > 0 and len(leafy.kind) < len(full.kind)
    assert leafy.leaf_pot.shape == (n_leaf,) and leafy.leaf_board.shape == (n_leaf, 5)
    assert np.all(leafy.leaf_board >= 0) and np.all(leafy.leaf_pot >= 1200) and leafy.leaf_oop == 0
    # ohne Netz werden keine Blaetter gebaut
    assert int((build_tree(st, k_river=6, seed=2).kind == LEAF).sum()) == 0


def test_orakel_blaetter_reproduzieren_vollen_baum():
    board = ["Ah", "Kd", "7c", "2s"]
    r = _uniform(board)
    st = _turn_state()
    _, s_full, v_full = solve(st, r, r, 24, k_river=4, seed=7)
    oracle = Oracle(iters=40)
    tree, s_leaf, v_leaf = solve(st, r, r, 24, k_river=4, seed=7, valuenet=oracle, leaf_street=5, leaf_every=6)
    assert oracle.calls > 0
    pot = sum(st.committed)
    ev_full = float(r @ v_full[0]) / pot
    ev_leaf = float(r @ v_leaf[0]) / pot
    assert abs(ev_full - ev_leaf) < 0.15                     # Pot-Einheiten; Orakel selbst nur grob konvergiert
    assert np.allclose(s_leaf.sum(0), 1)
    # Strategien an der Wurzel aehnlich (mittlere absolute Abweichung der Aktionswahrscheinlichkeiten)
    assert np.abs(s_full - s_leaf).mean() < 0.2


def test_null_netz_macht_weiterspielen_wertlos():
    board = ["Ah", "Kd", "7c", "2s"]
    r = _uniform(board)
    st = _turn_state()
    tree, strat, v = solve(st, r, r, 10, k_river=3, seed=1, valuenet=Zero(), leaf_street=5)
    assert int((tree.kind == LEAF).sum()) > 0
    assert abs(float(r @ v[0])) < 0.3 * sum(st.committed)     # alles ausser Fold-Gewinne ist 0
