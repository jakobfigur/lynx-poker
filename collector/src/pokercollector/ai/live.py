""" Live connection Collector -> Bot: proposals with hand history and opponent model.

During the game a reconstructor runs (the same reconstruction as after the session):
- Every finished hand feeds the opponent model (opponents.OpponentTracker) - for the bot itself if it
  has one (networks from feat-3) and always in a separate copy for display.
- The history of the ongoing hand (who bet, raised, called) is part of the observation.
  Without it, the bot live would see no raises ahead.
Source remains exclusively what the collector recognized visually. Nothing is clicked.
The reconstruction can lag the reality by fractions of a second (late folds/bets);
this is then in Observation.uncertain.
"""

from __future__ import annotations

import threading
from dataclasses import replace

from ..reconstruct import Reconstructor
from .observation import Action, Observation, PublicAction
from .opponents import OpponentTracker
from .replay import observation_from_table_state

HISTORY_KINDS = ("post_sb", "post_bb", "fold", "check", "call", "bet", "raise")
SETTLE_S = 0.7          # how long the situation must be calm before a proposal appears
BUST_S = 20.0           # own stack 0 for so long without a new hand -> eliminated (all-in play out is shorter)
SAME_AMOUNT = 0.25      # new proposal of same kind within the same street only from 25% different amount


def fix_dollar_misreads(state: dict, chips: int | None) -> dict:
    """ Check implausible numbers in the image against tournament chips.
    1. '$1000' is occasionally read as 51000 (dollar sign as 5). A stack exceeding all tournament chips that
       starts with 5 and fits without the 5 is such a case.
    2. A bet that together with the stack of the same seat exceeds all chips is not a bet
       (29.10. evening: at final screen the winner stack '$13408' was read as bet from seat 5 and stayed
       throughout the next tournament in that state -> pot 13438 instead of 30 every hand, proposals worthless).
       It is set to unknown (counts as 0)."""
    if not chips:
        return state
    out = None
    for k, v in state.items():
        if k.startswith("seat.") and k.endswith((".stack", ".bet")) and isinstance(v, int) and v > 1.05 * chips:
            t = str(v)
            if t.startswith("5") and len(t) > 2 and 0 < int(t[1:]) <= 1.05 * chips:
                out = out if out is not None else dict(state)
                out[k] = int(t[1:])
    cur = out if out is not None else state
    for k, v in cur.items():
        if k.startswith("seat.") and k.endswith(".bet") and isinstance(v, int) and v > 0:
            stack = cur.get(k[:-4] + ".stack")
            if v + (stack if isinstance(stack, int) else 0) > 1.05 * chips:
                out = out if out is not None else dict(state)
                out[k] = None
    return out if out is not None else state


def drop_stale_bets(obs: Observation, hand: dict) -> Observation:
    """ Bets in the image that the current hand knows no action of the seat for are remnants of a previous
    hand (or foreign text in bet field, 29.10.: winner stack '$13408' at end screen stayed throughout next tournament).
    Every real bet causes an action in the reconstructor (including blinds). An unchanged blind produces no event,
    so amounts remain until the big blind or the highest bet in the hand."""
    acts = hand.get("actions") or []
    if not acts:
        return obs
    seen = {a.get("seat") for a in acts if a.get("type") not in ("fold", "check")}
    cap = max([obs.big_blind or 0] + [a.get("amount_to") or 0 for a in acts])
    stale = [s for s in range(obs.num_seats) if obs.bets[s] > cap and s not in seen]
    if not stale:
        return obs
    bets, committed = list(obs.bets), list(obs.committed)
    for s in stale:
        committed[s] -= bets[s]
        bets[s] = 0
    unc = list(obs.uncertain) + ['Bet without action in this hand ignored']
    to_call, can_check = obs.to_call, obs.can_check
    if 'Amount to call estimated from bets' in unc:      # otherwise it originates from the call button
        to_call = min(max(0, max(bets) - bets[obs.seat]), obs.stacks[obs.seat])
        can_check = to_call == 0
    return replace(obs, bets=bets, committed=committed, uncertain=unc, to_call=to_call, can_check=can_check)


def sane(sug, obs):
    """ Adjust proposal to the recognized situation: raise never beyond own stack (then all-in), raise not
    below/at highest bet (then call or check), and raise pointless if all opponents are already all-in."""
    if sug is None or sug.kind != "raise":
        return sug
    me = obs.seat
    top = max(obs.bets) if obs.bets else 0
    cap = obs.stacks[me] + obs.bets[me]
    others = [s for s in range(obs.num_seats) if s != me and obs.in_hand[s] and not obs.folded[s]]
    if others and all(obs.allin[s] for s in others):
        return Action("call") if obs.to_call > 0 else Action("check")
    if sug.amount is None or sug.amount <= top:
        return Action("call") if obs.to_call > 0 else Action("check")
    if cap > 0 and sug.amount > cap:
        return Action("raise", cap)
    return sug


def decision_buttons(buttons) -> bool:
    """ Action buttons offer call or check (only 'fold' = default)."""
    return any(b.get("action") in ("call", "check") for b in (buttons or []))


def is_decision(state: dict, hero_seat: int = 0) -> bool:
    """ It's your turn: own seat highlighted AND call/check buttons visible. Buttons alone
    are not enough (default selection, while others act), 'hero.to_act' often remains set persistently."""
    return state.get(f"seat.{hero_seat}.active") is True and decision_buttons(state.get("hero.buttons"))


def public_history(hand: dict, num_seats: int = 10) -> list[PublicAction]:
    """ Public history of a (ongoing) reconstructed hand in the engine format."""
    bets = [0] * num_seats
    stacks = {int(k): v.get("start_stack") for k, v in (hand.get("seats") or {}).items()}
    street = "preflop"
    out = []
    for a in hand.get("actions", []):
        if a["type"] not in HISTORY_KINDS:
            continue
        if a["street"] != street:
            street, bets = a["street"], [0] * num_seats
        s = a["seat"]
        if a["type"] == "fold":
            out.append(PublicAction(street, s, "fold", None, 0))
            continue
        if a["type"] == "check":
            out.append(PublicAction(street, s, "check", bets[s], 0))
            continue
        to = a.get("amount_to") if a.get("amount_to") is not None else bets[s] + (a.get("added") or 0)
        added = to - bets[s]
        bets[s] = to
        if stacks.get(s) is not None:
            stacks[s] -= added
        allin = bool(a.get("allin")) or (stacks.get(s) is not None and stacks[s] <= 0)
        out.append(PublicAction(street, s, a["type"], to, added, allin))
    return out


def _alive(si: dict, key: str) -> bool | None:
    v = si.get(key)
    return None if v is None else v > 0


class TournamentWatch:
    """ Detects tournament end from completed reconstructed hands (image content only):
    - own stack after hand 0 -> eliminated; place = 1 + opponents still having chips.
      Confirmed once next hand starts without own chips or session ends (a single OCR dropout '0' should not end tournament).
    - only self has chips left -> place 1.
    - final screen: after last all-in often neither stacks nor winner visible. Then counts if
      a stack in image shows all tournament chips (sum of starting stacks, ±3%): own -> place 1,
      another -> place 2.
    - own stack 0 for BUST_S seconds without new hand starting (PokerTH often stops dealing after elimination)
      -> eliminated; place = 1 + opponents with chips in image.
    - two consecutive hands without own chips (after a hand with chips) -> eliminated, even if elimination itself
      not visible.
    Results are reported at most once per game (info.game_hand)."""

    def __init__(self, hero_seat: int = 0):
        self.hero = hero_seat
        self.game = None
        self.field = 0
        self.first_hand_no = None
        self.hands = 0
        self.reported = False
        self.pending: dict | None = None
        self.chips: int | None = None          # all chips in tournament (sum of starting stacks)
        self.missing = 0                       # consecutive hands without own chips
        self.last: dict | None = None
        self.zero_since: tuple | None = None   # (time, hand, opponent) since own stack shows 0
        self.last_no = None                    # last seen hand number (jump back = new game)
        self.pending_since: float | None = None
        self.before: dict[int, int] = {}       # stack+bet per seat, last when self still showed chips
        self.missing_place = 0

    def _reset(self, game):
        self.game, self.field, self.first_hand_no, self.hands = game, 0, None, 0
        self.reported, self.pending, self.chips, self.missing, self.last = False, None, None, 0, None
        self.last_no, self.pending_since, self.zero_since, self.before, self.missing_place = None, None, None, {}, 0

    def _result(self, place: int, last: dict) -> dict:
        self.reported, self.pending = True, None
        missed = self.first_hand_no is not None and self.first_hand_no > 1
        return {"platz": place, "spieler": max(self.field, place), "haende": self.hands, "spiel": self.game,
                "letzte_hand": last.get("hand_no"), "start_verpasst": missed}

    def on_hand(self, h: dict) -> dict | None:
        """ A finished hand (Reconstructor dict). Gives a result as soon as it is determined."""
        game = h.get("game_no")
        no = h.get("hand_no")
        seats = {int(k): v for k, v in (h.get("seats") or {}).items()}
        starts = [si.get("start_stack") for si in seats.values()]
        equal_starts = (len(seats) >= 2 and all(isinstance(v, int) and v > 0 for v in starts)
                        and len(set(starts)) == 1)
        # Jump back of hand number = new game, but only plausible (number 1/2 or all stacks equal):
        # a single OCR reader '12' -> '1' may not reset count
        restart = (no is not None and self.last_no is not None and no < self.last_no
                   and (no <= 2 or equal_starts))
        if (game is not None and game != self.game) or restart:
            out = self.flush()                     # new game: open result of old one applies
            self._reset(game)
            if out:
                return out
        if no is not None:
            self.last_no = no
        if self.reported:
            return None
        me = seats.get(self.hero)
        start_alive = [s for s, si in seats.items() if _alive(si, "start_stack")]
        me_alive = me is not None and bool(_alive(me, "start_stack"))
        if self.pending is not None:
            # Starting stacks of next hand are settled (wins after hand change credited)
            if not me_alive:
                return self._result(1 + sum(1 for s in start_alive if s != self.hero), self.pending["hand"])
            self.pending, self.pending_since = None, None   # still has chips or opponents present: reading error
        if not me_alive:
            if self.hands:
                self.missing += 1
                if self.missing == 1:
                    self.missing_place = 1 + sum(1 for s in start_alive if s != self.hero)
                if self.missing >= 2:
                    return self._result(self.missing_place, self.last or h)
            return None                             # not (any longer) present or unknown
        self.missing = 0
        self.last = h
        self.hands += 1
        if self.chips is None and len(seats) >= 2 and all(isinstance(v, int) and v > 0 for v in starts) \
                and ((no is not None and no <= 2) or equal_starts):
            self.chips = sum(starts)        # only if all seats are definitely read (tournament start)
        self.field = max(self.field, len(start_alive))
        if self.first_hand_no is None:
            self.first_hand_no = h.get("hand_no")
        end_alive = {s: _alive(si, "end_stack") for s, si in seats.items()}
        if end_alive.get(self.hero) is False:
            others = sum(1 for s, a in end_alive.items() if s != self.hero and a is not False)
            self.pending = {"platz": others + 1, "hand": h}
        elif end_alive.get(self.hero) and len(seats) >= 2 and all(a is False for s, a in end_alive.items()
                                                                 if s != self.hero):
            self.pending = {"platz": 1, "hand": h}  # confirmed after BUST_S without a new hand (on_state) or at the end
            self.pending_since = None
        return None

    def on_state(self, state: dict, now: float | None = None) -> dict | None:
        """Table state after each event: if one stack shows all chips of the tournament, it is over; if
        one's own stack remains 0 for BUST_S seconds without a new hand, one is eliminated."""
        if self.reported or not self.hands:
            return None
        opp_chips = [int(k.split(".")[1]) for k, v in state.items() if k.startswith("seat.")
                     and k.endswith(".stack") and isinstance(v, int) and v > 0 and int(k.split(".")[1]) != self.hero
                     and state.get(k[:-len("stack")] + "present") is True]
        if self.pending is not None and self.pending["platz"] == 1 and opp_chips:
            # The all-in winner was still at 0 during the hand change (pot will be credited later): no win
            self.pending, self.pending_since = None, None
        if now is not None and self.pending is not None and self.pending["platz"] == 1:
            if self.pending_since is None:
                self.pending_since = now
            elif now - self.pending_since >= BUST_S:
                return self._result(1, self.pending["hand"])
        mine = state.get(f"seat.{self.hero}.stack")
        hand = state.get("info.game_hand")
        if now is not None:
            # 0 read, then often nothing more (table gone): unreadable keeps the timer running
            if mine == 0 or (mine is None and self.zero_since is not None):
                if self.zero_since is None or self.zero_since[1] != hand:
                    # Count opponents NOW (then the table often disappears): PokerTH clears eliminated players from
                    # the table, those still sitting are present - even if their stack currently shows 0 (own all-in)
                    # Those who just had chips count (an all-in winner briefly shows no panel)
                    seated = {int(k.split(".")[1]) for k, v in state.items() if k.startswith("seat.")
                              and k.endswith(".present") and v is True}
                    seated |= {s for s, v in self.before.items() if v > 0}
                    # ... and those who still had chips after the last completed hand (stack just unreadable/all-in)
                    after_last = {int(k) for k, si in ((self.last or {}).get("seats") or {}).items()
                                  if (si.get("end_stack") or 0) > 0
                                  or (si.get("end_stack") is None and (si.get("start_stack") or 0) > 0)}
                    others = max(len(seated - {self.hero}), len(after_last - {self.hero}))
                    opp = [int(k.split(".")[1]) for k, v in state.items() if k.startswith("seat.")
                           and k.endswith(".present") and v is True and int(k.split(".")[1]) != self.hero]
                    self.zero_since = (now, hand, others, opp[0] if len(opp) == 1 else None)
                elif now - self.zero_since[0] >= BUST_S:
                    opp = self.zero_since[3]
                    me, them = self.before.get(self.hero), self.before.get(opp) if opp is not None else None
                    if opp is not None and me and them and me > them:
                        # Heads-up all-in, you cover the opponent: only he can be eliminated -> won (the
                        # end screen comes before the pot is credited)
                        return self._result(1, self.last or {})
                    return self._result(1 + self.zero_since[2], self.last or {})
            elif isinstance(mine, int):
                self.zero_since = None
                self.before = {}
                for k, v in state.items():
                    if k.startswith("seat.") and k.endswith(".stack") and isinstance(v, int)                             and state.get(k[:-len("stack")] + "present") is True:
                        bet = state.get(k[:-len("stack")] + "bet")
                        self.before[int(k.split(".")[1])] = v + (bet if isinstance(bet, int) else 0)
        if not self.chips:
            return None
        lo, hi = 0.97 * self.chips, 1.03 * self.chips
        for k, v in state.items():
            if k.startswith("seat.") and k.endswith(".stack") and isinstance(v, int) and lo <= v <= hi:
                seat = int(k.split(".")[1])
                # ±3% only if no one else shows chips (opponent still has 150 in the middle of the hand)
                others_have = [s for s in opp_chips if s != seat] or (
                    [self.hero] if seat != self.hero and isinstance(mine, int) and mine > 0 else [])
                if v == self.chips or not others_have:
                    return self._result(1 if seat == self.hero else 2, self.last or {})
        return None

    def activity(self, field: str, value) -> None:
        """Opponent’s play activity (bet, highlighting, action label) or own buttons: the hand
        is still running, the elimination timer (own stack 0 after all-in) must not continue counting."""
        if not value or self.zero_since is None:
            return
        parts = field.split(".")
        if field == "hero.buttons" or (len(parts) == 3 and parts[0] == "seat" and parts[1] != str(self.hero)
                                       and parts[2] in ("bet", "active", "action_label")):
            self.zero_since = None

    def flush(self) -> dict | None:
        """Session end: an yet unconfirmed elimination counts."""
        if self.pending is not None and not self.reported:
            return self._result(self.pending["platz"], self.pending["hand"])
        return None


class LiveBot:
    def __init__(self, agent, hero_seat: int = 0, num_seats: int = 10, on_result=None):
        self.agent = agent
        self.watch = TournamentWatch(hero_seat)
        self.on_result = on_result
        self.hero = hero_seat
        self.n = num_seats
        self.rec = Reconstructor(num_seats)
        self.tracker = OpponentTracker(fuzzy=True)   # for display (and bots without own model)
        if getattr(agent, "tracker", None) is not None:
            agent.tracker.fuzzy = True                # live: merge noisy names
        self.done = 0
        self.deciding = False
        self.last_key = None
        self.last_shown: tuple | None = None      # (hand, street, type, amount) of the last shown suggestion
        self.pending_since: float | None = None
        self.state: dict = {}
        self._lock = threading.RLock()            # on_event/poll come from analysis and main thread

    def _relevant(self, f: str) -> bool:
        """Fields that, when changed, cause a suggestion to be recalculated while it’s your turn."""
        return (f.startswith("board.") or f in (f"seat.{self.hero}.cards", f"seat.{self.hero}.stack")
                or f.endswith(".bet") or f in ("info.game_hand", "pot.total", "info.street")
                or f.endswith(".folded"))

    def on_event(self, ev: dict, state: dict, now: float):
        """Process one event (now = time in seconds, same clock as poll()).
        Buttons indicate whether it’s your turn. Cards, board, and bets are sometimes recognized only shortly
        after the buttons; therefore, a suggestion appears only when the state SETTLE_S is calm
        (poll), and is recalculated if anything changes afterwards."""
        with self._lock:
            self.feed(ev)
            self.state = state
            f = ev.get("field", "")
            self.watch.activity(f, ev.get("new"))
            was = self.deciding
            #Table gone: old buttons/highlighting remain in state but do not count
            self.deciding = state.get("table.found") is not False and is_decision(state, self.hero)
            if not self.deciding:
                self.pending_since = None
                self.last_key = None
            elif not was or f == "hero.buttons" or self._relevant(f):
                self.pending_since = now
            return self.poll(now)

    def poll(self, now: float):
        """Returns (suggestion, observation, opponents) as soon as a new decision situation is calm, otherwise None.
        Called on every analyzed image - even without new events (e.g., after own elimination)."""
        with self._lock:
            res = self.watch.on_state(self.state, now)
            if res and self.on_result:
                self.on_result(res)
            if not self.deciding or self.pending_since is None or now - self.pending_since < SETTLE_S:
                return None
            if not self.playable(self.state):
                return None                               #pending_since remains: next image checks again
            self.pending_since = None
            obs = self.observation(self.state)
            # cheap checks BEFORE the agent (the search calculates seconds)
            if not obs.hole_cards:
                return None                               # no own cards (e.g., already folded)
            if set(obs.hole_cards) & set(obs.board) or len(obs.board) not in (0, 3, 4, 5):
                return None                               # intermediate state (e.g., hand change)
            if not any(obs.in_hand[s] and not obs.folded[s] for s in range(obs.num_seats) if s != obs.seat):
                return None                               # everyone else folded: hand won, nothing to do
            sug = sane(self.agent.act(obs), obs)
            key = (obs.hand_id, tuple(obs.hole_cards), tuple(obs.board), obs.to_call, str(sug))
            if key == self.last_key or self.same_as_shown(sug, obs):
                return None
            self.last_key = key
            self.last_shown = (obs.hand_id, tuple(obs.hole_cards), obs.street, sug.kind,
                               sug.amount if sug.kind == "raise" else obs.to_call)
            return sug, obs, self.opponents(obs)

    def playable(self, state: dict) -> bool:
        """Only real decisions: table recognized and own stack readable > 0. After own all-in, after
        hand end (end screen, table gone), and with unreadable stack there is no suggestion."""
        if state.get("table.found") is False:
            return False
        st = state.get(f"seat.{self.hero}.stack")
        return isinstance(st, int) and st > 0

    def same_as_shown(self, sug, obs) -> bool:
        """Same street, same type, amount barely different: do not retrigger the bar (no flickering
        due to lagging bets/pots)."""
        if self.last_shown is None or sug is None:
            return False
        hand, cards, street, kind, amount = self.last_shown
        #Cards also in the key: the hand number sometimes is not newly read across multiple hands
        if (hand, cards, street, kind) != (obs.hand_id, tuple(obs.hole_cards), obs.street, sug.kind):
            return False
        # Amount: for a raise the target amount, otherwise the amount to call (a re-raise of the opponent is a
        # new decision, even if the answer is again 'Call')
        cur = sug.amount if kind == "raise" else obs.to_call
        return abs((cur or 0) - (amount or 0)) <= SAME_AMOUNT * max(cur or 0, amount or 0, 1)

    def feed(self, ev: dict):
        """Every collector event (as in observations.jsonl) in input order."""
        if "seq" not in ev:
            return
        self.rec.feed(ev)
        self._drain()

    def _drain(self):
        while self.done < len(self.rec.hands):
            h = self.rec.hands[self.done].to_dict()
            self.done += 1
            self.tracker.update_collector(h, self.hero)
            own = getattr(self.agent, "tracker", None)
            if own is not None:
                own.update_collector(h, self.hero)
            res = self.watch.on_hand(h)
            if res and self.on_result:
                self.on_result(res)

    def close(self):
        """Session end: finish open hand and report an unconfirmed result."""
        with self._lock:
            if self.rec.hand is not None:
                self.rec.finish()
                self._drain()
            res = self.watch.flush()
            if res and self.on_result:
                self.on_result(res)

    def session_ended(self):
        """Recording ended (table gone for longer): report open result, restart reconstruction fresh for next
        recording. A running elimination timer counts as expired (table is gone)."""
        with self._lock:
            w = self.watch
            self.close()
            if w.zero_since is not None and not w.reported and w.hands:
                res = w.on_state(self.state, w.zero_since[0] + BUST_S)
                if res and self.on_result:
                    self.on_result(res)
            self.rec = Reconstructor(self.n)
            self.done = 0
            self.state = {}
            self.deciding, self.pending_since, self.last_key = False, None, None

    def observation(self, state: dict) -> Observation:
        state = fix_dollar_misreads(state, self.watch.chips)
        obs = observation_from_table_state(state, self.hero, self.n)
        by_board = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}.get(len(obs.board))
        if by_board and by_board != obs.street:          # Street display lags behind, board cards do not
            obs = replace(obs, street=by_board)
        h = self.rec.hand
        if h is None:
            return obs
        hd = h.to_dict()
        hist = public_history(hd, self.n)
        order = ("preflop", "flop", "turn", "river")
        if hist and order.index(hist[-1].street) > order.index(obs.street):
            return obs                            # Reconstruction and image differ: better without history
        unc = [u for u in obs.uncertain if u != 'Action history not included live']
        unc.append('History from live reconstruction (may lag slightly)')
        obs = drop_stale_bets(obs, hd)
        committed = obs.committed
        hist_pot = sum(a.added for a in hist)
        if hist_pot > 0 and obs.pot < 0.9 * hist_pot:
            # Pot missing or too small in image (e.g., 'Total: $O'): take from reconstructed history
            committed = list(obs.bets)
            committed[obs.button] += max(0, hist_pot - sum(obs.bets))
            unc = [u for u in unc if u != 'Pot unknown or inconsistent'] + ['Pot from live history']
        return replace(obs, history=hist, uncertain=unc, committed=committed)

    def opponents(self, obs: Observation) -> list[tuple[str, dict]]:
        """Opponents in hand with their statistics (name, values) for display."""
        out = []
        for s in range(obs.num_seats):
            if s != obs.seat and obs.in_hand[s] and not obs.folded[s]:
                key = self.tracker._key(obs.names, s)
                out.append((key, self.tracker.stats(key)))
        return out

    def suggest(self, state: dict):
        obs = self.observation(state)
        if not obs.hole_cards:
            return None, obs
        return self.agent.act(obs), obs


def replay_session(events: list[dict], agent, hero_seat: int = 0):
    """Plays a recorded session as live: returns every suggestion that would have been seen live
    (suggestion, observation, opponent list, event). State = fields up to this event."""
    bot = LiveBot(agent, hero_seat)
    state: dict = {}
    # like live: order of journal (seq), only stable values ('change') or unreadable ('unknown')
    usable = [e for e in events if "seq" in e and e.get("kind") in ("change", "unknown")]
    for ev in sorted(usable, key=lambda e: e["seq"]):
        t = ev.get("t_first", 0.0)
        out = bot.poll(t)                     # Rest time elapsed since last event?
        if out:
            yield (*out, ev)
        state[ev["field"]] = ev.get("new") if ev.get("kind") == "change" else None
        out = bot.on_event(ev, dict(state), t)
        if out:
            yield (*out, ev)
    out = bot.poll(float("inf"))
    if out:
        yield (*out, {"seq": "Ende"})
