"""What the learning bot sees: Observation -> fixed-length numeric vector, plus action set.

Preprocessed on purpose instead of raw cards: Equity (preflop table or small Monte Carlo),
Pot odds, stack/pot ratios, position, hand history, tournament situation. The net
does not have to learn poker rules but only how to decide in these situations.

Actions (discrete, 6): Fold, Check/Call, Raise 1/2 Pot, Raise Pot, Raise 2x Pot, All-in.
A raise "x Pot" means: first call, then raise x times the pot (including call).
Action version act-2 (8 actions, nets store n_actions): additionally 6 = Raise 1/3 Pot and
7 = Min-Raise. The first 6 remain unchanged - old nets, datasets and anchor fit.
Fold is masked if checking is possible (fold would always be worse then).

Versions (each net stores which version it was trained with, and always plays with it):
  feat-1  46 features, equity against RANDOM opponent hands
  feat-2  feat-1 + 3: equity against estimated opponent ranges (ranges.py), their deviation from
          random equity ("how much worse does the opponent info make me") and tightness of opponent ranges
  feat-3  feat-2 + 8: opponent model (opponents.py) - opponent stats over previous hands
          (VPIP, PFR, aggression, fold to bet, resilience). Without observations: averages.
Each version extends the previous only at the end - first features are identical (anchor, widening).
"""

from __future__ import annotations

import math
import random
import zlib

import numpy as np

from ..poker import RANKS, evaluate
from .agents import mc_equity
from .observation import Action, Observation
from .tables import preflop_equity, preflop_percentile

FEATURES_VERSION = "feat-2"           # Default for new nets
FEATURE_SIZES = {"feat-1": 46, "feat-2": 49, "feat-3": 57}
RANGE_EQUITY_ITERATIONS = 120
ACTIONS = ("fold", "call", "raise_half", "raise_pot", "raise_2pot", "allin")
ACTIONS_8 = ACTIONS + ("raise_third", "raise_min")
RAISE_FRACTIONS = {2: 0.5, 3: 1.0, 4: 2.0}
RAISE_FRACTIONS_8 = {**RAISE_FRACTIONS, 6: 1 / 3}
MIN_RAISE = 7
N_ACTIONS = len(ACTIONS)                 # Default (act-1); act-2 has 8


def action_names(n: int = N_ACTIONS) -> tuple[str, ...]:
    return ACTIONS_8[:n]
EQUITY_ITERATIONS = 100

_STREET = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}


def _log_scaled(x: float, scale: float = 1.0) -> float:
    return math.log1p(max(0.0, x) / scale)


def equity_of(obs: Observation, rng: random.Random | None = None) -> float:
    opp = max(1, obs.opponents_in_hand)
    if obs.street == "preflop" or len(obs.board) < 3:
        return preflop_equity(obs.hole_cards, opp)
    rng = rng or random.Random(f"eq|{obs.hand_id}|{len(obs.history)}|{''.join(obs.hole_cards)}")
    return mc_equity(obs.hole_cards, obs.board, opp, EQUITY_ITERATIONS, rng)


def features(obs: Observation, equity: float | None = None, version: str = FEATURES_VERSION,
             opp: np.ndarray | None = None) -> np.ndarray:
    """opp: opponent features from OpponentTracker.features(obs) (only feat-3; None = no observations)."""
    base = _features_v1(obs, equity)
    if version == "feat-1":
        return base
    if version == "feat-2":
        return np.concatenate([base, _range_features(obs, float(base[4]))])
    if version == "feat-3":
        from .opponents import DEFAULT_FEATURES
        return np.concatenate([base, _range_features(obs, float(base[4])),
                               DEFAULT_FEATURES if opp is None else opp])
    raise ValueError(f"unknown feature version {version}")


def _range_features(obs: Observation, eq_random: float) -> np.ndarray:
    from .ranges import COMBO_PCT, equity_vs_ranges, opponent_ranges
    ranges = opponent_ranges(obs)
    if not ranges:
        return np.array([1.0, 0.0, 0.0], np.float32)
    seed = zlib.crc32(f"rq|{obs.hand_id}|{len(obs.history)}|{''.join(obs.hole_cards)}".encode())
    eq = equity_vs_ranges(obs, RANGE_EQUITY_ITERATIONS, seed, ranges=ranges)
    top = COMBO_PCT <= 0.15
    tight = float(np.mean([r[top].sum() for r in ranges.values()]))
    return np.array([eq, eq - eq_random, tight], np.float32)


def _features_v1(obs: Observation, equity: float | None = None) -> np.ndarray:
    f: list[float] = []
    bb = obs.big_blind or 1
    pot = obs.pot
    st = _STREET[obs.street]
    f += [1.0 if st == k else 0.0 for k in range(4)]

    # Hand
    eq = equity if equity is not None else equity_of(obs)
    opp = max(1, obs.opponents_in_hand)
    hc = obs.hole_cards
    r1, r2 = sorted((RANKS.index(c[0]) for c in hc), reverse=True)
    f += [eq, eq - 1.0 / (opp + 1), preflop_percentile(hc),
          1.0 if r1 == r2 else 0.0, 1.0 if hc[0][1] == hc[1][1] else 0.0, r1 / 12, r2 / 12]
    if len(obs.board) >= 3:
        cat = evaluate(hc + obs.board)[0]
        board_ranks = [c[0] for c in obs.board]
        suits = [c[1] for c in obs.board]
        f += [cat / 8, 1.0 if len(set(board_ranks)) < len(board_ranks) else 0.0,
              max(suits.count(s) for s in set(suits)) / 5,
              max(RANKS.index(r) for r in board_ranks) / 12]
    else:
        f += [0.0, 0.0, 0.0, 0.0]

    # Bets
    to_call = obs.to_call
    f += [to_call / (pot + to_call) if to_call else 0.0, min(to_call / pot, 4.0) / 4 if pot else 0.0,
          _log_scaled(to_call, bb), _log_scaled(pot, bb), _log_scaled(obs.my_stack, bb) / 2,
          min(obs.my_stack / pot, 20.0) / 20 if pot else 1.0,
          1.0 if obs.can_check else 0.0, 1.0 if obs.can_raise else 0.0,
          1.0 if to_call >= obs.my_stack else 0.0]
    others = [obs.stacks[s] + obs.bets[s] for s in range(obs.num_seats)
              if s != obs.seat and obs.in_hand[s] and not obs.folded[s]]
    eff = min(obs.my_stack + obs.my_bet, max(others)) if others else 0
    f += [_log_scaled(eff, bb) / 2]

    # Position and number of players
    players = sum(obs.in_hand)
    pos = obs.position()
    f += [pos / max(1, players - 1), 1.0 if obs.seat == obs.button else 0.0,
          1.0 if obs.seat == obs.sb_seat else 0.0, 1.0 if obs.seat == obs.bb_seat else 0.0,
          players / 10, obs.opponents_in_hand / 9, obs.active_opponents / 9]

    # History
    street_acts = obs.street_actions()
    raises = sum(1 for a in street_acts if a.kind in ("bet", "raise"))
    f += [1.0 if raises == k else 0.0 for k in range(3)] + [1.0 if raises >= 3 else 0.0]
    pre = obs.street_actions("preflop")
    pre_raisers = [a.seat for a in pre if a.kind in ("bet", "raise")]
    callers = sum(1 for a in street_acts if a.kind == "call")
    aggressors = [a.seat for a in obs.history if a.kind in ("bet", "raise")]
    f += [min(len(pre_raisers), 4) / 4, min(callers, 5) / 5,
          1.0 if pre_raisers and pre_raisers[-1] == obs.seat else 0.0,
          1.0 if aggressors and aggressors[-1] == obs.seat else 0.0,
          1.0 if any(a.allin for a in obs.history if a.seat != obs.seat) else 0.0]

    # Tournament
    t = obs.tournament
    if t:
        left = t.get("players_left", players)
        avg = t.get("average_stack") or 1
        paid = len(t.get("payouts") or ())
        f += [1.0, left / max(1, t.get("start_players", left)), min(t.get("level", 0), 10) / 10,
              _log_scaled(obs.my_stack + obs.my_bet, avg), 1.0 if left <= paid + 1 else 0.0]
    else:
        f += [0.0, 0.0, 0.0, 0.0, 0.0]
    return np.asarray(f, dtype=np.float32)


N_FEATURES = FEATURE_SIZES[FEATURES_VERSION]
EFF_STACK_INDEX = 24          # log1p(effective stack / BB) / 2
PLAYERS_INDEX = 29            # Players with cards / 10


def version_for_width(n: int) -> str:
    for v, k in FEATURE_SIZES.items():
        if k == n:
            return v
    raise ValueError(f"no feature version with {n} features")


def eff_stack_bb(x: np.ndarray) -> np.ndarray:
    return np.expm1(2 * x[..., EFF_STACK_INDEX])


def action_mask(obs: Observation, n: int = N_ACTIONS) -> np.ndarray:
    m = np.zeros(n, dtype=bool)
    m[1] = True
    m[0] = not obs.can_check
    if obs.can_raise and obs.max_raise_to is not None:
        m[5] = True
        for i, frac in (RAISE_FRACTIONS_8 if n > 6 else RAISE_FRACTIONS).items():
            # Offer size only if genuinely below all-in (otherwise twice) - for act-2 also
            # genuinely above min-raise (small amounts are otherwise rounded up to min-raise)
            amt = _raise_amount(obs, frac)
            m[i] = amt < obs.max_raise_to and (n <= MIN_RAISE or amt > obs.min_raise_to)
        if n > MIN_RAISE:
            m[MIN_RAISE] = obs.min_raise_to < obs.max_raise_to
    return m


def _raise_amount(obs: Observation, frac: float) -> int:
    target = obs.current_bet + frac * (obs.pot + obs.to_call)
    return int(round(max(obs.min_raise_to, min(obs.max_raise_to, target))))


def to_action(obs: Observation, idx: int) -> Action:
    if idx == 0:
        return Action.check() if obs.can_check else Action.fold()
    if idx == 1 or not obs.can_raise:
        return Action.check() if obs.can_check else Action.call()
    if idx == 5:
        return Action.raise_to(obs.max_raise_to)
    if idx == MIN_RAISE:
        return Action.raise_to(obs.min_raise_to)
    return Action.raise_to(_raise_amount(obs, RAISE_FRACTIONS_8[idx]))


def from_action(obs: Observation, action: Action, n: int = N_ACTIONS) -> int:
    """Maps a (legal) action of another bot to the next discrete action
    (for imitation)."""
    if action.kind == "fold":
        return 1 if obs.can_check else 0
    if action.kind in ("check", "call"):
        return 1
    if action.amount is not None and obs.max_raise_to is not None and action.amount >= obs.max_raise_to:
        return 5
    mask = action_mask(obs, n)
    best, best_d = 5, math.inf
    sizes = {i: _raise_amount(obs, f) for i, f in (RAISE_FRACTIONS_8 if n > 6 else RAISE_FRACTIONS).items()}
    if n > MIN_RAISE:
        sizes[MIN_RAISE] = obs.min_raise_to
    for i, amt in sizes.items():
        if mask[i]:
            d = abs(amt - action.amount)
            if d < best_d:
                best, best_d = i, d
    if mask[5] and abs(obs.max_raise_to - action.amount) < best_d:
        best = 5
    return best
