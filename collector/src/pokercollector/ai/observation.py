"""The common interface: what a player sees (Observation) and what he does (Action).

The same observation is generated in the simulator, in replay of recorded hands, and live
from the collector. It contains only visible information: own cards, board,
stacks, bets, positions, and public action history - never opponents’ hidden cards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

STREETS = ("preflop", "flop", "turn", "river")


@dataclass(frozen=True)
class Action:
    kind: str                    # 'fold' | 'check' | 'call' | 'raise'
    amount: int | None = None    # only with 'raise': total bet on this street AFTER the action ("raise to")

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
    amount_to: int | None        # street bet afterwards
    added: int                   # additionally posted
    allin: bool = False


@dataclass
class Observation:
    seat: int                            # own seat
    num_seats: int
    hole_cards: list[str]                # own cards (empty if unknown)
    board: list[str]                     # visible board cards
    street: str
    button: int
    sb_seat: int | None
    bb_seat: int | None
    big_blind: int
    small_blind: int
    stacks: list[int]                    # current stacks (excluding already posted chips)
    bets: list[int]                      # bets on this street
    committed: list[int]                 # total bet in this hand (including bets)
    folded: list[bool]
    allin: list[bool]
    in_hand: list[bool]                  # has been dealt cards
    history: list[PublicAction]
    # legal amount, calculated by the dealer
    to_call: int                         # additionally required to call (capped by own stack)
    can_check: bool
    can_raise: bool
    min_raise_to: int | None
    max_raise_to: int | None
    hand_id: str = ""
    names: list[str | None] = field(default_factory=list)
    source: str = "sim"                  # 'sim' | 'replay' | 'live'
    uncertain: list[str] = field(default_factory=list)   # for replay/live: what is uncertain
    # tournament (None in cash game): level, sb, bb, hands_to_next_level, players_left,
    # start_players, average_stack, payouts (shares per place), hand_no
    tournament: dict | None = None

    @property
    def stack_bb(self) -> float:
        """Effective own stack (including chips already bet) in big blinds."""
        return (self.my_stack + self.my_bet) / self.big_blind if self.big_blind else float("inf")

    @property
    def pot(self) -> int:
        """Entire pot including all bets on the table."""
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
        """Opponents who can still act (not folded, not all-in)."""
        return sum(1 for s in range(self.num_seats)
                   if s != self.seat and self.in_hand[s] and not self.folded[s] and not self.allin[s])

    def position(self) -> int:
        """0 = button, 1 = cutoff, ... (distance counterclockwise from the button among players with cards).
        Higher = acts earlier."""
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
    """Makes an agent action legal (e.g., raise beyond stack -> all-in).
    Illegal intentions are mapped to the next legal action."""
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
    raise ValueError(f"unknown action: {action}")
