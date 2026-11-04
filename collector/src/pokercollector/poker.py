"""Cards, 7-card hand evaluation, and Monte Carlo equity.

Card notation: Rank from '23456789TJQKA' + Suit from 'shdc' (e.g. 'Ts' = Ten of Spades).
"""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass

RANKS = "23456789TJQKA"
SUITS = "shdc"
SUIT_SYMBOLS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
FULL_DECK = [r + s for r in RANKS for s in SUITS]

CATEGORY_NAMES = [
    'High Card', "Pair", 'Two Pair', 'Three of a Kind', "Straight",
    "Flush", 'Full House', 'Four of a Kind', 'Straight Flush',
]


def is_card(c: str | None) -> bool:
    return isinstance(c, str) and len(c) == 2 and c[0] in RANKS and c[1] in SUITS


def normalize_rank(token: str) -> str | None:
    t = token.strip().upper().replace("O", "0")
    if t in ("10", "1O", "IO", "T"):
        return "T"
    if len(t) == 1 and t in RANKS:
        return t
    return None


def _straight_high(rank_mask: int) -> int:
    """ Highest card of a straight in the bitmask (bit i = rank i), otherwise -1. Wheel = 3."""
    for high in range(12, 3, -1):
        need = 0b11111 << (high - 4)
        if rank_mask & need == need:
            return high
    if rank_mask & 0b1000000001111 == 0b1000000001111:  # A-2-3-4-5
        return 3
    return -1


def evaluate(cards: list[str]) -> tuple:
    """ Evaluates 5-7 cards. Larger tuple = stronger hand. Element 0 = category."""
    ranks = [RANKS.index(c[0]) for c in cards]
    suits = [c[1] for c in cards]
    suit_count = Counter(suits)
    flush_suit = next((s for s, n in suit_count.items() if n >= 5), None)
    if flush_suit:
        fr = sorted((r for r, s in zip(ranks, suits) if s == flush_suit), reverse=True)
        mask = 0
        for r in fr:
            mask |= 1 << r
        sh = _straight_high(mask)
        if sh >= 0:
            return (8, sh)
    cnt = Counter(ranks)
    groups = sorted(cnt.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    if groups[0][1] == 4:
        quad = groups[0][0]
        kicker = max(r for r in ranks if r != quad)
        return (7, quad, kicker)
    trips = sorted((r for r, n in cnt.items() if n >= 3), reverse=True)
    pairs = sorted((r for r, n in cnt.items() if n == 2), reverse=True)
    if trips and (len(trips) > 1 or pairs):
        t = trips[0]
        p = max(([trips[1]] if len(trips) > 1 else []) + pairs)
        return (6, t, p)
    if flush_suit:
        fr = sorted((r for r, s in zip(ranks, suits) if s == flush_suit), reverse=True)
        return (5, *fr[:5])
    mask = 0
    for r in ranks:
        mask |= 1 << r
    sh = _straight_high(mask)
    if sh >= 0:
        return (4, sh)
    if trips:
        t = trips[0]
        kick = sorted((r for r in ranks if r != t), reverse=True)[:2]
        return (3, t, *kick)
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        kicker = max(r for r in ranks if r not in (p1, p2))
        return (2, p1, p2, kicker)
    if pairs:
        p = pairs[0]
        kick = sorted((r for r in ranks if r != p), reverse=True)[:3]
        return (1, p, *kick)
    return (0, *sorted(ranks, reverse=True)[:5])


def describe(value: tuple) -> str:
    return CATEGORY_NAMES[value[0]]


@dataclass(frozen=True)
class EquityResult:
    equity: float          # Winning share including partial split pots
    win: float
    tie: float
    iterations: int
    std_error: float
    opponents: int
    assumption: str


def equity_vs_random(hero: list[str], board: list[str], opponents: int,
                     iterations: int = 3000, seed: int | None = 0,
                     dead: list[str] | None = None) -> EquityResult:
    """Monte Carlo equity against `opponents` random hands.

    Explicit assumption: opponents hold randomly distributed cards. Real
    opponents still in the pot usually have stronger hands on average; thus, the
    figure typically overestimates the equity.
    """
    if len(hero) != 2 or not all(is_card(c) for c in hero):
        raise ValueError(f"invalid hero cards: {hero}")
    if len(board) > 5 or not all(is_card(c) for c in board):
        raise ValueError(f"invalid board: {board}")
    if opponents < 1:
        raise ValueError('at least one opponent')
    if len(set(hero + board)) != len(hero) + len(board):
        raise ValueError('duplicate cards')
    from .fastpoker import HAVE_NUMBA, mc_stats
    if HAVE_NUMBA and not dead:
        s, sq, wins, ties = mc_stats(hero, board, opponents, iterations, random.Random(seed).getrandbits(31))
        n = iterations
        mean = s / n
        var = max(0.0, sq / n - mean * mean)
        return EquityResult(mean, wins / n, ties / n, n, math.sqrt(var / n), opponents,
                            'opponent with random cards (no ranges)')
    known = set(hero) | set(board) | set(dead or [])
    deck = [c for c in FULL_DECK if c not in known]
    rng = random.Random(seed)
    need_board = 5 - len(board)
    share_sum = 0.0
    share_sq = 0.0
    wins = ties = 0
    for _ in range(iterations):
        draw = rng.sample(deck, need_board + 2 * opponents)
        full_board = board + draw[:need_board]
        hv = evaluate(hero + full_board)
        best_opp = None
        n_equal = 0
        lost = False
        for i in range(opponents):
            o = draw[need_board + 2 * i: need_board + 2 * i + 2]
            ov = evaluate(o + full_board)
            if ov > hv:
                lost = True
                break
            if ov == hv:
                n_equal += 1
            if best_opp is None or ov > best_opp:
                best_opp = ov
        if lost:
            share = 0.0
        elif n_equal:
            share = 1.0 / (n_equal + 1)
            ties += 1
        else:
            share = 1.0
            wins += 1
        share_sum += share
        share_sq += share * share
    n = iterations
    mean = share_sum / n
    var = max(0.0, share_sq / n - mean * mean)
    return EquityResult(mean, wins / n, ties / n, n, math.sqrt(var / n), opponents,
                        'opponent with random cards (no ranges)')


def pot_odds(to_call: int, pot: int) -> float:
    """Required equity for a profitable call without future bets."""
    if to_call <= 0:
        return 0.0
    return to_call / (pot + to_call)
