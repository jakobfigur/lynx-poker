"""Heads-up Preflop: Gleichgewicht per CFR+ ueber die 169 Starthand-Klassen, in jeder Entscheidung neu.

Gegen Slumbot zeigte sich das groesste Leck preflop (BB 3-bettet ~50 %, callt kaum). Hier wird der
Preflop-Baum heads-up geloest:

  Aktionen   SB: Fold, Limp, Open 2,5 BB, All-in.  BB gegen Limp: Check, Raise 4 BB, All-in.
             Gegen einen Raise: Fold, Call, Re-Raise (3-Bet 3x, 4-Bet 2,3x, solange < 45 % Stack), All-in.
             Die TATSAECHLICH gespielten Groessen der Hand werden als zusaetzliche Aeste eingefuegt -
             so passt der Baum immer zur echten Lage (keine Uebersetzung noetig).
  Showdown   All-in: exakte Equity (Matrix hand_vs_hand.json, Blocker exakt ueber Kombinationszahlen).
  Postflop   Pot wird nach "realisierter Equity" geteilt: der Spieler ohne Position (BB) realisiert weniger
             (Faktor 0,80 bei tiefen Stacks, schwache Haende zusaetzlich weniger: ALPHA, gegen 1 bei kleinem Stack-zu-Pot-Verhaeltnis).

Das ist ein Modell (Postflop nicht ausgespielt), aber es gibt die Grundform heads-up richtig vor:
breit eroeffnen, breit verteidigen, 3-Bets polarisiert und selten. Ergebnis wird je Stack und Verlauf
zwischengespeichert (Slumbot: immer 200 BB -> fast nur Cache-Treffer).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from .pushfold import CLASSES, IDX, matrix
from .tables import hand_class

HUPREFLOP_VERSION = "hupre-1"
OPEN_TO = 2.5
ISO_TO = 4.0
RERAISE = {1: 3.0, 2: 2.3, 3: 2.2}          # Faktor auf den Raise davor je Stufe (3-Bet, 4-Bet, 5-Bet)
MAX_FRACTION = 0.45                         # groessere Raises -> nur noch All-in
OOP_REALIZE = 0.80
ITERATIONS = 800
SAME_SIZE = 0.04                            # tatsaechliche Groesse innerhalb 4 % = vorhandener Ast


@dataclass
class Node:
    kind: str                               # 'dec' | 'fold' | 'post' | 'allin'
    c: tuple[float, float]                  # Einsaetze (BB) SB, BB
    player: int = -1                        # handelt (dec) bzw. foldet (fold)
    children: list = field(default_factory=list)
    labels: list = field(default_factory=list)     # (Art, auf BB)
    M0: np.ndarray | None = None            # Terminal: Nutzenmatrix aus SB-Sicht (gewichtet mit Kombis)
    regret: np.ndarray | None = None
    avg: np.ndarray | None = None


ALPHA = 1.3                                 # >1: starke Haende realisieren mehr, schwache weniger


def _realized_share(E: np.ndarray, spr: float) -> np.ndarray:
    """Anteil des SB (Button, hat Position) am Pot, wenn ohne All-in zum Flop gegangen wird."""
    deep = min(1.0, spr / 6.0)
    r_oop = 1.0 - (1.0 - OOP_REALIZE) * deep
    a = 1.0 + (ALPHA - 1.0) * deep
    e, f = E ** a, (1.0 - E) ** a
    return e / (e + f * r_oop)


def build(S: float, path: list[tuple[str, float]] = ()) -> tuple[Node, list[Node]]:
    """Baum fuer effektiven Stack S (BB). path: tatsaechliche Aktionen bisher (Art, auf BB).
    Rueckgabe: Wurzel und die Knoten entlang des Pfads (letzter = aktuelle Entscheidung)."""
    E, W = matrix()
    path = list(path)
    on_path: list[Node] = []

    def terminal(kind, c, folder=-1):
        n = Node(kind, c, folder)
        if kind == "fold":
            u0 = -c[0] if folder == 0 else c[1]
            n.M0 = W * u0
        else:
            pot = 2 * c[0]
            share = E if kind == "allin" else _realized_share(E, (S - c[0]) / pot)
            n.M0 = W * (share * pot - c[0])
        return n

    def dec(c, p, last_inc, raises, can_check, depth, matched):
        n = Node("dec", c, p)
        q = 1 - p
        acts: list[tuple[str, float]] = []
        to_call = c[q] - c[p]
        if to_call > 0:
            acts.append(("fold", c[p]))
            acts.append(("call", c[q]))
        else:
            acts.append(("check" if can_check else "call", c[q]))
        if c[q] < S:
            sizes = []
            if raises == 0 and p == 0 and c[q] == 1.0:
                sizes = [OPEN_TO]
            elif raises == 0:
                sizes = [ISO_TO]
            elif raises in RERAISE:
                sizes = [round(c[q] * RERAISE[raises], 2)]
            for x in sizes:
                if x < MAX_FRACTION * S and x >= c[q] + last_inc:
                    acts.append(("raise", x))
            acts.append(("raise", S))
        if matched and depth < len(path):
            kind, x = path[depth]
            if kind == "raise":
                x = min(x, S)
                if not any(k == "raise" and abs(v - x) <= SAME_SIZE * x for k, v in acts):
                    acts.append(("raise", x))
        for kind, x in acts:
            on = matched and depth < len(path) and _same(path[depth], (kind, x))
            if kind == "fold":
                child = terminal("fold", c, p)
            elif kind in ("call", "check"):
                cc = (c[q], c[q]) if p == 0 else (c[0], c[0])
                closes = to_call == 0 or not (raises == 0 and p == 0 and c[q] == 1.0)   # SB-Limp schliesst nicht
                if kind == "check" or closes:
                    child = terminal("allin" if cc[0] >= S else "post", cc)
                else:
                    child = dec(cc, q, 1.0, 0, True, depth + 1, on)
            else:
                cc = list(c)
                cc[p] = x
                cc = tuple(cc)
                child = dec(cc, q, x - c[q], raises + 1, False, depth + 1, on)
            n.children.append(child)
            n.labels.append((kind, x))
        if matched and depth == len(path):
            on_path.append(n)
        elif matched and depth < len(path):
            on_path.append(n)
        n.regret = np.zeros((len(acts), len(CLASSES)))
        n.avg = np.zeros((len(acts), len(CLASSES)))
        return n

    root = dec((0.5, 1.0), 0, 1.0, 0, False, 0, True)
    # Pfadknoten in Reihenfolge der Tiefe (dec haengt beim Rueckweg an -> umdrehen)
    return root, on_path[::-1]


def _same(a: tuple[str, float], b: tuple[str, float]) -> bool:
    ka, xa = a
    kb, xb = b
    if ka in ("call", "check") and kb in ("call", "check"):
        return True
    return ka == kb and (ka == "fold" or abs(xa - xb) <= SAME_SIZE * max(xa, xb))


def _sigma(n: Node) -> np.ndarray:
    r = np.maximum(n.regret, 0)
    s = r.sum(0)
    return np.where(s > 0, r / np.where(s > 0, s, 1), 1.0 / len(r))


def _walk(n: Node, r0, r1, upd: int, t: int) -> np.ndarray:
    if n.kind != "dec":
        return n.M0 @ r1 if upd == 0 else -(n.M0.T @ r0)
    sig = _sigma(n)
    if n.player == upd:
        own = r0 if upd == 0 else r1
        vals = np.array([_walk(ch, r0 * sig[i] if upd == 0 else r0, r1 * sig[i] if upd == 1 else r1, upd, t)
                         for i, ch in enumerate(n.children)])
        v = (sig * vals).sum(0)
        n.regret = np.maximum(n.regret + vals - v, 0)          # CFR+
        n.avg += t * own * sig
        return v
    return sum(_walk(ch, r0 * sig[i] if n.player == 0 else r0, r1 * sig[i] if n.player == 1 else r1, upd, t)
               for i, ch in enumerate(n.children))


def _avg(n: Node) -> np.ndarray:
    s = n.avg.sum(0)
    return np.where(s > 0, n.avg / np.where(s > 0, s, 1), 1.0 / len(n.avg))


def _br(n: Node, r0, r1, b: int) -> np.ndarray:
    if n.kind != "dec":
        return n.M0 @ r1 if b == 0 else -(n.M0.T @ r0)
    sig = _avg(n)
    if n.player == b:
        return np.max([_br(ch, r0, r1, b) for ch in n.children], axis=0)
    return sum(_br(ch, r0 * sig[i] if n.player == 0 else r0, r1 * sig[i] if n.player == 1 else r1, b)
               for i, ch in enumerate(n.children))


def solve(S: float, path=(), iterations: int = ITERATIONS):
    root, on_path = build(S, path)
    one = np.ones(len(CLASSES))
    for t in range(1, iterations + 1):
        for upd in (0, 1):
            _walk(root, one, one, upd, t)
    return root, on_path


def exploitability(root: Node) -> float:
    """(BR_SB + BR_BB) / 2 in BB je Hand (0 = Gleichgewicht)."""
    _, W = matrix()
    one = np.ones(len(CLASSES))
    tot = W.sum()
    return float((_br(root, one, one, 0).sum() + _br(root, one, one, 1).sum()) / tot / 2)


@lru_cache(maxsize=256)
def strategy(S2: int, path: tuple) -> tuple[list, np.ndarray]:
    """Strategie (Aktionen, Wahrscheinlichkeiten je Klasse) am aktuellen Knoten. S2 = Stack in halben BB."""
    root, on_path = solve(S2 / 2, list(path))
    node = on_path[-1] if on_path else root
    if len(on_path) != len(path) + 1:
        raise ValueError("Verlauf passt nicht in den Baum")
    return node.labels, _avg(node)


@lru_cache(maxsize=256)
def path_ranges(S2: int, path: tuple) -> tuple[np.ndarray, np.ndarray] | None:
    """Gleichgewichts-Ranges (169 Klassen, unnormiert, Prior 1 je Klasse) von SB und BB NACH dem Preflop-Verlauf
    `path`: Produkt der Durchschnittsstrategie-Wahrscheinlichkeiten der tatsaechlich gewaehlten Aktionen. Anders als
    strategy() darf der Pfad abgeschlossen sein (Call schliesst, es folgt der Flop). None, wenn er nicht in den
    Baum passt. Grundlage fuer die Suche im tiefen Cash-Format (ranges=eq): dort stimmt 'Gegner spielt wie unser
    Netz' nicht (Slumbot hus-4 30.10.), das Gleichgewicht ist der bessere Prior."""
    root, on_path = solve(S2 / 2, list(path))
    if len(on_path) < len(path):
        return None
    r = [np.ones(len(CLASSES)), np.ones(len(CLASSES))]
    for i, step in enumerate(path):
        node = on_path[i]
        j = next((k for k, lab in enumerate(node.labels) if _same(lab, step)), None)
        if j is None:
            return None
        r[node.player] = r[node.player] * _avg(node)[j]
    return r[0], r[1]


def stack_key(S: float) -> int:
    """Stack-Rasterung wie in decide(): halbe BB, ab 30 BB ganze, ab 60 BB Zweierschritte (Cache-Treffer)."""
    if S >= 60:
        return int(round(S / 2)) * 4
    if S >= 30:
        return int(round(S)) * 2
    return int(round(S * 2))


def equilibrium_ranges(obs) -> tuple[np.ndarray, np.ndarray] | None:
    """Gleichgewichts-Ranges (169 Klassen) von (SB, BB) zu Beginn der aktuellen Postflop-Strasse bzw. am
    aktuellen Preflop-Punkt, aus dem bisherigen Preflop-Verlauf. None, wenn nicht anwendbar."""
    path = history_path(obs)
    if path is None or obs.sb_seat is None or sum(obs.in_hand) != 2:
        return None
    S = effective_stack_bb(obs)
    if S < 1.5:
        return None
    key = tuple((k, round(x, 1)) for k, x in path)
    try:
        return path_ranges(stack_key(S), key)
    except ValueError:
        return None


def history_path(obs) -> list[tuple[str, float]] | None:
    """Preflop-Verlauf als (Art, auf BB); None, wenn es kein normales Heads-up-Preflop ist."""
    bb = obs.big_blind or 1
    out = []
    for a in obs.history:
        if a.street != "preflop" or a.kind in ("post_sb", "post_bb"):
            continue
        if a.kind == "fold":
            return None
        if a.kind in ("check", "call"):
            out.append((a.kind, 0.0))
        elif a.kind in ("bet", "raise"):
            out.append(("raise", round((a.amount_to or 0) / bb, 2)))
    return out


def effective_stack_bb(obs) -> float:
    live = [s for s in range(obs.num_seats) if obs.in_hand[s]]
    return min(obs.stacks[s] + obs.committed[s] for s in live) / (obs.big_blind or 1)


def decide(obs, rng) -> tuple[tuple[str, float], list, np.ndarray] | None:
    """Aktion (Art, auf BB) fuer die eigene Hand plus alle Aktionen/Wahrscheinlichkeiten, oder None."""
    path = history_path(obs)
    if path is None or obs.sb_seat is None:
        return None
    S = effective_stack_bb(obs)
    if S < 1.5:
        return None
    S2 = stack_key(S)
    key = tuple((k, round(x, 1)) for k, x in path)
    try:
        labels, avg = strategy(S2, key)
    except ValueError:
        return None
    me = 0 if obs.seat == obs.sb_seat else 1
    if len(path) % 2 != me:                   # SB handelt bei geradem Pfad, BB bei ungeradem
        return None
    p = avg[:, IDX[hand_class(obs.hole_cards)]]
    i = int(min(np.searchsorted(np.cumsum(p), rng.random(), side="right"), len(p) - 1))
    return labels[i], labels, p
