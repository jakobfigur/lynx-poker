"""Blueprint ranges for the heads-up search (husearch.py).

Previously, the search estimated both players' ranges at street start with a heuristic (ranges.py:
"Button opens ~85%, BB defends ~70%"). Night diagnosis 29/30.10. showed that the search loses against its own blueprint network with that. Here the ranges instead come from the blueprint itself
(Bayes with the actual strategy): the hand is replayed from the start with the engine, and at every
decision of either player, for EACH possible starting hand it is queried with what probability
the network would have chosen exactly this action. The product over all actions is the range
(preflop over 169 hand classes, afterward spread over 1326 combinations; postflop, if desired, over all combinations excluding board cards).

For the own player, this is exact (because they play the blueprint, where no search is done); for the opponent,
it is the assumption "he plays like our blueprint" - still better than a rule of thumb, because the network
knows stack depth, blind level, and tournament situation. Opponent features (feat-3) are filled with given values.

Streets not modeled by the blueprint (default: everything after preflop) continue to get the heuristic factors from ranges.py. If the course does not match the engine (live uncertainty), blueprint_ranges returns None and the search falls back to public_ranges.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from ..poker import FULL_DECK
from .engine import Hand, IllegalAction
from .features import action_mask, features, from_action
from .observation import Action, Observation
from .ranges import COMBOS, PRE_CALL_HU, PRE_RAISE_HU, board_factors, dead_mask
from .tables import all_classes, example_cards, hand_class

CLASSES = all_classes()
CLASS_ID = {c: i for i, c in enumerate(CLASSES)}
COMBO_CLASS = np.array([CLASS_ID[hand_class([FULL_DECK[i], FULL_DECK[j]])] for i, j in COMBOS], np.int64)
CLASS_CARDS = [example_cards(c) for c in CLASSES]
COMBO_CARDS = [[FULL_DECK[i], FULL_DECK[j]] for i, j in COMBOS]

_CACHE: dict = {}
_CACHE_MAX = 512


def forward_batch(w: dict, x: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Network probabilities for many situations (rows) with a common action mask."""
    h = np.maximum(x @ w["w1"].T + w["b1"], 0)
    h = np.maximum(h @ w["w2"].T + w["b2"], 0)
    logits = h @ w["wp"].T + w["bp"]
    logits = np.where(mask[None, :], logits, -1e9)
    logits -= logits.max(1, keepdims=True)
    p = np.exp(logits) * mask[None, :]
    return p / p.sum(1, keepdims=True)


def _action(a) -> Action:
    if a.kind == "fold":
        return Action.fold()
    if a.kind == "check":
        return Action.check()
    if a.kind == "call":
        return Action.call()
    return Action.raise_to(int(a.amount_to or 0))


def _deck_for(board: list[str]) -> list[str]:
    """Deck whose board (positions 20-24) begins with the known board."""
    rest = [c for c in FULL_DECK if c not in board]
    full = list(board) + rest[: 5 - len(board)]
    remaining = rest[5 - len(board):]
    return remaining[:20] + full + remaining[20:]


def _blueprint_probs(w: dict, obs_t: Observation, act: Action, cards: list[list[str]]) -> np.ndarray:
    """P(act | hand) for each hand list in `cards` in state obs_t (without own cards)."""
    na = w.get("n_actions", 6)
    version = w.get("features", "feat-1")
    mask = action_mask(obs_t, na)
    idx = from_action(obs_t, act, na)
    x = np.stack([features(replace(obs_t, hole_cards=list(hc)), version=version) for hc in cards])
    return forward_batch(w, x, mask)[:, idx]


def _apply_blueprint(w: dict, weights: np.ndarray, obs_t: Observation, act: Action) -> None:
    if obs_t.street == "preflop":
        p = _blueprint_probs(w, obs_t, act, CLASS_CARDS)
        weights *= p[COMBO_CLASS]
    else:
        live = np.nonzero(~dead_mask(list(obs_t.board)))[0]
        p = _blueprint_probs(w, obs_t, act, [COMBO_CARDS[i] for i in live])
        f = np.zeros(len(COMBOS))
        f[live] = p
        weights *= f


def _apply_heuristic(weights: np.ndarray, obs_t: Observation, a, raises_before: int) -> None:
    if obs_t.street == "preflop":
        if a.kind in ("bet", "raise"):
            weights *= PRE_RAISE_HU[min(raises_before, 3)]
        elif a.kind == "call":
            weights *= PRE_CALL_HU[min(raises_before, 3)]
        return
    f_bet, f_call, f_check = board_factors(tuple(obs_t.board))
    if a.kind in ("bet", "raise"):
        weights *= f_bet
    elif a.kind == "call":
        weights *= f_call
    elif a.kind == "check":
        weights *= f_check


def _cache_key(obs: Observation, hero: int, opp: int, w: dict, bp_streets: tuple[str, ...]):
    past = tuple((a.street, a.seat, a.kind, a.amount_to) for a in obs.history if a.street != obs.street)
    return (obs.hand_id, hero, opp, past, tuple(obs.board), obs.street, id(w), bp_streets,
            tuple(obs.stacks), tuple(obs.committed))


def blueprint_ranges(obs: Observation, hero: int, opp: int, blueprint,
                     bp_streets: tuple[str, ...] = ("preflop",), opp_weights: dict | None = None,
                     opp_fold=None) -> tuple[np.ndarray, np.ndarray] | None:
    """Ranges (sum 1) of hero and opp at BEGINNING of current street from the blueprint network.
    opp_weights: own network for the opponent’s actions (e.g., human model human-1, H11); if not
    specified, 'the opponent plays like our blueprint' applies. None if no network is available or the history
    cannot be replayed."""
    w = getattr(blueprint, "w", None)
    if not isinstance(w, dict) or "w1" not in w:
        if not (bp_streets and set(bp_streets) <= {"eq"}):   # equilibrium only needs no network
            return None
        w = {}
    key = _cache_key(obs, hero, opp, w, bp_streets) + (id(opp_weights) if opp_weights is not None else 0,
                                                       id(opp_fold) if opp_fold is not None else 0)
    if key in _CACHE:
        r_hero, r_opp = _CACHE[key]
        return r_hero.copy(), r_opp.copy()
    try:
        out = _compute(obs, hero, opp, w, bp_streets, opp_weights, opp_fold)
    except (IllegalAction, ValueError, RuntimeError, IndexError, KeyError, TypeError):
        return None
    if out is None:
        return None
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = out
    return out[0].copy(), out[1].copy()


def _compute(obs: Observation, hero: int, opp: int, w: dict, bp_streets: tuple[str, ...],
             opp_weights: dict | None = None, opp_fold=None):
    """opp_fold: humanfold.HumanFold - before each (non-fold) opponent action, their range is multiplied
    with the continuation probability per combination (hands a human would have folded here disappear), then opp_weights assesses the chosen action."""
    n = obs.num_seats
    w_of = {hero: w, opp: opp_weights if opp_weights is not None else w}
    start = [int(obs.stacks[s] + obs.committed[s]) if obs.in_hand[s] else 0 for s in range(n)]
    h = Hand(start, obs.button, obs.small_blind, obs.big_blind, deck=_deck_for(list(obs.board)),
             hand_id=obs.hand_id, tournament=obs.tournament)
    if h.sb_seat != obs.sb_seat or h.bb_seat != obs.bb_seat or h.button != obs.button:
        return None
    base = (~dead_mask(list(obs.board))).astype(np.float64)
    weights = {hero: base.copy(), opp: base.copy()}
    raises = {"preflop": 0, "flop": 0, "turn": 0, "river": 0}
    eq = "eq" in bp_streets                 # Preflop from heads-up equilibrium (hupreflop) instead of network/heuristic
    if eq:
        if obs.street == "preflop":
            return None
        from .hupreflop import equilibrium_ranges
        rr = equilibrium_ranges(obs)
        if rr is None:
            return None
        r_sb, r_bb = rr
        for s in (hero, opp):
            weights[s] *= (r_sb if s == obs.sb_seat else r_bb)[COMBO_CLASS]
    for a in obs.history:
        if a.kind in ("post_sb", "post_bb"):
            continue
        if a.street == obs.street:
            break
        if h.done or h.street != a.street or h.to_act != a.seat:
            return None
        act = _action(a)
        if a.seat == opp and opp_fold is not None and a.kind != "fold":
            weights[opp] *= opp_fold.continue_factor(h.observation(opp), weights[opp])
        if a.seat in weights and not (eq and a.street == "preflop"):
            obs_t = h.observation(a.seat)
            if a.street in bp_streets:
                _apply_blueprint(w_of[a.seat], weights[a.seat], obs_t, act)
            else:
                _apply_heuristic(weights[a.seat], obs_t, a, raises[a.street])
        if a.kind in ("bet", "raise"):
            raises[a.street] += 1
        h.apply(a.seat, act)
    if obs.street != "preflop" and h.street != obs.street:
        return None
    out = []
    for s in (hero, opp):
        x = weights[s]
        tot = x.sum()
        out.append(x / tot if tot > 0 else base / base.sum())
    return out[0], out[1]
