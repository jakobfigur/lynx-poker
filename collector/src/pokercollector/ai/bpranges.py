"""Blueprint-Ranges fuer die Heads-up-Suche (husearch.py).

Bisher schaetzte die Suche die Ranges beider Spieler zu Strassenbeginn mit einer Heuristik (ranges.py:
"Button eroeffnet ~85 %, BB verteidigt ~70 %"). Die Nachtdiagnose 29./30.10. zeigte, dass die Suche damit
gegen ihr eigenes Blueprint-Netz verliert. Hier kommen die Ranges stattdessen aus dem Blueprint selbst
(Bayes mit der tatsaechlichen Strategie): die Hand wird mit der Engine von vorn nachgespielt, und bei jeder
Entscheidung eines der beiden Spieler wird fuer JEDE moegliche Starthand gefragt, mit welcher
Wahrscheinlichkeit das Netz genau diese Aktion gewaehlt haette. Das Produkt ueber alle Aktionen ist die
Range (preflop ueber die 169 Handklassen, danach auf die 1326 Kombinationen verteilt; postflop, wenn
gewuenscht, ueber alle Kombinationen ohne Boardkarten).

Fuer den eigenen Spieler ist das exakt (er spielt ja das Blueprint, wo nicht gesucht wird); fuer den Gegner
ist es die Annahme "er spielt wie unser Blueprint" - immer noch besser als eine Faustformel, weil das Netz
Stacktiefe, Blindstufe und Turnierlage kennt. Gegnermerkmale (feat-3) werden mit den Vorgabewerten belegt.

Strassen, die nicht vom Blueprint modelliert werden (Standard: alles nach dem Preflop), bekommen weiter die
Heuristik-Faktoren aus ranges.py. Passt der Verlauf nicht zur Engine (Live-Unsicherheit), liefert
blueprint_ranges None und die Suche faellt auf public_ranges zurueck.
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
    """Wahrscheinlichkeiten des Netzes fuer viele Situationen (Zeilen) mit gemeinsamer Aktionsmaske."""
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
    """Kartenstapel, dessen Board (Positionen 20-24) mit dem bekannten Board beginnt."""
    rest = [c for c in FULL_DECK if c not in board]
    full = list(board) + rest[: 5 - len(board)]
    remaining = rest[5 - len(board):]
    return remaining[:20] + full + remaining[20:]


def _blueprint_probs(w: dict, obs_t: Observation, act: Action, cards: list[list[str]]) -> np.ndarray:
    """P(act | Hand) fuer jede Handliste in `cards` in der Lage obs_t (ohne eigene Karten)."""
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
    """Ranges (Summe 1) von hero und opp zu BEGINN der aktuellen Strasse aus dem Blueprint-Netz.
    opp_weights: eigenes Netz fuer die Aktionen des GEGNERS (z. B. Menschenmodell human-1, H11); ohne
    Angabe gilt 'der Gegner spielt wie unser Blueprint'. None, wenn kein Netz da ist oder der Verlauf
    sich nicht nachspielen laesst."""
    w = getattr(blueprint, "w", None)
    if not isinstance(w, dict) or "w1" not in w:
        if not (bp_streets and set(bp_streets) <= {"eq"}):   # nur Gleichgewicht braucht kein Netz
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
    """opp_fold: humanfold.HumanFold - vor jeder (Nicht-Fold-)Aktion des Gegners wird seine Range mit der
    Weiterspiel-Wahrscheinlichkeit je Kombination multipliziert (die Haende, die ein Mensch hier weggelegt
    haette, verschwinden), danach bewertet opp_weights die gewaehlte Aktion."""
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
    eq = "eq" in bp_streets                 # Preflop aus dem Heads-up-Gleichgewicht (hupreflop) statt Netz/Heuristik
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
