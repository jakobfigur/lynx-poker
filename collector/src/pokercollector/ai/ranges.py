"""Ranges: which hands is an opponent likely to have after their previous actions?

Previously, the bot calculated equity against RANDOM opponent hands. But someone who 3-bets preflop or goes all-in on the river rarely has junk. Each opponent maintains a weighting over all 1326 starting combinations,
which shifts with each of their actions (Bayes-like, with a simple action model):

  preflop  Raise:  weight ~ "belonging to the top q %" (Open ~30%, 3-Bet ~10%, 4-Bet ~4.5%);
                   short all-ins broader (10 BB ~ 24%, 5 BB ~ 48%)
           Call:   top ~60% (Limp) or ~35 / 14 / 6% against 1 / 2 / 3 raises
  postflop Bet/Raise: weight x (0.15 + 0.85 * s^1.5), Call: x (0.3 + 0.7 * s^0.6), Check: x (1 - 0.35 * s^4)
           s = strength of combination on that board (percentile 0..1 among all combos).
           The lower bounds allow bluffs and draws in the range.

Then equity via Monte-Carlo: opponent hands are sampled from their ranges (numba). This is a
heuristic model, not an exact Bayes with an opponent strategy - but it is exactly the
"belief state" that a later search (Pluribus-like) needs as a starting point: sample_hands().
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from ..fastpoker import CARD_INDEX, eval_cards, njit
from ..poker import FULL_DECK
from .observation import Observation
from .tables import preflop_percentile

RANGES_VERSION = "ranges-1"
COMBOS = np.array([(i, j) for i in range(52) for j in range(i + 1, 52)], np.int64)       # 1326 x 2
COMBO_PCT = np.array([preflop_percentile([FULL_DECK[i], FULL_DECK[j]]) for i, j in COMBOS])
OPEN_Q = (0.30, 0.10, 0.045, 0.03)
CALL_Q = (0.60, 0.35, 0.14, 0.06)


def _sig(x):
    return 1.0 / (1.0 + np.exp(-x))


# Precomputed (for speed): which combinations contain card c; preflop factors per raise level
COMBO_HAS = np.zeros((52, len(COMBOS)), bool)
COMBO_HAS[COMBOS[:, 0], np.arange(len(COMBOS))] = True
COMBO_HAS[COMBOS[:, 1], np.arange(len(COMBOS))] = True
PRE_RAISE = [_sig((q - COMBO_PCT) / 0.03) for q in OPEN_Q]
PRE_CALL = [_sig((q - COMBO_PCT) / 0.05) for q in CALL_Q]
# Heads-up (only for search, husearch.py): button opens ~85%, BB defends ~70%, 3-bet ~15%
OPEN_Q_HU = (0.85, 0.15, 0.06, 0.035)
CALL_Q_HU = (0.90, 0.70, 0.45, 0.12)
PRE_RAISE_HU = [_sig((q - COMBO_PCT) / 0.05) for q in OPEN_Q_HU]
PRE_CALL_HU = [_sig((q - COMBO_PCT) / 0.06) for q in CALL_Q_HU]


def dead_mask(cards: list[str]) -> np.ndarray:
    return COMBO_HAS[[CARD_INDEX[c] for c in cards]].any(0) if cards else np.zeros(len(COMBOS), bool)


@njit(cache=True)
def _strengths(combos, board, nb):
    n = combos.shape[0]
    vals = np.empty(n, np.int64)
    cards = np.empty(7, np.int64)
    for k in range(nb):
        cards[2 + k] = board[k]
    for i in range(n):
        a, b = combos[i, 0], combos[i, 1]
        clash = False
        for k in range(nb):
            if board[k] == a or board[k] == b:
                clash = True
        if clash:
            vals[i] = -1
            continue
        cards[0] = a
        cards[1] = b
        vals[i] = eval_cards(cards, nb + 2)
    return vals


@lru_cache(maxsize=4096)
def board_strength(board: tuple[str, ...]) -> np.ndarray:
    """Strength of each combination on this board as percentile (0 weakest .. 1 strongest)."""
    b = np.array([CARD_INDEX[c] for c in board], np.int64)
    vals = _strengths(COMBOS, b, len(b))
    ok = vals >= 0
    order = np.sort(vals[ok])
    lo = np.searchsorted(order, vals, side="left")
    hi = np.searchsorted(order, vals, side="right")
    s = (lo + hi) / 2.0 / max(1, len(order))           # Tie: average rank
    s[~ok] = 0.0
    return s


@lru_cache(maxsize=4096)
def board_factors(board: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Factors for Bet/Raise, Call, Check on this board (precomputed, cached)."""
    s = board_strength(board)
    return 0.15 + 0.85 * s ** 1.5, 0.3 + 0.7 * s ** 0.6, 1.0 - 0.35 * s ** 4


def opponent_ranges(obs: Observation, heads_up: bool = False) -> dict[int, np.ndarray]:
    """Weights (sum 1) over the 1326 combinations for every opponent still in hand.
    heads_up=True: preflop parameters for heads-up (much wider; only the search uses this)."""
    pre_raise, pre_call = (PRE_RAISE_HU, PRE_CALL_HU) if heads_up else (PRE_RAISE, PRE_CALL)
    open_q = OPEN_Q_HU if heads_up else OPEN_Q
    known = list(obs.hole_cards) + list(obs.board)
    base = (~dead_mask(known)).astype(np.float64)
    live = [s for s in range(obs.num_seats) if s != obs.seat and obs.in_hand[s] and not obs.folded[s]]
    w = {s: base.copy() for s in live}
    bb = obs.big_blind or 1
    raises = {"preflop": 0, "flop": 0, "turn": 0, "river": 0}
    board_at = {"flop": tuple(obs.board[:3]), "turn": tuple(obs.board[:4]), "river": tuple(obs.board[:5])}
    for a in obs.history:
        if a.kind in ("post_sb", "post_bb"):
            continue
        st = a.street
        n_before = raises[st]
        if a.kind in ("bet", "raise"):
            raises[st] += 1
        if a.seat not in w:
            continue
        x = w[a.seat]
        if st == "preflop":
            if a.kind in ("bet", "raise"):
                amt_bb = (a.amount_to or 0) / bb
                q = open_q[min(n_before, 3)]
                if a.allin and 0 < amt_bb <= 20 and min(0.7, 0.12 * 20 / amt_bb) > q:
                    x *= _sig((min(0.7, 0.12 * 20 / amt_bb) - COMBO_PCT) / 0.03)
                else:
                    x *= pre_raise[min(n_before, 3)]
            elif a.kind == "call":
                x *= pre_call[min(n_before, 3)]
        else:
            if len(board_at[st]) < {"flop": 3, "turn": 4, "river": 5}[st]:
                continue
            f_bet, f_call, f_check = board_factors(board_at[st])
            if a.kind in ("bet", "raise"):
                x *= f_bet
            elif a.kind == "call":
                x *= f_call
            elif a.kind == "check":
                x *= f_check
    out = {}
    for s, x in w.items():
        tot = x.sum()
        out[s] = x / tot if tot > 0 else base / base.sum()
    return out


@njit(cache=True)
def _mc_vs_ranges(hole, board, nb, cum, combos, iterations, seed):
    np.random.seed(seed)
    k = cum.shape[0]
    used0 = np.zeros(52, np.bool_)
    used0[hole[0]] = True
    used0[hole[1]] = True
    for i in range(nb):
        used0[board[i]] = True
    mine = np.empty(7, np.int64)
    theirs = np.empty(7, np.int64)
    mine[0], mine[1] = hole[0], hole[1]
    for i in range(nb):
        mine[2 + i] = board[i]
        theirs[2 + i] = board[i]
    opp = np.empty((k, 2), np.int64)
    deck = np.empty(52, np.int64)
    total = 0.0
    done = 0
    for _ in range(iterations):
        used = used0.copy()
        ok = True
        for o in range(k):
            got = False
            for _try in range(30):
                u = np.random.random()
                idx = np.searchsorted(cum[o], u)
                if idx >= combos.shape[0]:
                    idx = combos.shape[0] - 1
                a, b = combos[idx, 0], combos[idx, 1]
                if not used[a] and not used[b]:
                    used[a] = True
                    used[b] = True
                    opp[o, 0], opp[o, 1] = a, b
                    got = True
                    break
            if not got:
                ok = False
                break
        if not ok:
            continue
        nd = 0
        for c in range(52):
            if not used[c]:
                deck[nd] = c
                nd += 1
        need = 5 - nb
        for j in range(need):
            x = j + np.random.randint(nd - j)
            t = deck[j]
            deck[j] = deck[x]
            deck[x] = t
            mine[2 + nb + j] = deck[j]
            theirs[2 + nb + j] = deck[j]
        hv = eval_cards(mine, 7)
        n_eq = 0
        lost = False
        for o in range(k):
            theirs[0], theirs[1] = opp[o, 0], opp[o, 1]
            ov = eval_cards(theirs, 7)
            if ov > hv:
                lost = True
                break
            if ov == hv:
                n_eq += 1
        if not lost:
            total += 1.0 / (n_eq + 1)
        done += 1
    return total / done if done else 0.5


def equity_vs_ranges(obs: Observation, iterations: int = 200, seed: int = 0,
                     ranges: dict[int, np.ndarray] | None = None) -> float:
    ranges = ranges if ranges is not None else opponent_ranges(obs)
    if not ranges:
        return 1.0
    cum = np.cumsum(np.array(list(ranges.values())), axis=1)
    cum[:, -1] = 1.0
    hole = np.array([CARD_INDEX[c] for c in obs.hole_cards], np.int64)
    board = np.array([CARD_INDEX[c] for c in obs.board], np.int64) if obs.board else np.zeros(0, np.int64)
    return float(_mc_vs_ranges(hole, board, len(obs.board), cum, COMBOS, iterations, seed & 0x7FFFFFFF))


def sample_hands(ranges: dict[int, np.ndarray], dead: list[str], rng: np.random.Generator,
                 tries: int = 50) -> dict[int, list[str]] | None:
    """Draws consistent opponent hands from the ranges (for search: possible 'worlds').
    None if no collision-free assignment found after `tries` attempts."""
    for _ in range(tries):
        used = {CARD_INDEX[c] for c in dead}
        out = {}
        for s, r in ranges.items():
            idx = int(rng.choice(len(r), p=r))
            a, b = COMBOS[idx]
            if a in used or b in used:
                break
            used |= {int(a), int(b)}
            out[s] = [FULL_DECK[a], FULL_DECK[b]]
        else:
            return out
    return None


def range_summary(r: np.ndarray) -> dict:
    """For display/tests: how tight is the range (weight proportion in top 10% / 30%)?"""
    return {"top10": float(r[COMBO_PCT <= 0.10].sum()), "top30": float(r[COMBO_PCT <= 0.30].sum()),
            "entropy_bits": float(-(r[r > 0] * np.log2(r[r > 0])).sum())}
