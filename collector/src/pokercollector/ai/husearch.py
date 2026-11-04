"""Heads-up runtime search: Turn and River are solved anew at every decision (CFR over ranges),
preflop at heads-up table the preflop solver is used (hupreflop.py).

The net (Blueprint) plays the flop (and preflop if more than two players at the table). On the
streets analyzed - heads-up, both still with chips - the bot builds the game tree FROM STREET START to showdown
(small selection of bet sizes, all river cards); the actual bets played on that street are inserted as branches
and the current decision is the node at the end of this path.
Solution is with CFR+ over ALL 1326 hand combos of both players simultaneously:

  Starting distribution   Both players' ranges from history to street start (ranges.py, heads-up params)
  Opponent                the worst-case: CFR finds equilibrium in subgame, no exploitation
  Result                  average strategy at root node for own hand -> action selected

This is "uncertain" re-solving (no guarantee against range errors), but much closer to what
Libratus/DeepStack/ReBeL do, than the old search (search.py) which assumed the opponent plays like us.
Card removal (blockers) is exactly accounted for. Compute core in numba, tree as flat arrays.

Specification: 'hus?bp=<league name or nn-spec without ?>&iters=..&streets=turn,river' (default)
Examples: 'hus?bp=lynx-3-300' or 'hus?bp=run:lynx-3@300'. streets=preflop,... enables the preflop solver
(hupreflop) - Night diagnosis 29/30.10: in tournament format it costs ~25 points, so not default.

ranges=pre,flop (default) | pre | heur: source of ranges at street start. 'pre' = preflop actions
of both players evaluated with the blueprint net (bpranges.py), then heuristic; 'pre,flop' also
flop actions evaluated over all combos (~0.5 s per street; hu480 30.10: +6.0 vs heuristic, -2.5 n.s. vs
net, hus-1 was -29.4); 'heur' = only old heuristic (ranges.py).

hus-2 (29.10): flop can also be solved (streets=preflop,flop,turn,river). Because 49 x 48 follow-up boards
would be too many, random nodes k_turn Turn and k_river River cards are sampled (default 6/6, fixed per
situation); the weight per random node keeps expected value unbiased. Bet sizes as preset
(sizes=narrow|wide). Kernel computes layers in parallel (numba prange); threads=N limits threads per
process (testbench with multiple workers: threads = cores / workers).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from ..fastpoker import CARD_INDEX, njit, prange
from .agents import BaseAgent
from .bpranges import blueprint_ranges
from .observation import Action, Observation
from .ranges import COMBO_HAS, COMBOS, _strengths, dead_mask, opponent_ranges

HUSEARCH_VERSION = "hus-2"
N_COMBOS = len(COMBOS)
DECISION, FOLD, SHOWDOWN, CHANCE, LEAF = 0, 1, 2, 3, 4
LEAF_EVERY = 10                     #Hand values all re-evaluated from the net every so many iterations
AUTO_DEEP_BB = 80                   #auto=1: from this effective stack (BB, Cash) the cash config applies

#Bet sizes (fraction of pot) per (root street, current street) in board cards - more conservative deeper in the tree,
#because every following street occurs with all (or drawn) cards. 'narrow' = hus-1 standard (turn/river).
SIZE_PRESETS = {
    "narrow": {
        (5, 5): {"bet": (0.33, 0.75, 1.5), "raise": (1.0,)},
        (4, 4): {"bet": (0.66,), "raise": ()},
        (4, 5): {"bet": (0.75,), "raise": ()},
        (3, 3): {"bet": (0.5,), "raise": ()},
        (3, 4): {"bet": (0.66,), "raise": ()},
        (3, 5): {"bet": (0.75,), "raise": ()},
    },
    "wide": {
        (5, 5): {"bet": (0.33, 0.66, 1.0, 1.5), "raise": (0.6, 1.2)},
        (4, 4): {"bet": (0.5, 1.0), "raise": (0.8,)},
        (4, 5): {"bet": (0.5, 1.0), "raise": (0.8,)},
        (3, 3): {"bet": (0.33, 0.75), "raise": (0.8,)},
        (3, 4): {"bet": (0.66,), "raise": ()},
        (3, 5): {"bet": (0.75,), "raise": ()},
    },
}
#Backward compatible names (tests, older callers)
SIZES_RIVER = SIZE_PRESETS["narrow"][(5, 5)]
SIZES_TURN = SIZE_PRESETS["narrow"][(4, 4)]
SIZES_RIVER_IN_TURN = SIZE_PRESETS["narrow"][(4, 5)]
#Card sampling at chance nodes: from the flop onwards not all turn/river cards are enumerated (49 x 48 boards
#would be too many), but K cards are drawn per chance node; each drawn card represents (number of possible
#cards / K) cards, expectation stays unbiased. None = all cards (hus-1 standard for the turn).
K_TURN_DEFAULT = 6                  #Turn cards in flop tree
K_RIVER_DEFAULT = 6                 #River cards under a drawn turn card in flop tree
MAX_RAISES = 4                      #per street total (afterwards only fold/call)
SAME_SIZE = 0.04                    #actual size within 4% = existing branch
ALLIN_SNAP = 0.85                   #sizes over 85% of stack -> All-in


@dataclass
class State:
    board: tuple[int, ...]          #card indices
    committed: tuple[int, int]      #total in hand (0 = us, 1 = opponent)
    bets: tuple[int, int]           #this street
    stacks: tuple[int, int]
    to_act: int
    last_inc: int                   #last raise (minimum raise)
    raises: int                     #bets/raises on this street
    acted: tuple[bool, bool]
    oop: int                        #acts first postflop
    bb: int


@dataclass
class Tree:
    kind: np.ndarray
    player: np.ndarray
    first_child: np.ndarray
    n_children: np.ndarray
    util0: np.ndarray               #fold: winning for us
    stake: np.ndarray               #showdown: bet each player
    board_id: np.ndarray
    card: np.ndarray                #card that fell to reach this node (-1 = none)
    root_actions: list              #(type, amount 'raise to') per child of CURRENT node
    boards: list                    #boards (5 cards) for showdown evaluation
    div: float                      # Number of possible river cards per hand pair (full turn tree), otherwise 1
    current: int = 0                # Node of the current decision (end of the actual path)
    cdiv: np.ndarray | None = None  # per chance node: divisor for the expected value over the children
    levels: np.ndarray | None = None  # Limits of tree levels (BFS order): Level k = [levels[k], levels[k+1])
    leaf_ix: np.ndarray | None = None  # per node: index in the leaf list (-1 = no leaf)
    leaf_pot: np.ndarray | None = None  # per leaf: pot (chips)
    leaf_stack: np.ndarray | None = None  # per leaf: effective stack (chips)
    leaf_board: np.ndarray | None = None  # per leaf: board (int8[5], -1 = empty)
    leaf_oop: int = 0
    river_roots: list | None = None   # (node, state) per river start in the full turn tree (valuedata river-leaf)
    turn_roots: list | None = None    # (node, state) per turn start of a flop tree (valuedata turn-leaf)


def _sizes(st: State, root_street: int, preset: str = "narrow") -> dict:
    return SIZE_PRESETS[preset][(root_street, len(st.board))]


def _children(st: State, root_street: int, extra: int | None = None, preset: str = "narrow"):
    """ Abstracted actions: list (type, amount, next state or terminal). extra: actually
    played amount ('raise to'), which is added as its own branch if no size is close enough."""
    p, q = st.to_act, 1 - st.to_act
    to_call = st.bets[q] - st.bets[p]
    pot = sum(st.committed)
    out = []
    if to_call > 0:
        out.append(("fold", None, ("fold", p)))
        call = min(to_call, st.stacks[p])
        out.append(("call", None, _after_call(st, p, call)))
    else:
        out.append(("check", None, _after_check(st, p)))
    can_raise = st.stacks[p] > to_call and st.stacks[q] > 0 and st.raises < MAX_RAISES
    if not can_raise:
        return out
    max_to = st.bets[p] + st.stacks[p]
    cur = st.bets[q]
    min_to = min(max_to, cur + max(st.last_inc, st.bb))
    fracs = _sizes(st, root_street, preset)["raise" if to_call > 0 else "bet"]
    amounts = []
    for f in fracs:
        x = int(round(cur + f * (pot + to_call)))
        x = max(x, min_to)
        if x >= ALLIN_SNAP * max_to + (1 - ALLIN_SNAP) * cur:
            continue
        if x not in amounts:
            amounts.append(x)
    amounts.append(max_to)
    if extra is not None:
        extra = max(min_to, min(max_to, extra))
        if not any(abs(x - extra) <= SAME_SIZE * x for x in amounts):
            amounts.append(extra)
            amounts.sort()
    for x in amounts:
        out.append(("raise", x, _after_raise(st, p, x)))
    return out


def _after_check(st: State, p: int):
    acted = list(st.acted)
    acted[p] = True
    if acted[1 - p]:
        return _street_end(st)
    return replace(st, to_act=1 - p, acted=tuple(acted))


def _after_call(st: State, p: int, call: int):
    st = _put(st, p, call)
    return _street_end(st)


def _after_raise(st: State, p: int, to: int):
    inc = to - st.bets[1 - p]
    st = _put(st, p, to - st.bets[p])
    acted = [False, False]
    acted[p] = True
    return replace(st, to_act=1 - p, last_inc=max(inc, st.bb), raises=st.raises + 1, acted=tuple(acted))


def _put(st: State, p: int, x: int) -> State:
    c, b, s = list(st.committed), list(st.bets), list(st.stacks)
    c[p] += x
    b[p] += x
    s[p] -= x
    return replace(st, committed=tuple(c), bets=tuple(b), stacks=tuple(s))


def _street_end(st: State):
    if len(st.board) == 5:
        return ("showdown", min(st.committed))
    return ("chance", replace(st, bets=(0, 0), to_act=st.oop, last_inc=st.bb, raises=0, acted=(False, False)))


def _matches(label: str, amt, step: tuple[str, int | None]) -> bool:
    kind, x = step
    if kind in ("check", "call"):
        return label == kind
    return label == "raise" and abs(amt - x) <= SAME_SIZE * max(amt, x)


def chance_cards(board: tuple[int, ...], k: int | None, rng) -> list[int]:
    """ Cards for a chance node: all not on the board (k None) or k of them drawn."""
    avail = [c for c in range(52) if c not in board]
    if k is None or k >= len(avail):
        return avail
    pick = rng.choice(len(avail), size=k, replace=False)
    return sorted(avail[i] for i in pick)


def build_tree(root: State, path: tuple = (), k_turn: int | None = None, k_river: int | None = None,
               preset: str = "narrow", seed: int = 0, leaf_street: int | None = None) -> Tree:
    """ Build tree breadth-first: children of a node are contiguous, parents before children.
    path: actual street actions since root ((type, amount to) per step) - their sizes
    appear as branches in the tree, the node after is the current decision.
    k_turn/k_river: number of cards drawn at chance nodes (None = all); the divisor per chance node is
    chosen so that the expected value per hand pair remains unbiased (drawn card represents
    available/K cards, each of which has probability 1/(available - 4) for a fixed hand pair)."""
    root_street = len(root.board)
    kind, player, first, nch, util0, stake, bid, card = [], [], [], [], [], [], [], []
    cdiv: list[float] = []
    leaf_ix: list[int] = []
    leaves: list[State] = []            # State at the start of the leaf street (card already dealt)
    boards: list[tuple[int, ...]] = []
    board_ix: dict[tuple[int, ...], int] = {}
    root_actions = []
    river_roots: list[tuple[int, State]] = []
    turn_roots: list[tuple[int, State]] = []
    current = -1
    rng = np.random.default_rng(seed)

    def new(k, pl=-1, u=0.0, sk=0.0, b=-1, c=-1):
        kind.append(k), player.append(pl), first.append(-1), nch.append(0)
        util0.append(u), stake.append(sk), bid.append(b), card.append(c), cdiv.append(1.0), leaf_ix.append(-1)
        return len(kind) - 1

    def board_id(board):
        if board not in board_ix:
            board_ix[board] = len(boards)
            boards.append(board)
        return board_ix[board]

    queue = [(new(DECISION, root.to_act), root, 0)]
    qi = 0
    while qi < len(queue):
        n, st, depth = queue[qi]
        qi += 1
        if kind[n] == CHANCE:
            k = k_turn if len(st.board) == 3 else k_river
            cards = chance_cards(st.board, k, rng)
            avail = 52 - len(st.board)
            cdiv[n] = (avail - 4) * len(cards) / avail       # full turn tree: 44 * 48 / 48 = 44
            kids = []
            for c in cards:
                child_st = replace(st, board=st.board + (c,))
                if min(child_st.stacks) == 0:                 # all-in: showdown, possibly one more card before
                    if len(child_st.board) == 5:
                        kids.append((SHOWDOWN, None, min(st.committed), board_id(child_st.board), c))
                    else:
                        kids.append((CHANCE, child_st, 0.0, -1, c))
                elif leaf_street is not None and len(child_st.board) == leaf_street:
                    kids.append((LEAF, child_st, 0.0, -1, c))     # Valuenet evaluates from here
                else:
                    kids.append((DECISION, child_st, 0.0, -1, c))
            first[n] = len(kind)
            nch[n] = len(kids)
            for k, child_st, sk, b, c in kids:
                m = new(k, child_st.to_act if k == DECISION else -1, sk=sk, b=b, c=c)
                if k == LEAF:
                    leaf_ix[m] = len(leaves)
                    leaves.append(child_st)
                elif k != SHOWDOWN:
                    if k == DECISION and len(child_st.board) == 5:
                        river_roots.append((m, child_st))
                    elif k == DECISION and len(child_st.board) == 4:
                        turn_roots.append((m, child_st))
                    queue.append((m, child_st, -1))
            continue
        step = path[depth] if 0 <= depth < len(path) else None
        acts = _children(st, root_street, step[1] if step and step[0] == "raise" else None, preset)
        first[n] = len(kind)
        nch[n] = len(acts)
        if depth == len(path):
            current = n
            root_actions = [(label, amt) for label, amt, _ in acts]
        nxt = -1
        if step is not None:
            cands = [i for i, (label, amt, _) in enumerate(acts) if _matches(label, amt, step)]
            if not cands:
                raise ValueError(f"Action {step} does not fit in tree")
            nxt = min(cands, key=lambda i: abs((acts[i][1] or 0) - (step[1] or 0)))
        pending = []
        for i, (label, amt, res) in enumerate(acts):
            d = depth + 1 if i == nxt else -1
            if isinstance(res, tuple) and res[0] == "fold":
                p = res[1]
                m = new(FOLD, p, u=float(-st.committed[0] if p == 0 else st.committed[1]))
            elif isinstance(res, tuple) and res[0] == "showdown":
                m = new(SHOWDOWN, sk=float(res[1]), b=board_id(st.board))
            elif isinstance(res, tuple) and res[0] == "chance":
                m = new(CHANCE)
                pending.append((m, res[1], -1))
            else:
                m = new(DECISION, res.to_act)
                pending.append((m, res, d))
        queue.extend(pending)
    if current < 0:
        raise ValueError('Current decision not in tree')
    a = lambda x, t: np.asarray(x, t)
    div = 44.0 if root_street == 4 and k_river is None else 1.0
    lb = np.full((len(leaves), 5), -1, np.int8)
    for i, ls in enumerate(leaves):
        lb[i, :len(ls.board)] = ls.board
    return Tree(a(kind, np.int64), a(player, np.int64), a(first, np.int64), a(nch, np.int64),
                a(util0, np.float64), a(stake, np.float64), a(bid, np.int64), a(card, np.int64),
                root_actions, boards, div, current, a(cdiv, np.float64), tree_levels(a(first, np.int64), a(nch, np.int64)),
                a(leaf_ix, np.int64), a([float(sum(ls.committed)) for ls in leaves], np.float64),
                a([float(min(ls.stacks)) for ls in leaves], np.float64), lb, root.oop, river_roots, turn_roots)


def average_reaches(tree: Tree, avg: np.ndarray, r0: np.ndarray, r1: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """ Reach (= unnormalized range) of both players at EVERY node under the average strategy avg
    (edge weights as in solve/_best_response), chance cards block matching hands.
    This allows reading out actual ranges at street starts (valuedata 'river-leaf')."""
    n = len(tree.kind)
    R = np.zeros((2, n, N_COMBOS))
    R[0, 0], R[1, 0] = r0, r1
    for node in range(n):
        f, m = int(tree.first_child[node]), int(tree.n_children[node])
        if m <= 0:
            continue
        k = tree.kind[node]
        if k == DECISION:
            p = int(tree.player[node])
            a = avg[f:f + m].astype(np.float64)
            s = a.sum(0)
            strat = np.where(s > 0, a / np.where(s > 0, s, 1.0), 1.0 / m)
            R[p, f:f + m] = R[p, node][None, :] * strat
            R[1 - p, f:f + m] = R[1 - p, node][None, :]
        elif k == CHANCE:
            for c in range(f, f + m):
                R[:, c] = R[:, node] * ~COMBO_HAS[tree.card[c]]
    return R[0], R[1]


def tree_levels(first: np.ndarray, nch: np.ndarray) -> np.ndarray:
    """ Level boundaries: the tree is built breadth-first, children are after all nodes of their parent level.
    Within a level, nodes are independent (disjoint children) -> can be processed in parallel."""
    n = len(first)
    depth = np.zeros(n, np.int64)
    for i in range(n):
        if nch[i] > 0:
            depth[first[i]:first[i] + nch[i]] = depth[i] + 1
    assert np.all(np.diff(depth) >= 0), 'Tree not level-ordered'
    bounds = [0] + [i for i in range(1, n) if depth[i] != depth[i - 1]] + [n]
    return np.asarray(bounds, np.int64)


def board_tables(boards: list[tuple[int, ...]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ Per board: hand values of all combinations (-1 = blocked) and ascending order of valid ones."""
    vals = np.empty((len(boards), N_COMBOS), np.int64)
    order = np.zeros((len(boards), N_COMBOS), np.int64)
    nvalid = np.zeros(len(boards), np.int64)
    for i, b in enumerate(boards):
        v = _strengths(COMBOS, np.array(b, np.int64), len(b))
        vals[i] = v
        ok = np.nonzero(v >= 0)[0]
        o = ok[np.argsort(v[ok], kind="stable")]
        order[i, :len(o)] = o
        nvalid[i] = len(o)
    return vals, order, nvalid


@njit(cache=True, nogil=True)
def _fold_sums(r, combos, out):
    """ out[h] = sum of opponent reach over combinations without common card with h."""
    per = np.zeros(52)
    tot = 0.0
    for o in range(r.shape[0]):
        per[combos[o, 0]] += r[o]
        per[combos[o, 1]] += r[o]
        tot += r[o]
    for h in range(r.shape[0]):
        out[h] = tot - per[combos[h, 0]] - per[combos[h, 1]] + r[h]


@njit(cache=True, nogil=True)
def _showdown(r, vals, order, nvalid, combos, out):
    """ out[h] = reach of opponent hands that h beats minus those that beat h (no blockers)."""
    for h in range(out.shape[0]):
        out[h] = 0.0
    per = np.zeros(52)
    tot = 0.0
    i = 0
    while i < nvalid:                 # upwards: winning against weaker hands
        j = i
        while j < nvalid and vals[order[j]] == vals[order[i]]:
            j += 1
        for k in range(i, j):
            h = order[k]
            out[h] += tot - per[combos[h, 0]] - per[combos[h, 1]]
        for k in range(i, j):
            o = order[k]
            per[combos[o, 0]] += r[o]
            per[combos[o, 1]] += r[o]
            tot += r[o]
        i = j
    per[:] = 0.0
    tot = 0.0
    i = nvalid - 1
    while i >= 0:                     # downwards: losing against stronger hands
        j = i
        while j >= 0 and vals[order[j]] == vals[order[i]]:
            j -= 1
        for k in range(j + 1, i + 1):
            h = order[k]
            out[h] -= tot - per[combos[h, 0]] - per[combos[h, 1]]
        for k in range(j + 1, i + 1):
            o = order[k]
            per[combos[o, 0]] += r[o]
            per[combos[o, 1]] += r[o]
            tot += r[o]
        i = j


@njit(cache=True, nogil=True, parallel=True)
def _solve(kind, player, first, nch, util0, stake, bid, card, vals, order, nvalid, combos, has,
           r0, r1, t_start, t_end, cdiv, gamma, levels, leaf_ix, leafval, regret, reach, val, avg, own, root_val):
    """ CFR+ over all hand combinations, iterations t_start..t_end-1 on the passed state (regret, avg
    etc. remain between calls so that leaf values can be re-evaluated in between).
    Level-wise: nodes of a tree level have disjoint children and are processed in parallel.
    Leaf (LEAF): val[n,h] = leafval[leaf, upd, h] * sum of opponent reach at the leaf (net value per unit
    of opponent mass, in chips)."""
    H = r0.shape[0]
    n_lev = levels.shape[0] - 1
    for t in range(t_start, t_end):
        for upd in range(2):              # alternating: first player 0, then 1 (CFR+)
            q = 1 - upd
            wt = float(t) ** gamma
            for h in range(H):
                reach[0, h] = r1[h] if q == 1 else r0[h]
                own[0, h] = r0[h] if upd == 0 else r1[h]
            for L in range(n_lev):
                for n in prange(levels[L], levels[L + 1]):
                    k = kind[n]
                    if k == DECISION:
                        p = player[n]
                        f, m = first[n], nch[n]
                        for h in range(H):
                            s = 0.0
                            for c in range(f, f + m):
                                if regret[c, h] > 0:
                                    s += regret[c, h]
                            for c in range(f, f + m):
                                if s > 0:
                                    sg = max(regret[c, h], 0.0) / s
                                else:
                                    sg = 1.0 / m
                                if p == q:
                                    reach[c, h] = reach[n, h] * sg
                                    own[c, h] = own[n, h]
                                else:
                                    reach[c, h] = reach[n, h]
                                    own[c, h] = own[n, h] * sg
                                    avg[c, h] += wt * own[n, h] * sg
                    elif k == CHANCE:
                        for c in range(first[n], first[n] + nch[n]):
                            cd = card[c]
                            for h in range(H):
                                reach[c, h] = 0.0 if has[cd, h] else reach[n, h]
                                own[c, h] = 0.0 if has[cd, h] else own[n, h]
            for L in range(n_lev - 1, -1, -1):
                for n in prange(levels[L], levels[L + 1]):
                    k = kind[n]
                    if k == FOLD:
                        _fold_sums(reach[n], combos, val[n])
                        u = util0[n] if upd == 0 else -util0[n]
                        for h in range(H):
                            val[n, h] *= u
                    elif k == SHOWDOWN:
                        b = bid[n]
                        _showdown(reach[n], vals[b], order[b], nvalid[b], combos, val[n])
                        sk = stake[n]
                        for h in range(H):
                            val[n, h] *= sk
                    elif k == CHANCE:
                        dv = cdiv[n]
                        for h in range(H):
                            val[n, h] = 0.0
                        for c in range(first[n], first[n] + nch[n]):
                            cd = card[c]
                            for h in range(H):
                                if not has[cd, h]:
                                    val[n, h] += val[c, h] / dv
                    elif k == LEAF:
                        li = leaf_ix[n]
                        S = 0.0
                        for h in range(H):
                            S += reach[n, h]
                        for h in range(H):
                            val[n, h] = leafval[li, upd, h] * S
                    else:
                        p = player[n]
                        f, m = first[n], nch[n]
                        if p == upd:
                            for h in range(H):
                                # strategy as in the forward pass: from the regrets BEFORE updating this node
                                s = 0.0
                                for c in range(f, f + m):
                                    if regret[c, h] > 0:
                                        s += regret[c, h]
                                v = 0.0
                                for c in range(f, f + m):
                                    sg = (max(regret[c, h], 0.0) / s) if s > 0 else 1.0 / m
                                    v += sg * val[c, h]
                                val[n, h] = v
                                for c in range(f, f + m):
                                    x = regret[c, h] + val[c, h] - v
                                    regret[c, h] = x if x > 0 else 0.0      # CFR+
                        else:
                            for h in range(H):
                                v = 0.0
                                for c in range(f, f + m):
                                    v += val[c, h]
                                val[n, h] = v
            for h in range(H):
                root_val[upd, h] = val[0, h]
    return avg, root_val


@njit(cache=True, nogil=True)
def _solve_small(kind, player, first, nch, util0, stake, bid, card, vals, order, nvalid, combos, has,
           r0, r1, t_start, t_end, cdiv, gamma, levels, leaf_ix, leafval, regret, reach, val, avg, own, root_val):
    """CFR+ over all hand combinations, iterations t_start..t_end-1 on the passed state (regret, avg
    etc. remain between calls so that leaf values can be re-evaluated in between).
    Level-wise: nodes of a tree level have disjoint children and are processed in parallel.
    Leaf (LEAF): val[n,h] = leafval[leaf, upd, h] * sum of opponent reach at the leaf (net value per unit
    of opponent mass, in chips)."""
    H = r0.shape[0]
    n_lev = levels.shape[0] - 1
    for t in range(t_start, t_end):
        for upd in range(2):              # alternating: first player 0, then 1 (CFR+)
            q = 1 - upd
            wt = float(t) ** gamma
            for h in range(H):
                reach[0, h] = r1[h] if q == 1 else r0[h]
                own[0, h] = r0[h] if upd == 0 else r1[h]
            for L in range(n_lev):
                for n in range(levels[L], levels[L + 1]):
                    k = kind[n]
                    if k == DECISION:
                        p = player[n]
                        f, m = first[n], nch[n]
                        for h in range(H):
                            s = 0.0
                            for c in range(f, f + m):
                                if regret[c, h] > 0:
                                    s += regret[c, h]
                            for c in range(f, f + m):
                                if s > 0:
                                    sg = max(regret[c, h], 0.0) / s
                                else:
                                    sg = 1.0 / m
                                if p == q:
                                    reach[c, h] = reach[n, h] * sg
                                    own[c, h] = own[n, h]
                                else:
                                    reach[c, h] = reach[n, h]
                                    own[c, h] = own[n, h] * sg
                                    avg[c, h] += wt * own[n, h] * sg
                    elif k == CHANCE:
                        for c in range(first[n], first[n] + nch[n]):
                            cd = card[c]
                            for h in range(H):
                                reach[c, h] = 0.0 if has[cd, h] else reach[n, h]
                                own[c, h] = 0.0 if has[cd, h] else own[n, h]
            for L in range(n_lev - 1, -1, -1):
                for n in range(levels[L], levels[L + 1]):
                    k = kind[n]
                    if k == FOLD:
                        _fold_sums(reach[n], combos, val[n])
                        u = util0[n] if upd == 0 else -util0[n]
                        for h in range(H):
                            val[n, h] *= u
                    elif k == SHOWDOWN:
                        b = bid[n]
                        _showdown(reach[n], vals[b], order[b], nvalid[b], combos, val[n])
                        sk = stake[n]
                        for h in range(H):
                            val[n, h] *= sk
                    elif k == CHANCE:
                        dv = cdiv[n]
                        for h in range(H):
                            val[n, h] = 0.0
                        for c in range(first[n], first[n] + nch[n]):
                            cd = card[c]
                            for h in range(H):
                                if not has[cd, h]:
                                    val[n, h] += val[c, h] / dv
                    elif k == LEAF:
                        li = leaf_ix[n]
                        S = 0.0
                        for h in range(H):
                            S += reach[n, h]
                        for h in range(H):
                            val[n, h] = leafval[li, upd, h] * S
                    else:
                        p = player[n]
                        f, m = first[n], nch[n]
                        if p == upd:
                            for h in range(H):
                                # strategy as in the forward pass: from the regrets BEFORE updating this node
                                s = 0.0
                                for c in range(f, f + m):
                                    if regret[c, h] > 0:
                                        s += regret[c, h]
                                v = 0.0
                                for c in range(f, f + m):
                                    sg = (max(regret[c, h], 0.0) / s) if s > 0 else 1.0 / m
                                    v += sg * val[c, h]
                                val[n, h] = v
                                for c in range(f, f + m):
                                    x = regret[c, h] + val[c, h] - v
                                    regret[c, h] = x if x > 0 else 0.0      # CFR+
                        else:
                            for h in range(H):
                                v = 0.0
                                for c in range(f, f + m):
                                    v += val[c, h]
                                val[n, h] = v
            for h in range(H):
                root_val[upd, h] = val[0, h]
    return avg, root_val


PARALLEL_MIN_NODES = 256            # measured under load: 357 nodes x 100 iterations parallel 0.9 s, serial 1.75 s
                                    # as it delivers (357 nodes x 100 iterations: 0.8 s parallel, significantly less serial)


def _solve_any(*args):
    kind = args[0]
    return (_solve if kind.shape[0] >= PARALLEL_MIN_NODES else _solve_small)(*args)


@njit(cache=True, nogil=True)
def _best_response(kind, player, first, nch, util0, stake, bid, card, vals, order, nvalid, combos, has,
                   r0, r1, cdiv, avg, b):
    """ Value of the best response of player b to the average strategy of the other
    (sum over b’s hands, weighted by b’s range)."""
    n_nodes = kind.shape[0]
    H = r0.shape[0]
    q = 1 - b
    reach = np.zeros((n_nodes, H))
    val = np.zeros((n_nodes, H))
    tmp = np.zeros(H)
    rr = np.zeros(H)
    for h in range(H):
        reach[0, h] = r1[h] if q == 1 else r0[h]
    for n in range(n_nodes):
        k = kind[n]
        if k == DECISION:
            f, m = first[n], nch[n]
            for h in range(H):
                if player[n] == q:
                    s = 0.0
                    for c in range(f, f + m):
                        s += avg[c, h]
                    for c in range(f, f + m):
                        reach[c, h] = reach[n, h] * (avg[c, h] / s if s > 0 else 1.0 / m)
                else:
                    for c in range(f, f + m):
                        reach[c, h] = reach[n, h]
        elif k == CHANCE:
            for c in range(first[n], first[n] + nch[n]):
                for h in range(H):
                    reach[c, h] = 0.0 if has[card[c], h] else reach[n, h]
    for n in range(n_nodes - 1, -1, -1):
        k = kind[n]
        if k == FOLD:
            for h in range(H):
                rr[h] = reach[n, h]
            _fold_sums(rr, combos, tmp)
            u = util0[n] if b == 0 else -util0[n]
            for h in range(H):
                val[n, h] = u * tmp[h]
        elif k == SHOWDOWN:
            for h in range(H):
                rr[h] = reach[n, h]
            _showdown(rr, vals[bid[n]], order[bid[n]], nvalid[bid[n]], combos, tmp)
            for h in range(H):
                val[n, h] = stake[n] * tmp[h]
        elif k == CHANCE:
            dv = cdiv[n]
            for c in range(first[n], first[n] + nch[n]):
                for h in range(H):
                    if not has[card[c], h]:
                        val[n, h] += val[c, h] / dv
        else:
            f, m = first[n], nch[n]
            for h in range(H):
                if player[n] == b:
                    best = -1e30
                    for c in range(f, f + m):
                        if val[c, h] > best:
                            best = val[c, h]
                    val[n, h] = best
                else:
                    v = 0.0
                    for c in range(f, f + m):
                        v += val[c, h]
                    val[n, h] = v
    tot = 0.0
    for h in range(H):
        tot += (r0[h] if b == 0 else r1[h]) * val[0, h]
    return tot


GAMMA = 2.0                         # Average strategy: iteration t counts as t^GAMMA (later, better counts more)


def leaf_values(tree: Tree, valuenet, reach: np.ndarray, own: np.ndarray, bb: int) -> np.ndarray:
    """ Leaf values from the valuenet: per leaf the (normalized) ranges of both players from current reaches,
    output leafval[leaf, player, hand] in chips per unit opponent mass. After a full iteration (upd=1
    last) reach = reach of player 0 and own = reach of player 1."""
    idx = np.nonzero(tree.leaf_ix >= 0)[0]
    n = len(idx)
    out = np.zeros((max(n, 1), 2, N_COMBOS), np.float32)
    if n == 0:
        return out
    r0 = reach[idx].astype(np.float64)
    r1 = own[idx].astype(np.float64)
    s0, s1 = r0.sum(1, keepdims=True), r1.sum(1, keepdims=True)
    ok = (s0[:, 0] > 1e-12) & (s1[:, 0] > 1e-12)
    if ok.any():
        li = tree.leaf_ix[idx[ok]]
        r0n = r0[ok] / s0[ok]
        r1n = r1[ok] / s1[ok]
        v0, v1 = valuenet.predict(tree.leaf_board[li], tree.leaf_pot[li] / bb, tree.leaf_stack[li] / bb,
                                  np.full(len(li), tree.leaf_oop), r0n, r1n)
        pot = tree.leaf_pot[li][:, None]
        out[li, 0] = (v0 * pot).astype(np.float32)
        out[li, 1] = (v1 * pot).astype(np.float32)
    return out


def solve(root: State, r0: np.ndarray, r1: np.ndarray, iters: int = 200, exploit: bool = False,
          gamma: float = GAMMA, path: tuple = (), k_turn: int | None = None, k_river: int | None = None,
          preset: str = "narrow", seed: int = 0, valuenet=None, leaf_street: int | None = None,
          leaf_every: int = LEAF_EVERY, return_avg: bool = False):
    """ Solves the subgame from root. Returns: tree, average strategy at current node (end of
    path; actions x 1326), values at root; with exploit=True additionally exploitability in chips
    ((BR0 + BR1) / 2, zero at equilibrium). k_turn/k_river/preset/seed: see build_tree.
    valuenet + leaf_street: subtrees from start of this street (card count, e.g. 5 = river) are replaced by
    net values which are re-evaluated every leaf_every iterations from current ranges."""
    tree = build_tree(root, path, k_turn, k_river, preset, seed, leaf_street if valuenet is not None else None)
    vals, order, nvalid = board_tables(tree.boards) if tree.boards else (
        np.zeros((1, N_COMBOS), np.int64), np.zeros((1, N_COMBOS), np.int64), np.zeros(1, np.int64))
    args = (tree.kind, tree.player, tree.first_child, tree.n_children, tree.util0, tree.stake,
            tree.board_id, tree.card, vals, order, nvalid, COMBOS, COMBO_HAS,
            r0.astype(np.float64), r1.astype(np.float64))
    n_nodes, H = len(tree.kind), N_COMBOS
    regret = np.zeros((n_nodes, H), np.float32)       # per edge (child node), for the acting player at the parent node
    reach = np.zeros((n_nodes, H), np.float32)        # Reach of the OPPONENT of the currently updated player
    val = np.zeros((n_nodes, H), np.float32)          # counterfactual values of the updated player
    avg = np.zeros((n_nodes, H), np.float32)          # sum weight * own reach * strategy (per edge)
    own = np.zeros((n_nodes, H), np.float32)          # own reach of the updated player
    root_val = np.zeros((2, H))
    n_leaves = int((tree.leaf_ix >= 0).sum())
    leafval = np.zeros((max(n_leaves, 1), 2, H), np.float32)
    state = (regret, reach, val, avg, own, root_val)
    if n_leaves == 0:
        avg, v = _solve_any(*args, 1, iters + 1, tree.cdiv, gamma, tree.levels, tree.leaf_ix, leafval, *state)
    else:
        if exploit:
            raise ValueError('Exploitability with value network leaves not defined')
        # first iteration with leaf value 0 yields the reaches of the uniform strategy, then evaluate
        t = 1
        while t <= iters:
            t_end = min(iters + 1, t + leaf_every)
            if t == 1:
                _solve_any(*args, 1, 2, tree.cdiv, gamma, tree.levels, tree.leaf_ix, leafval, *state)
                leafval[:] = leaf_values(tree, valuenet, reach, own, root.bb)
                # reset state: the zero-leaf iteration should not count into regrets/average
                regret[:] = 0.0
                avg[:] = 0.0
            avg, v = _solve_any(*args, t, t_end, tree.cdiv, gamma, tree.levels, tree.leaf_ix, leafval, *state)
            leafval[:] = leaf_values(tree, valuenet, reach, own, root.bb)
            t = t_end
    f, m = tree.first_child[tree.current], tree.n_children[tree.current]
    ra = avg[f:f + m].astype(np.float64)
    s = ra.sum(0)
    strat = np.where(s > 0, ra / np.where(s > 0, s, 1), 1.0 / m)
    if return_avg:
        return tree, strat, v, avg
    if not exploit:
        return tree, strat, v
    br = [_best_response(*args, tree.cdiv, avg, b) for b in (0, 1)]
    return tree, strat, v, (br[0] + br[1]) / 2


# --- Ranges heads-up -------------------------------------------------------------------------------

def public_ranges(obs: Observation, hero: int, opp: int) -> tuple[np.ndarray, np.ndarray]:
    """ Ranges of both players at BEGINNING of the current street, only from public information - the
    own as the opponent sees it. What happens on this street is determined in the tree itself
    from equilibrium (who raises here has with what the equilibrium raises). Blockers of own
    cards are accounted for by the solver."""
    pub = replace(obs, hole_cards=[], history=[a for a in obs.history if a.street != obs.street])
    hu = sum(obs.in_hand) == 2          # Table heads-up started (otherwise: pot only became heads-up)
    r_opp = opponent_ranges(replace(pub, seat=hero), heads_up=hu)[opp]
    r_hero = opponent_ranges(replace(pub, seat=opp), heads_up=hu)[hero]
    return r_hero, r_opp


def root_state(obs: Observation) -> tuple[State, int, tuple]:
    """ State at the start of the current street (0 = us, 1 = opponent) and actions since then."""
    hero = obs.seat
    live = [s for s in range(obs.num_seats) if obs.in_hand[s] and not obs.folded[s]]
    opp = next(s for s in live if s != hero)
    idx = {hero: 0, opp: 1}
    # Who acts postflop first? The first of the two left of the button (engine._next) - at a full table the
    # opponent can also be that, even though we do not have the button
    order = [(obs.button + k) % obs.num_seats for k in range(1, obs.num_seats + 1)]
    first = next(s for s in order if s in (hero, opp))
    oop = 0 if first == hero else 1
    # dead money of folded players (blinds, limps, 3-bet-folds) belongs in the pot: split evenly assigned
    # (constant shift, equilibrium unchanged, showdown/fold utilities match automatically)
    dead = int(sum(obs.committed) - obs.committed[hero] - obs.committed[opp])
    st = State(board=tuple(CARD_INDEX[c] for c in obs.board),
               committed=(obs.committed[hero] - obs.bets[hero] + dead // 2,
                          obs.committed[opp] - obs.bets[opp] + dead - dead // 2), bets=(0, 0),
               stacks=(obs.stacks[hero] + obs.bets[hero], obs.stacks[opp] + obs.bets[opp]), to_act=oop,
               last_inc=obs.big_blind, raises=0, acted=(False, False), oop=oop, bb=obs.big_blind)
    path = []
    for a in obs.street_actions():
        if a.seat not in idx or a.kind in ("post_sb", "post_bb"):
            continue
        if a.kind in ("check", "call"):
            path.append((a.kind, None))
        elif a.kind in ("bet", "raise"):
            path.append(("raise", int(a.amount_to or 0)))
    return st, opp, tuple(path)


def hand_index(cards: list[str]) -> int:
    a, b = sorted(CARD_INDEX[c] for c in cards)
    return int(np.nonzero((COMBOS[:, 0] == a) & (COMBOS[:, 1] == b))[0][0])


class HUSearchAgent(BaseAgent):
    """ Blueprint net where no search is done; heads-up re-solving by CFR on chosen streets
    (flop with drawn turn/river cards, turn with all river cards, river exactly)."""
    name = "hus"

    def __init__(self, blueprint: BaseAgent, iters_turn: int = 120, iters_river: int = 300,
                 streets: tuple[str, ...] = ("turn", "river"), seed: int = 0, iters_flop: int = 40,
                 k_turn: int = K_TURN_DEFAULT, k_river: int = K_RIVER_DEFAULT, preset: str = "narrow",
                 threads: int | None = None, k_river_turn: int | None = None, valuenet=None,
                 bp_streets: tuple[str, ...] | None = ("preflop",), opp_weights: dict | None = None,
                 auto: bool = False, opp_fold=None, leaf: int = 5, k_turn_leaf: bool = False, greedy: bool = False):
        super().__init__(seed)
        self.bp = blueprint
        self.bp_streets = bp_streets        # Streets whose actions translate blueprint into ranges (None = heuristic)
        self.opp_weights = opp_weights      # Opponent model (e.g. human network human-1) for opponent ranges
        self.opp_fold = opp_fold            # Fold model (humanfold.HumanFold): continuation factor per hand before each opponent action
        self.auto = auto                    # Choose hand format: tournament/short -> turn,river + pre,flop; deep -> + preflop solver, eq,flop
        self.iters = {"flop": iters_flop, "turn": iters_turn, "river": iters_river}
        self.streets = streets
        self.k_turn, self.k_river, self.preset = k_turn, k_river, preset
        self.threads = threads
        self.k_river_turn = k_river_turn    # River cards in the turn tree (None = all 48, exact)
        self.valuenet = valuenet            # Valuenet: River subtrees become leaves (hus-3)
        self.leaf = leaf                    # Street (card count): 5 = River beginnings; 4 = Turn beginnings (level 2, requires Turn network)
        self.greedy = greedy                # Search: most likely action from the mixed strategy instead of fold (31.10.)
        self.k_turn_leaf = k_turn_leaf      # leaf=4: still draw Turn cards (k_turn), instead of taking all 47 (31.10.: 8 drawn ~ same time as 6x6, closer to reference)
        self.last = None

    def hand_over(self, rec, seat):
        if hasattr(self.bp, "hand_over"):
            self.bp.hand_over(rec, seat)

    def applies(self, obs: Observation) -> bool:
        live = [s for s in range(obs.num_seats) if obs.in_hand[s] and not obs.folded[s]]
        return (obs.street in self.streets and obs.street in self.iters and len(live) == 2 and len(obs.hole_cards) == 2
                and not any(obs.allin[s] for s in live) and obs.stacks[obs.seat] > 0)

    def preflop(self, obs: Observation) -> Action | None:
        """ Heads-up table preflop: equilibrium from hupreflop (None = not applicable)."""
        from .hupreflop import decide
        if obs.street != "preflop" or sum(obs.in_hand) != 2 or len(obs.hole_cards) != 2 or obs.stacks[obs.seat] <= 0:
            return None
        out = decide(obs, self.rng(obs))
        if out is None:
            return None
        (kind, x), labels, p = out
        bb = obs.big_blind or 1
        self.last = {"actions": [(k, None if k != "raise" else int(round(v * bb))) for k, v in labels],
                     "probs": p, "nodes": 0}
        if kind == "fold":
            return Action.fold()
        if kind in ("check", "call"):
            return Action.check() if obs.can_check else Action.call()
        amt = int(round(x * bb))
        if obs.max_raise_to is not None and amt >= obs.max_raise_to - bb / 2:
            amt = obs.max_raise_to
        return Action.raise_to(amt)

    def choose_format(self, obs: Observation) -> None:
        """ auto: deep cash (no tournament, effective stack >= 80 BB) -> Preflop solver + equilibrium ranges
        (Slumbot hus-5: +-0 instead of -39); otherwise tournament configuration (hu480: network ranges, no preflop solver)."""
        from .hupreflop import effective_stack_bb
        deep = obs.tournament is None and sum(obs.in_hand) == 2 and effective_stack_bb(obs) >= AUTO_DEEP_BB
        if deep:
            self.streets = ("preflop", "turn", "river")
            self.bp_streets = ("eq", "flop")
        else:
            self.streets = ("turn", "river")
            self.bp_streets = ("preflop", "flop")

    def act(self, obs: Observation) -> Action:
        self.last = None
        if self.auto:
            self.choose_format(obs)
        if "preflop" in self.streets:
            a = self.preflop(obs)
            if a is not None:
                return a
        if not self.applies(obs):
            return self.bp.act(obs)
        if self.threads:
            set_threads(self.threads)
        st, opp, path = root_state(obs)
        rr = blueprint_ranges(obs, obs.seat, opp, self.bp, self.bp_streets, self.opp_weights, self.opp_fold) \
            if self.bp_streets else None
        source = "bp" if rr is not None else "heur"
        r_hero, r_opp = rr if rr is not None else public_ranges(obs, obs.seat, opp)
        h = hand_index(obs.hole_cards)
        r_hero = r_hero.copy()
        r_hero[h] = max(r_hero[h], 1e-4)            # never completely exclude own hand
        r_opp = r_opp * ~dead_mask(obs.hole_cards)
        if r_opp.sum() <= 0:
            return self.bp.act(obs)
        # Flop: draw Turn and River cards (fixed per situation, so the same situation gets the same tree);
        # Turn: all River cards as before
        flop = obs.street == "flop"
        import zlib
        seed = zlib.crc32(f"{obs.board}|{obs.hole_cards}|{path}".encode()) & 0x7FFFFFFF
        try:
            # Street: at the Flop with Turn network (leaf=4) the subtrees already end at the Turn beginnings (all
            # 47 Turn cards, no drawing needed), otherwise at the River beginnings
            leaf_street = 4 if (self.leaf == 4 and obs.street == "flop") else 5
            use_net = self.valuenet is not None and obs.street in ("flop", "turn")
            tree, strat, _ = solve(st, r_hero / r_hero.sum(), r_opp / r_opp.sum(), self.iters[obs.street], path=path,
                                   k_turn=(None if leaf_street == 4 and not self.k_turn_leaf else self.k_turn) if flop else None,
                                   k_river=self.k_river if flop else (self.k_river_turn if obs.street == "turn" else None),
                                   preset=self.preset, seed=seed,
                                   valuenet=self.valuenet if use_net else None, leaf_street=leaf_street if use_net else None)
        except ValueError:                          # Sequence does not fit (e.g. more raises than allowed)
            return self.bp.act(obs)
        p = strat[:, h].astype(np.float64)
        p /= p.sum()
        self.last = {"actions": tree.root_actions, "probs": p, "nodes": len(tree.kind), "ranges": source}
        if self.greedy:
            i = int(np.argmax(p))
        else:
            u = self.rng(obs).random()
            i = int(min(np.searchsorted(np.cumsum(p), u, side="right"), len(p) - 1))
        kind, amt = tree.root_actions[i]
        if kind == "fold":
            return Action.fold()
        if kind == "check":
            return Action.check()
        if kind == "call":
            return Action.call()
        return Action.raise_to(amt)


def warmup(streets: tuple[str, ...] = ("flop", "turn", "river")) -> None:
    """ Kernel for the requested streets translated once or loaded from cache (otherwise the first
    decision of a session waits up to 20 s for numba)."""
    r = np.full(N_COMBOS, 1.0 / N_COMBOS)
    for street, board in (("flop", (0, 5, 10)), ("turn", (0, 5, 10, 15)), ("river", (0, 5, 10, 15, 20))):
        if street not in streets:
            continue
        st = State(board=board, committed=(100, 100), bets=(0, 0), stacks=(900, 900), to_act=0, last_inc=20,
                   raises=0, acted=(False, False), oop=0, bb=20)
        solve(st, r, r, 1, k_turn=2, k_river=2, seed=0)


def load_valuenet(name: str):
    """ Load value network: path or name under data/valuenet/<name>.pt."""
    from pathlib import Path
    from .nn_agent import rl_root
    from .valuenet import ValueNet
    p = Path(name)
    if not p.exists():
        p = rl_root().parent / "valuenet" / (name if name.endswith(".pt") else name + ".pt")
    return ValueNet.load(p)


def set_threads(n: int) -> None:
    """ Limit numba threads per process (affects process-wide; no effect without numba)."""
    try:
        import numba
        numba.set_num_threads(max(1, min(int(n), numba.config.NUMBA_NUM_THREADS)))
    except Exception:       # pragma: no cover - no numba or not supported
        pass


def make_husearch_agent(params: str, seed: int = 0) -> HUSearchAgent:
    from .agents import make_agent
    kv = dict(p.partition("=")[::2] for p in params.split("&") if p)
    unknown = set(kv) - {"bp", "iters", "iters_river", "iters_flop", "streets", "k_turn", "k_river", "sizes", "threads",
                         "k_river_turn", "vnet", "ranges", "opp", "auto", "oppfold", "leaf", "bpgreedy", "greedy"}
    ranges = kv.get("ranges", "pre,flop")      # Standard since 30.10. 14:08 (Measurement E: +6.0 vs heuristic, -2.5 vs network)
    if unknown or "bp" not in kv or kv.get("sizes", "narrow") not in SIZE_PRESETS \
            or ranges not in ("pre", "pre,flop", "eq", "eq,flop", "heur") or kv.get("leaf", "5") not in ("4", "5"):
        raise ValueError("hus-Bot: 'hus?bp=<League-Name>|run:<Run>@<Ckpt>&iters=120&iters_river=300&iters_flop=40&streets=preflop,flop,turn,river&k_turn=6&k_river=6&k_river_turn=16&sizes=narrow|wide&threads=12&vnet=vnet-river-1&leaf=5|4&ranges=pre|pre,flop|eq|eq,flop|heur&opp=human-1@1&auto=1&bpgreedy=1 (Blueprint plays greedy where no search) &greedy=1 (Search takes top action)'")
    # ranges=eq[,flop]: Preflop ranges from heads-up equilibrium (hupreflop.path_ranges) instead of from network -
    # for deep cash (Slumbot), where opponent does not play like our tournament network (hus-4 30.10.)
    bp_streets = None if ranges == "heur" else tuple({"pre": "preflop", "flop": "flop", "eq": "eq"}[x] for x in ranges.split(","))
    bp = kv["bp"]
    if bp.startswith("run:"):
        blueprint = make_agent(f"nn?run={bp[4:]}", seed)
    else:
        from .league import League
        from .nn_agent import rl_root
        blueprint = League(rl_root().parent / "league").agent(bp, seed)
    if kv.get("bpgreedy") == "1" and hasattr(blueprint, "greedy"):
        blueprint.greedy = True             # Ranges (blueprint_ranges) remain the learned mixture, only the action becomes greedy
    streets = tuple(kv.get("streets", "turn,river").split(","))
    warmup(streets)
    return HUSearchAgent(blueprint, int(kv.get("iters", 120)), int(kv.get("iters_river", 300)), streets, seed,
                         iters_flop=int(kv.get("iters_flop", 40)), k_turn=int(kv.get("k_turn", K_TURN_DEFAULT)),
                         k_river=int(kv.get("k_river", K_RIVER_DEFAULT)), preset=kv.get("sizes", "narrow"),
                         threads=int(kv["threads"]) if "threads" in kv else None,
                         k_river_turn=int(kv["k_river_turn"]) if "k_river_turn" in kv else None,
                         valuenet=load_valuenet(kv["vnet"]) if "vnet" in kv else None, bp_streets=bp_streets,
                         opp_weights=load_opp_weights(kv["opp"]) if "opp" in kv else None, auto=kv.get("auto") == "1",
                         opp_fold=load_opp_fold(kv["oppfold"]) if "oppfold" in kv else None, leaf=int(kv.get("leaf", 5)),
                         k_turn_leaf="k_turn" in kv, greedy=kv.get("greedy") == "1")


def load_opp_fold(name: str):
    """ Fold model (humanfold.HumanFold) from data/humans/<name>.npz or path."""
    from .humanfold import HumanFold
    from .nn_agent import rl_root
    p = Path(name) if name.endswith(".npz") else rl_root().parent / "humans" / f"{name}.npz"
    return HumanFold.load(p)


def load_opp_weights(spec: str) -> dict:
    """ Opponent model '<Run>@<Checkpoint>' (e.g. human-1@1, human network from HandHQ) as numpy weights."""
    from .nn_agent import load_weights
    run, _, ck = spec.partition("@")
    return load_weights(run, ck or "latest")
