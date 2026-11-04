"""Schnelle Handbewertung und Monte-Carlo-Equity (numba, Maschinencode).

Profil vom 26.10.2026: 95 % der Simulationszeit steckten in mc_equity -> evaluate (reines Python,
~70 us je Bewertung). Hier dieselbe Logik auf ganzen Zahlen, kompiliert: ~100x schneller.

Karten als Zahl 0..51 = Rang * 4 + Farbe (Reihenfolge wie poker.FULL_DECK).
Bewertung als eine Zahl: Kategorie << 20 | bis zu 5 Raenge je 4 Bit. Die Rangfolge ist identisch
mit poker.evaluate (Test: tests/test_fastpoker.py vergleicht beide auf Zufallshaenden).

Ohne numba (z. B. nicht installiert) faellt alles auf die Python-Version zurueck.
"""

from __future__ import annotations

import numpy as np

from .poker import FULL_DECK

CARD_INDEX = {c: i for i, c in enumerate(FULL_DECK)}

try:
    from numba import njit, prange
    HAVE_NUMBA = True
except ImportError:          # pragma: no cover - Rueckfall
    HAVE_NUMBA = False
    prange = range

    def njit(*args, **kwargs):
        if args and callable(args[0]):
            return args[0]
        return lambda f: f


@njit(cache=True)
def _straight_high(mask):
    for high in range(12, 3, -1):
        need = 0b11111 << (high - 4)
        if mask & need == need:
            return high
    if mask & 0b1000000001111 == 0b1000000001111:
        return 3
    return -1


@njit(cache=True)
def _top(mask, k):
    """Die k hoechsten gesetzten Raenge, je 4 Bit, absteigend gepackt (linksbuendig in 5 Stellen)."""
    v = 0
    got = 0
    r = 12
    while r >= 0 and got < k:
        if mask & (1 << r):
            v = (v << 4) | r
            got += 1
        r -= 1
    while got < 5:
        v <<= 4
        got += 1
    return v


@njit(cache=True)
def eval_cards(cards, n):
    counts = np.zeros(13, np.int64)
    suit_mask = np.zeros(4, np.int64)
    suit_n = np.zeros(4, np.int64)
    rank_mask = 0
    for i in range(n):
        c = cards[i]
        r = c >> 2
        s = c & 3
        counts[r] += 1
        suit_mask[s] |= 1 << r
        suit_n[s] += 1
        rank_mask |= 1 << r
    flush = -1
    for s in range(4):
        if suit_n[s] >= 5:
            flush = s
    if flush >= 0:
        sh = _straight_high(suit_mask[flush])
        if sh >= 0:
            return (8 << 20) | (sh << 16)
    quad = -1
    t1 = -1
    t2 = -1
    p1 = -1
    p2 = -1
    p3 = -1
    for r in range(12, -1, -1):
        c = counts[r]
        if c == 4 and quad < 0:
            quad = r
        elif c == 3:
            if t1 < 0:
                t1 = r
            elif t2 < 0:
                t2 = r
        elif c == 2:
            if p1 < 0:
                p1 = r
            elif p2 < 0:
                p2 = r
            elif p3 < 0:
                p3 = r
    if quad >= 0:
        kick = _top(rank_mask & ~(1 << quad), 1) >> 16
        return (7 << 20) | (quad << 16) | (kick << 12)
    if t1 >= 0 and (t2 >= 0 or p1 >= 0):
        p = max(t2, p1)
        return (6 << 20) | (t1 << 16) | (p << 12)
    if flush >= 0:
        return (5 << 20) | _top(suit_mask[flush], 5)
    sh = _straight_high(rank_mask)
    if sh >= 0:
        return (4 << 20) | (sh << 16)
    if t1 >= 0:
        return (3 << 20) | (t1 << 16) | (_top(rank_mask & ~(1 << t1), 2) >> 4)
    if p2 >= 0:
        kick = _top(rank_mask & ~(1 << p1) & ~(1 << p2), 1) >> 16
        return (2 << 20) | (p1 << 16) | (p2 << 12) | (kick << 8)
    if p1 >= 0:
        return (1 << 20) | (p1 << 16) | (_top(rank_mask & ~(1 << p1), 3) >> 4)
    return _top(rank_mask, 5)


@njit(cache=True)
def _mc(hole, board, n_board, opponents, iterations, seed):
    """Summe der Anteile, Quadratsumme, Siege, Splits gegen `opponents` Zufallshaende."""
    np.random.seed(seed)
    known = np.zeros(52, np.bool_)
    known[hole[0]] = True
    known[hole[1]] = True
    for i in range(n_board):
        known[board[i]] = True
    deck = np.empty(52 - 2 - n_board, np.int64)
    k = 0
    for c in range(52):
        if not known[c]:
            deck[k] = c
            k += 1
    nd = k
    need = 5 - n_board
    draws = need + 2 * opponents
    mine = np.empty(7, np.int64)
    theirs = np.empty(7, np.int64)
    mine[0] = hole[0]
    mine[1] = hole[1]
    for i in range(n_board):
        mine[2 + i] = board[i]
        theirs[2 + i] = board[i]
    s_sum = 0.0
    s_sq = 0.0
    wins = 0
    ties = 0
    for _ in range(iterations):
        for j in range(draws):                      # teilweises Mischen (Fisher-Yates)
            x = j + np.random.randint(nd - j)
            tmp = deck[j]
            deck[j] = deck[x]
            deck[x] = tmp
        for j in range(need):
            mine[2 + n_board + j] = deck[j]
            theirs[2 + n_board + j] = deck[j]
        hv = eval_cards(mine, 7)
        n_eq = 0
        lost = False
        for o in range(opponents):
            theirs[0] = deck[need + 2 * o]
            theirs[1] = deck[need + 2 * o + 1]
            ov = eval_cards(theirs, 7)
            if ov > hv:
                lost = True
                break
            if ov == hv:
                n_eq += 1
        if lost:
            share = 0.0
        elif n_eq > 0:
            share = 1.0 / (n_eq + 1)
            ties += 1
        else:
            share = 1.0
            wins += 1
        s_sum += share
        s_sq += share * share
    return s_sum, s_sq, wins, ties


def to_ints(cards: list[str]) -> np.ndarray:
    return np.array([CARD_INDEX[c] for c in cards], np.int64)


def evaluate_fast(cards: list[str]) -> int:
    return int(eval_cards(to_ints(cards), len(cards)))


def mc_stats(hole: list[str], board: list[str], opponents: int, iterations: int, seed: int,
             dead: list[str] | None = None) -> tuple[float, float, int, int]:
    """(Summe, Quadratsumme, Siege, Splits). dead: zusaetzlich bekannte Karten (selten, Python-Weg)."""
    b = to_ints(board) if board else np.zeros(0, np.int64)
    return _mc(to_ints(hole), b, len(board), max(1, min(opponents, 9)), iterations, seed & 0x7FFFFFFF)
