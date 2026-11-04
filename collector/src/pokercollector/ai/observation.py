"""Die gemeinsame Schnittstelle: was ein Spieler sieht (Observation) und was er tut (Action).

Dieselbe Observation entsteht im Simulator, im Replay aufgezeichneter Haende und live
aus dem Collector. Sie enthaelt nur sichtbare Information: eigene Karten, Board,
Stacks, Einsaetze, Positionen und den oeffentlichen Aktionsverlauf - nie fremde
verdeckte Karten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

STREETS = ("preflop", "flop", "turn", "river")


@dataclass(frozen=True)
class Action:
    kind: str                    # 'fold' | 'check' | 'call' | 'raise'
    amount: int | None = None    # nur bei 'raise': Gesamteinsatz dieser Strasse NACH der Aktion ("raise auf")

    def __str__(self):
        return f"{self.kind} {self.amount}" if self.kind == "raise" else self.kind

    @staticmethod
    def fold() -> "Action":
        return Action("fold")

    @staticmethod
    def check() -> "Action":
        return Action("check")

    @staticmethod
    def call() -> "Action":
        return Action("call")

    @staticmethod
    def raise_to(amount: int) -> "Action":
        return Action("raise", int(amount))


@dataclass(frozen=True)
class PublicAction:
    street: str
    seat: int
    kind: str                    # post_sb, post_bb, fold, check, call, bet, raise
    amount_to: int | None        # Strasseneinsatz danach
    added: int                   # zusaetzlich gesetzt
    allin: bool = False


@dataclass
class Observation:
    seat: int                            # eigener Platz
    num_seats: int
    hole_cards: list[str]                # eigene Karten (leer, wenn unbekannt)
    board: list[str]                     # sichtbare Boardkarten
    street: str
    button: int
    sb_seat: int | None
    bb_seat: int | None
    big_blind: int
    small_blind: int
    stacks: list[int]                    # aktuelle Stacks (ohne bereits gesetzte Chips)
    bets: list[int]                      # Einsaetze dieser Strasse
    committed: list[int]                 # insgesamt in dieser Hand gesetzt (inkl. bets)
    folded: list[bool]
    allin: list[bool]
    in_hand: list[bool]                  # hat Karten bekommen
    history: list[PublicAction]
    # Rechtliches, vom Spielleiter berechnet
    to_call: int                         # zusaetzlich noetig zum Mitgehen (begrenzt durch eigenen Stack)
    can_check: bool
    can_raise: bool
    min_raise_to: int | None
    max_raise_to: int | None
    hand_id: str = ""
    names: list[str | None] = field(default_factory=list)
    source: str = "sim"                  # 'sim' | 'replay' | 'live'
    uncertain: list[str] = field(default_factory=list)   # bei replay/live: was unsicher ist
    # Turnier (None im Cash-Game): level, sb, bb, hands_to_next_level, players_left,
    # start_players, average_stack, payouts (Anteile je Platz), hand_no
    tournament: dict | None = None

    @property
    def stack_bb(self) -> float:
        """Effektiver eigener Stack (inkl. gesetzter Chips) in Big Blinds."""
        return (self.my_stack + self.my_bet) / self.big_blind if self.big_blind else float("inf")

    @property
    def pot(self) -> int:
        """Gesamter Pot inkl. aller Einsaetze auf dem Tisch."""
        return sum(self.committed)

    @property
    def my_stack(self) -> int:
        return self.stacks[self.seat]

    @property
    def my_bet(self) -> int:
        return self.bets[self.seat]

    @property
    def current_bet(self) -> int:
        return max(self.bets) if self.bets else 0

    @property
    def opponents_in_hand(self) -> int:
        return sum(1 for s in range(self.num_seats)
                   if s != self.seat and self.in_hand[s] and not self.folded[s])

    @property
    def active_opponents(self) -> int:
        """Gegner, die noch handeln koennen (nicht gefoldet, nicht all-in)."""
        return sum(1 for s in range(self.num_seats)
                   if s != self.seat and self.in_hand[s] and not self.folded[s] and not self.allin[s])

    def position(self) -> int:
        """0 = Button, 1 = Cutoff, ... (Abstand gegen den Uhrzeigersinn vom Button
        unter den Spielern mit Karten). Hoeher = frueher."""
        order = [(self.button - k) % self.num_seats for k in range(self.num_seats)]
        live = [s for s in order if self.in_hand[s]]
        return live.index(self.seat) if self.seat in live else -1

    def street_actions(self, street: str | None = None) -> list[PublicAction]:
        st = street or self.street
        return [a for a in self.history if a.street == st]

    def raises_this_street(self) -> int:
        return sum(1 for a in self.street_actions() if a.kind in ("bet", "raise"))

    def legal(self) -> list[str]:
        out = ["fold"]
        out.append("check" if self.can_check else "call")
        if self.can_raise:
            out.append("raise")
        return out


class Agent(Protocol):
    name: str

    def act(self, obs: Observation) -> Action:
        ...


def clamp_action(obs: Observation, action: Action) -> Action:
    """Macht eine Agentenaktion regelkonform (z. B. Raise ueber Stack -> All-in).
    Unzulaessige Absichten werden auf die naechste zulaessige Aktion abgebildet."""
    if action.kind == "fold":
        return Action.check() if obs.can_check else Action.fold()
    if action.kind in ("check", "call"):
        return Action.check() if obs.can_check else Action.call()
    if action.kind == "raise":
        if not obs.can_raise or obs.min_raise_to is None or obs.max_raise_to is None:
            return Action.check() if obs.can_check else Action.call()
        amt = action.amount if action.amount is not None else obs.min_raise_to
        amt = max(obs.min_raise_to, min(obs.max_raise_to, amt))
        return Action.raise_to(amt)
    raise ValueError(f"unbekannte Aktion: {action}")
