"""Suche waehrend des Spiels - Grundlage fuer Pluribus-artiges Vorausrechnen.

Pluribus' Staerke kam nicht allein aus seiner Grundstrategie ("Blueprint"), sondern aus der Suche:
in jeder Situation rechnet er die Hand ein Stueck weit voraus und verfeinert die Entscheidung.
Hier die Bausteine dafuer und eine erste, einfache Suche:

1. Glaubenszustand: Ranges der Gegner (ranges.py) -> daraus moegliche Gegnerkarten ziehen ("Welten").
2. world_from_obs(): aus der Beobachtung + gezogenen Karten einen vollstaendigen Spielstand der Engine
   bauen (Stacks zu Handbeginn, Button, Blinds, oeffentlicher Verlauf nachgespielt). Davon aus kann
   man jede Aktion ausprobieren (Hand.clone()).
3. SearchAgent (Stufe 1, "Rollout-Suche"): fuer jede erlaubte Aktion in vielen Welten die Hand mit der
   Blueprint-Strategie (einem unserer Netze) fuer ALLE Spieler zu Ende spielen; dieselben Welten fuer
   alle Aktionen (gepaarter Vergleich, weniger Rauschen). Gewaehlt wird die Aktion mit dem besten
   Mittelwert - nur wenn sie klar besser ist als die Wahl der Blueprint, sonst bleibt es bei dieser.

Unterschied zu Pluribus (spaetere Stufen): Pluribus loest an jeder Entscheidung ein begrenztes
Teilspiel mit CFR, wobei Gegner am Suchhorizont zwischen mehreren Fortsetzungsstrategien waehlen
duerfen (robust gegen Ausnutzung). Stufe 1 nimmt dagegen an, dass alle nach der Blueprint weiterspielen.
Die Bausteine 1 und 2 sind fuer beide Stufen dieselben.
"""

from __future__ import annotations

import random

import numpy as np

from ..poker import FULL_DECK
from .agents import BaseAgent, make_agent
from .cfr import abstract_mask
from .engine import Hand
from .features import N_ACTIONS, to_action
from .observation import Action, Observation, clamp_action
from .ranges import opponent_ranges, sample_hands

SEARCH_VERSION = "search-1"


def world_from_obs(obs: Observation, opp_hands: dict[int, list[str]], rng: random.Random,
                   hand_id: str = "world") -> Hand:
    """Vollstaendiger Spielstand, der fuer den Spieler obs.seat genauso aussieht wie obs.
    opp_hands: angenommene Karten der Gegner, die noch in der Hand sind; ausgestiegene Gegner bekommen
    beliebige freie Karten (sie spielen keine Rolle mehr). Kommende Boardkarten sind zufaellig."""
    n = obs.num_seats
    start = [obs.stacks[s] + obs.committed[s] for s in range(n)]
    used = set(obs.hole_cards) | set(obs.board) | {c for h in opp_hands.values() for c in h}
    rest = [c for c in FULL_DECK if c not in used]
    rng.shuffle(rest)
    it = iter(rest)
    deck: list[str | None] = [None] * 52
    for s in range(n):
        if not obs.in_hand[s]:
            continue
        cards = obs.hole_cards if s == obs.seat else opp_hands.get(s) or [next(it), next(it)]
        deck[2 * s], deck[2 * s + 1] = cards
    for k, c in enumerate(obs.board):
        deck[20 + k] = c
    deck = [c if c is not None else next(it) for c in deck]
    h = Hand(start, obs.button, obs.small_blind, obs.big_blind, deck=deck, hand_id=hand_id,
             names=list(obs.names) if obs.names else None, tournament=obs.tournament)
    for a in obs.history:
        if a.kind in ("post_sb", "post_bb"):
            continue
        if h.to_act != a.seat:
            raise ValueError(f"Verlauf passt nicht: {a} (Engine erwartet Platz {h.to_act})")
        if a.kind == "fold":
            act = Action.fold()
        elif a.kind == "check":
            act = Action.check()
        elif a.kind == "call":
            act = Action.call()
        else:
            act = Action.raise_to(a.amount_to)
        h.apply(a.seat, act)
    if h.done or h.to_act != obs.seat:
        raise ValueError("nachgebauter Spielstand ist nicht an der Stelle der Beobachtung")
    return h


def play_out(h: Hand, agents, seat: int) -> float:
    """Spielt die Hand mit den gegebenen Agenten (Liste je Platz oder ein Agent fuer alle) zu Ende.
    Ergebnis fuer `seat` in Big Blinds."""
    while not h.done:
        s = h.to_act
        obs = h.observation(s)
        a = agents[s] if isinstance(agents, list) else agents
        h.apply(s, clamp_action(obs, a.act(obs)))
    return h.record.results[seat].net / h.bb


class SearchAgent(BaseAgent):
    """Rollout-Suche ueber eine Blueprint-Strategie. last_q: geschaetzter Wert je Aktion (BB) - auch fuer
    Live-Empfehlungen nutzbar. min_gain: Mindestvorteil (BB) gegenueber der Blueprint-Wahl."""
    name = "search"

    def __init__(self, blueprint: str, worlds: int = 24, min_gain: float = 0.25, seed: int = 0,
                 name: str | None = None):
        super().__init__(seed, name)
        self.blueprint_spec = blueprint
        self.blueprint = make_agent(f"{blueprint}:bp", seed)
        self.worlds = worlds
        self.min_gain = min_gain
        self.last_q: np.ndarray | None = None
        self.searches = 0
        self.overrides = 0

    def act(self, obs: Observation) -> Action:
        bp_action = clamp_action(obs, self.blueprint.act(obs))
        mask = abstract_mask(obs)
        if len(obs.hole_cards) != 2 or mask.sum() <= 1:
            return bp_action
        rng = self.rng(obs)
        nrng = np.random.default_rng(rng.randrange(1 << 30))
        ranges = opponent_ranges(obs)
        # Kandidaten: die abstrahierten Aktionen und - falls nicht darunter - die Wahl der Blueprint
        idxs = [int(a) for a in np.flatnonzero(mask)]
        cands = [clamp_action(obs, to_action(obs, a)) for a in idxs]
        if bp_action not in cands:
            idxs.append(-1)
            cands.append(bp_action)
        bp_col = cands.index(bp_action)
        rows = []
        for k in range(self.worlds):
            hands = sample_hands(ranges, list(obs.hole_cards) + list(obs.board), nrng)
            if hands is None:
                continue
            try:
                world = world_from_obs(obs, hands, random.Random(rng.randrange(1 << 30)), hand_id=f"w{k}")
            except ValueError:
                return bp_action
            row = []
            for j, act in enumerate(cands):
                h = world.clone()
                h.hand_id = f"{obs.hand_id}|w{k}|c{j}"        # eigener Zufall je Fortsetzung
                h.apply(obs.seat, act)
                row.append(play_out(h, self.blueprint, obs.seat))
            rows.append(row)
        if len(rows) < 4:
            return bp_action
        vals = np.array(rows)                                 # Welten x Kandidaten, gleiche Welten je Spalte
        means = vals.mean(0)
        q = np.full(N_ACTIONS, -np.inf)
        for j, a in enumerate(idxs):
            if a >= 0:
                q[a] = means[j]
        self.last_q = q
        self.searches += 1
        best = int(np.argmax(means))
        if best == bp_col:
            return bp_action
        # Nur bei klarem Vorteil ueberstimmen: gepaarte Differenz pro Welt, Mittel > 2 Standardfehler
        d = vals[:, best] - vals[:, bp_col]
        se = d.std(ddof=1) / np.sqrt(len(d))
        if d.mean() < max(self.min_gain, 2.0 * se):
            return bp_action
        self.overrides += 1
        return cands[best]


def make_search_agent(params: str, seed: int = 0) -> SearchAgent:
    """'search?bp=pros-2@300,worlds=24' (bp = Netz-Lauf@Checkpoint; ',' oder '&' trennen - ',' ist cmd-sicher)."""
    kv = dict(p.partition("=")[::2] for p in params.replace(",", "&").split("&") if p)
    if "bp" not in kv:
        raise ValueError("search-Bot: 'search?bp=<lauf>@<ckpt>[&worlds=24&gain=0.25]'")
    return SearchAgent(f"nn?run={kv['bp']}", int(kv.get("worlds", 24)), float(kv.get("gain", 0.25)), seed)
