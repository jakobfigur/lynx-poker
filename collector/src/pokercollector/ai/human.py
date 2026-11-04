"""You as player: Terminal interface over the same Observation/Action interface.

Inputs:  f = Fold   c/k = Call or Check   r 120 = Raise to 120   r = Minimum raise
           p = Pot-raise   a = All-in   ? = Help   q = Quit session
You see only what a player at the table sees. Opponents’ cards appear only at showdown.
"""

from __future__ import annotations

from .observation import Action, Observation

SUIT_SYM = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
SUIT_ASCII = {"s": "s", "h": "h", "d": "d", "c": "c"}
KIND_DE = {"post_sb": 'posts Small Blind', "post_bb": 'posts Big Blind', "fold": "foldet", "check": "checkt",
           "call": "callt", "bet": "setzt", "raise": 'raises to'}


class QuitGame(Exception):
    pass


class HumanAgent:
    def __init__(self, name: str = "du", input_fn=input, output_fn=print, ascii_only: bool = False,
                 coach: bool = False):
        self.name = name
        self.input = input_fn
        self.out = output_fn
        self.ascii = ascii_only
        self.coach = coach
        self._shown: dict[str, int] = {}
        self._last_hand = None

    # ---- Display -------------------------------------------------------

    def card(self, c: str | None) -> str:
        if not c:
            return "[  ]"
        sym = (SUIT_ASCII if self.ascii else SUIT_SYM)[c[1]]
        r = "10" if c[0] == "T" else c[0]
        return f"[{r}{sym}]"

    def cards(self, cs) -> str:
        return " ".join(self.card(c) for c in cs)

    def _seat_name(self, obs_or_rec, s: int) -> str:
        nm = obs_or_rec.names[s] if obs_or_rec.names and s < len(obs_or_rec.names) else None
        return nm or f"Seat {s}"

    def _show_new_actions(self, hand_id: str, history, names_src, upto: int | None = None):
        start = self._shown.get(hand_id, 0)
        hist = history[: upto] if upto is not None else history
        street = None if start == 0 else hist[start - 1].street if start <= len(hist) else None
        for a in hist[start:]:
            if a.street != street:
                street = a.street
                if a.street != "preflop":
                    self.out(f"  --- {a.street.upper()} ---")
            amt = f" {a.amount_to}" if a.kind in ("post_sb", "post_bb", "bet", "raise") else ""
            if a.kind == "call":
                amt = f" ({a.added})"
            self.out(f"  {self._seat_name(names_src, a.seat):14s} {KIND_DE.get(a.kind, a.kind)}{amt}"
                     f"{'  ALL-IN' if a.allin else ''}")
        self._shown[hand_id] = len(hist)

    def render(self, obs: Observation):
        if obs.hand_id != self._last_hand:
            self._last_hand = obs.hand_id
            t = obs.tournament
            head = f"Hand {obs.hand_id}  Blinds {obs.small_blind}/{obs.big_blind}"
            if t:
                head += f"  Level {t.get('level', 0) + 1} (still {t.get('hands_to_next_level')} hands)" \
                        f"  {t.get('players_left')} players remaining"
            self.out("")
            self.out("=" * 72)
            self.out(head)
            self.out("=" * 72)
            self.out(f"Your cards: {self.cards(obs.hole_cards)}")
        self._show_new_actions(obs.hand_id, obs.history, obs)
        self.out("")
        board = obs.board + [None] * (5 - len(obs.board))
        self.out(f"Board: {self.cards(board)}     Pot: {obs.pot}")
        for s in range(obs.num_seats):
            if not obs.in_hand[s] and obs.stacks[s] == 0:
                continue
            mark = "▶" if s == obs.seat and not self.ascii else (">" if s == obs.seat else " ")
            role = []
            if s == obs.button:
                role.append("D")
            if s == obs.sb_seat:
                role.append("SB")
            if s == obs.bb_seat:
                role.append("BB")
            state = "folded" if obs.folded[s] else ("ALL-IN" if obs.allin[s] else "")
            bet = f"Bet {obs.bets[s]}" if obs.bets[s] else ""
            self.out(f" {mark} {self._seat_name(obs, s):14s} {obs.stacks[s]:>7}  {bet:14s} "
                     f"{'/'.join(role):6s} {state}")
        self.out(f"Your cards: {self.cards(obs.hole_cards)}   Stack {obs.my_stack} "
                 f"({obs.stack_bb:.1f} BB)")

    def _prompt(self, obs: Observation) -> str:
        parts = ["[f]old"]
        parts.append('[k] check' if obs.can_check else f"[c] call {obs.to_call}")
        if obs.can_raise:
            parts.append(f"[r <amount>] raise to {obs.min_raise_to}..{obs.max_raise_to}")
            parts.append('[p] pot')
            parts.append(f"[a] all-in {obs.max_raise_to}")
        return "  ".join(parts) + '  [?] [q] > '

    # ---- Decision --------------------------------------------------------

    def act(self, obs: Observation) -> Action:
        self.render(obs)
        while True:
            raw = self.input(self._prompt(obs)).strip().lower()
            try:
                action = self.parse(raw, obs)
            except ValueError as e:
                self.out(f"  ! {e}")
                continue
            if action is None:
                self.out(__doc__)
                continue
            if self.coach:
                self._coach(obs, action)
            return action

    def parse(self, raw: str, obs: Observation) -> Action | None:
        if raw in ("q", "quit", "exit"):
            raise QuitGame()
        if raw in ("?", "h", "hilfe", "help"):
            return None
        if raw in ("f", "fold"):
            return Action.fold()
        if raw in ("k", "check"):
            if not obs.can_check:
                raise ValueError(f"Check not allowed, {obs.to_call} is to call - 'c' to call")
            return Action.check()
        if raw in ("c", "call", ""):
            return Action.check() if obs.can_check else Action.call()
        if raw in ("a", "allin", "all-in"):
            if not obs.can_raise:
                return Action.check() if obs.can_check else Action.call()
            return Action.raise_to(obs.max_raise_to)
        if raw in ("p", "pot"):
            if not obs.can_raise:
                raise ValueError('Raise is not allowed here')
            target = obs.current_bet + obs.pot + obs.to_call
            return Action.raise_to(max(obs.min_raise_to, min(obs.max_raise_to, target)))
        if raw.startswith("r"):
            if not obs.can_raise:
                raise ValueError('Raise is not allowed here')
            rest = raw[1:].strip()
            if not rest:
                return Action.raise_to(obs.min_raise_to)
            if not rest.isdigit():
                raise ValueError("Specify amount as number, e.g. 'r 120'")
            amt = int(rest)
            if not obs.min_raise_to <= amt <= obs.max_raise_to:
                raise ValueError(f"Raise must be between {obs.min_raise_to} and {obs.max_raise_to}")
            return Action.raise_to(amt)
        raise ValueError(f"unknown input '{raw}' - '?' for help")

    def _coach(self, obs: Observation, action: Action):
        """Subsequent hint in push/fold situations (only AFTER your decision)."""
        from .recording import PF_MAX_BB, classify_pf_choice
        from .agents import push_fold_spot
        from .observation import clamp_action
        from .pushfold import decision_ev
        if obs.street != "preflop" or obs.stack_bb > PF_MAX_BB:
            return
        spot = push_fold_spot(obs)
        chose = classify_pf_choice(obs, clamp_action(obs, action), spot) if spot["kind"] != "other" else None
        if not chose:
            return
        ev = decision_ev(obs.hole_cards, spot, chose)
        if ev and ev["ev_loss"] > 0.01:
            self.out(f"  Coach: Nash would play {ev['best']} here ({ev['hand']}, {ev['stack_bb']:g} BB). "
                     f"Your {chose} costs approx. {ev['ev_loss']:.2f} BB.")
        elif ev:
            self.out(f"  Coach: {chose} with {ev['hand']} fits Nash strategy.")

    def hand_over(self, rec, seat: int):
        self._show_new_actions(rec.hand_id, rec.actions, rec)
        if len(rec.board) > 0:
            self.out(f"  Board: {self.cards(rec.board)}")
        for r in rec.results:
            if r.showed:
                self.out(f"  {self._seat_name(rec, r.seat):14s} shows {self.cards(r.hole)}")
        for p in rec.pots:
            self.out(f"  Pot {p['amount']} -> {', '.join(self._seat_name(rec, s) for s in p['winners'])}")
        me = rec.results[seat]
        self.out(f"  Your result: {me.net:+d}  (Stack {me.end_stack})")
        self._shown.pop(rec.hand_id, None)
