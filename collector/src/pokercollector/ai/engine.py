""" No-Limit Hold'em dealer for 2-10 players.

Rules:
- Blinds: SB to the left of the button, BB left of that. Heads-up: button = SB, acts preflop first
  and postflop last. Too short stacks post whatever they have (all-in).
- Minimum raise: raise at least the last full raise (at least 1 BB).
- An all-in below a full raise does not restart the betting round: Anyone who has already
  acted and only gets to act again due to this may only call or fold.
- Side pots by bet sizes; uncalled chips return automatically.
- Odd chips when splitting: to the first winner left of the button.
- Cards: seat i receives deck[2i], deck[2i+1]; board = deck[20:25]. Thus, with the same
  seed, every seat gets the same cards regardless of button position (important for
  duplicate evaluation).
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

from ..poker import FULL_DECK, evaluate
from .observation import Action, Observation, PublicAction, STREETS

ENGINE_VERSION = "nlhe-engine-1"

try:                                 # fast evaluation (numba), same ranking as poker.evaluate
    from ..fastpoker import HAVE_NUMBA, evaluate_fast
    _hand_value = evaluate_fast if HAVE_NUMBA else evaluate
except ImportError:                  # pragma: no cover
    _hand_value = evaluate


class IllegalAction(Exception):
    pass


@dataclass
class SeatResult:
    seat: int
    start_stack: int
    end_stack: int
    hole: list[str]
    showed: bool
    won: int

    @property
    def net(self) -> int:
        return self.end_stack - self.start_stack


@dataclass
class HandRecord:
    hand_id: str
    seed: int | None
    button: int
    sb_seat: int | None
    bb_seat: int | None
    blinds: tuple[int, int]
    board: list[str]
    actions: list[PublicAction]
    results: list[SeatResult]
    pots: list[dict]
    went_to_showdown: bool
    names: list[str | None] = field(default_factory=list)


class Hand:
    """A single hand. Flow: h = Hand(...); while not h.done: h.apply(seat, agent.act(h.observation(seat)))."""

    def __init__(self, stacks: list[int], button: int, small_blind: int, big_blind: int,
                 seed: int | None = None, deck: list[str] | None = None, hand_id: str = "",
                 names: list[str | None] | None = None, tournament: dict | None = None):
        n = len(stacks)
        self.tournament = tournament
        if not 2 <= n <= 10:
            raise ValueError('2 to 10 seats')
        self.n = n
        self.hand_id = hand_id
        self.seed = seed
        self.names = names or [None] * n
        self.sb, self.bb = small_blind, big_blind
        self.start = list(stacks)
        self.stacks = list(stacks)
        self.in_hand = [s > 0 for s in stacks]
        if sum(self.in_hand) < 2:
            raise ValueError('at least two players with chips')
        if not self.in_hand[button]:
            button = self._next(button, lambda s: self.in_hand[s])
        self.button = button
        if deck is None:
            deck = list(FULL_DECK)
            random.Random(seed).shuffle(deck)
        self.deck = deck
        self.hole = [deck[2 * i: 2 * i + 2] if self.in_hand[i] else [] for i in range(n)]
        self.full_board = deck[20:25]
        self.board: list[str] = []
        self.bets = [0] * n
        self.committed = [0] * n
        self.folded = [False] * n
        self.allin = [False] * n
        self.history: list[PublicAction] = []
        self.street = "preflop"
        self.current_bet = 0
        self.min_raise_inc = big_blind
        self.full_raise_level = 0            # Amount after last full raise
        self.acted = [False] * n
        self.acted_at_full_level = [-1] * n  # full_raise_level at last own action
        self.done = False
        self.to_act: int | None = None
        self.record: HandRecord | None = None
        self._post_blinds()

    # ---- Helpers ----------------------------------------------------------

    def clone(self) -> "Hand":
        """Fast copy of game state (CFR plays every own action from a point).
        Only the lists that change during play are copied."""
        h = copy.copy(self)
        for f in ("stacks", "bets", "committed", "folded", "allin", "history", "acted", "acted_at_full_level"):
            setattr(h, f, list(getattr(self, f)))
        return h

    def _next(self, seat: int, pred) -> int:
        for k in range(1, self.n + 1):
            s = (seat + k) % self.n
            if pred(s):
                return s
        raise RuntimeError('no suitable seat')

    def _can_act(self, s: int) -> bool:
        return self.in_hand[s] and not self.folded[s] and not self.allin[s]

    def _live(self) -> list[int]:
        return [s for s in range(self.n) if self.in_hand[s] and not self.folded[s]]

    def _put(self, s: int, amount: int) -> int:
        amount = min(amount, self.stacks[s])
        self.stacks[s] -= amount
        self.bets[s] += amount
        self.committed[s] += amount
        if self.stacks[s] == 0:
            self.allin[s] = True
        return amount

    def _post_blinds(self):
        players = sum(self.in_hand)
        if players == 2:
            self.sb_seat = self.button
            self.bb_seat = self._next(self.button, lambda s: self.in_hand[s])
        else:
            self.sb_seat = self._next(self.button, lambda s: self.in_hand[s])
            self.bb_seat = self._next(self.sb_seat, lambda s: self.in_hand[s])
        a = self._put(self.sb_seat, self.sb)
        self.history.append(PublicAction("preflop", self.sb_seat, "post_sb", self.bets[self.sb_seat], a,
                                         self.allin[self.sb_seat]))
        a = self._put(self.bb_seat, self.bb)
        self.history.append(PublicAction("preflop", self.bb_seat, "post_bb", self.bets[self.bb_seat], a,
                                         self.allin[self.bb_seat]))
        # Minimum bet remains a full BB, even if BB posted shorter all-in
        self.current_bet = max(self.bb, max(self.bets))
        self.full_raise_level = self.current_bet
        self.min_raise_inc = self.bb
        self.to_act = self.bb_seat
        self._advance(after=self.bb_seat)

    # ---- Player's perspective ---------------------------------------------

    def legal(self, s: int) -> dict:
        to_call = min(self.current_bet - self.bets[s], self.stacks[s])
        can_check = self.current_bet - self.bets[s] <= 0
        max_to = self.bets[s] + self.stacks[s]
        reopened = (not self.acted[s]) or self.acted_at_full_level[s] < self.full_raise_level
        others_can_act = any(self._can_act(o) for o in range(self.n) if o != s)
        can_raise = reopened and max_to > self.current_bet and others_can_act
        min_to = self.current_bet + self.min_raise_inc
        if can_raise and max_to < min_to:
            min_to = max_to  # only all-in possible now
        return {"to_call": max(0, to_call), "can_check": can_check, "can_raise": can_raise,
                "min_raise_to": min_to if can_raise else None, "max_raise_to": max_to if can_raise else None}

    def observation(self, s: int) -> Observation:
        lg = self.legal(s)
        return Observation(
            seat=s, num_seats=self.n, hole_cards=list(self.hole[s]), board=list(self.board),
            street=self.street, button=self.button, sb_seat=self.sb_seat, bb_seat=self.bb_seat,
            big_blind=self.bb, small_blind=self.sb, stacks=list(self.stacks), bets=list(self.bets),
            committed=list(self.committed), folded=list(self.folded), allin=list(self.allin),
            in_hand=list(self.in_hand), history=list(self.history), to_call=lg["to_call"],
            can_check=lg["can_check"], can_raise=lg["can_raise"], min_raise_to=lg["min_raise_to"],
            max_raise_to=lg["max_raise_to"], hand_id=self.hand_id, names=list(self.names), source="sim",
            tournament=dict(self.tournament) if self.tournament else None)

    # ---- Flow ------------------------------------------------------------

    def apply(self, s: int, action: Action):
        if self.done:
            raise IllegalAction('hand is finished')
        if s != self.to_act:
            raise IllegalAction(f"seat {s} is not to act (to act: {self.to_act})")
        lg = self.legal(s)
        before = self.bets[s]
        if action.kind == "fold":
            self.folded[s] = True
            kind, added = "fold", 0
        elif action.kind == "check":
            if not lg["can_check"]:
                raise IllegalAction('check not allowed, there is an open bet')
            kind, added = "check", 0
        elif action.kind == "call":
            if lg["can_check"]:
                raise IllegalAction('nothing to call - use check')
            added = self._put(s, lg["to_call"])
            kind = "call"
        elif action.kind == "raise":
            if not lg["can_raise"]:
                raise IllegalAction('raise not allowed')
            to = action.amount
            if to is None or to < lg["min_raise_to"] or to > lg["max_raise_to"]:
                raise IllegalAction(f"Raise to {to} outside [{lg['min_raise_to']}, {lg['max_raise_to']}]")
            added = self._put(s, to - before)
            inc = self.bets[s] - self.current_bet
            kind = "bet" if self.current_bet == 0 else "raise"
            if inc >= self.min_raise_inc:
                self.min_raise_inc = inc
                self.full_raise_level = self.bets[s]
            self.current_bet = self.bets[s]
        else:
            raise IllegalAction(f"unknown action {action.kind}")
        self.acted[s] = True
        self.acted_at_full_level[s] = self.full_raise_level
        self.history.append(PublicAction(self.street, s, kind, self.bets[s] if kind != "fold" else None,
                                         added, self.allin[s]))
        self._advance(after=s)

    def _needs_action(self, s: int) -> bool:
        if not self._can_act(s) or (self.acted[s] and self.bets[s] >= self.current_bet):
            return False
        others_can_act = any(self._can_act(o) for o in range(self.n) if o != s)
        if not others_can_act:
            # All others are all-in or out: Anyone who has already put in at least as much as every
            # other player must do nothing more (e.g. SB vs shorter all-in BB).
            top_other = max((self.bets[o] for o in self._live() if o != s), default=0)
            if self.bets[s] >= top_other:
                return False
        return True

    def _round_complete(self) -> bool:
        return not any(self._needs_action(s) for s in range(self.n))

    def _advance(self, after: int):
        live = self._live()
        if len(live) == 1:
            self._finish()
            return
        if not self._round_complete():
            self.to_act = self._next(after, self._needs_action)
            return
        # Street ended
        can_act = [s for s in live if not self.allin[s]]
        if self.street == "river" or len(can_act) <= 1:
            self._run_out()
            self._finish()
            return
        self._next_street()

    def _next_street(self):
        i = STREETS.index(self.street)
        self.street = STREETS[i + 1]
        self.board = self.full_board[: {"flop": 3, "turn": 4, "river": 5}[self.street]]
        self.bets = [0] * self.n
        self.current_bet = 0
        self.min_raise_inc = self.bb
        self.full_raise_level = 0
        self.acted = [False] * self.n
        self.acted_at_full_level = [-1] * self.n
        self.to_act = self._next(self.button, self._can_act)

    def _run_out(self):
        self.board = list(self.full_board)

    def _finish(self):
        self.done = True
        self.to_act = None
        live = self._live()
        showdown = len(live) > 1
        won = [0] * self.n
        pots = []
        levels = sorted({c for c in self.committed if c > 0})
        prev = 0
        for lvl in levels:
            amount = sum(min(c, lvl) - min(c, prev) for c in self.committed)
            eligible = [s for s in live if self.committed[s] >= lvl]
            prev_lvl, prev = prev, lvl
            if amount == 0:
                continue
            if not eligible:
                # Only folded players bet that much: uncovered chips go to the
                # contributor back (no living player could win them)
                for s in range(self.n):
                    won[s] += min(self.committed[s], lvl) - min(self.committed[s], prev_lvl)
                pots.append({"amount": amount, "eligible": [], "winners": [], "returned": True})
                continue
            if len(eligible) == 1:
                winners = eligible
            else:
                vals = {s: _hand_value(self.hole[s] + self.board) for s in eligible}
                best = max(vals.values())
                winners = [s for s in eligible if vals[s] == best]
            share, rest = divmod(amount, len(winners))
            order = sorted(winners, key=lambda s: (s - self.button - 1) % self.n)
            for k, s in enumerate(order):
                won[s] += share + (1 if k < rest else 0)
            if pots and pots[-1]["eligible"] == sorted(eligible):
                pots[-1]["amount"] += amount
            else:
                pots.append({"amount": amount, "eligible": sorted(eligible), "winners": sorted(winners)})
        for s in range(self.n):
            self.stacks[s] += won[s]
        assert sum(self.stacks) == sum(self.start), 'chips not received'
        results = [SeatResult(s, self.start[s], self.stacks[s], list(self.hole[s]),
                              showdown and s in live, won[s]) for s in range(self.n)]
        self.record = HandRecord(self.hand_id, self.seed, self.button, self.sb_seat, self.bb_seat,
                                 (self.sb, self.bb), list(self.board), list(self.history), results, pots,
                                 showdown, list(self.names))


def play_hand(agents: list, stacks: list[int], button: int, small_blind: int, big_blind: int,
              seed: int | None = None, hand_id: str = "", names=None, on_illegal: str = "clamp",
              tournament: dict | None = None) -> HandRecord:
    """Plays a hand with given agents (index = seat). Illegal actions
    are by default made legal ('clamp') or throw ('raise')."""
    from .observation import clamp_action

    h = Hand(stacks, button, small_blind, big_blind, seed=seed, hand_id=hand_id,
             names=names or [getattr(a, "name", None) for a in agents], tournament=tournament)
    while not h.done:
        s = h.to_act
        obs = h.observation(s)
        act = agents[s].act(obs)
        if on_illegal == "clamp":
            act = clamp_action(obs, act)
        h.apply(s, act)
    for i, a in enumerate(agents):
        cb = getattr(a, "hand_over", None)
        if cb:
            cb(h.record, i)
    return h.record
