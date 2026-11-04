"""Regelbasierte Handrekonstruktion aus stabilisierten Feldereignissen.

Arbeitet ausschliesslich auf dem Journal (observations.jsonl), ist also jederzeit
mit neuer Logik wiederholbar, ohne Rohdaten zu veraendern.

Quellen einer Aktion (`source`):
  observed_label   Aktionsbeschriftung am Platz gelesen (z. B. 'Check')
  observed_fold    Fold ueber Beschriftung/Ausblendung des Panels gesehen
  derived_bet      aus Aenderung des sichtbaren Einsatzes abgeleitet
  derived_turn     aus Wechsel der Hervorhebung ohne Einsatzaenderung (-> Check)
  derived_stack    aus Stackzuwachs (Gewinn/Rueckgabe)
  inferred_gap     Reihenfolge verlangt eine Aktion, die nicht gesehen wurde
  inferred_street_end  am Strassenende logisch erschlossen: wer noch in der Hand ist, hat gecallt (Einsatz
                   unter dem Hoechstgebot) oder gecheckt (nichts offen). Ein abschliessender Call ist
                   praktisch nie zu sehen, weil die Einsaetze sofort eingesammelt werden.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

RECONSTRUCT_VERSION = "reconstruct-2"
STREETS = ["preflop", "flop", "turn", "river"]
BOARD_TO_STREET = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}
NUM_SEATS = 10
TURN_GRACE_S = 0.9      # Wartezeit, ob nach Hervorhebungswechsel noch ein Einsatz kommt
SWEEP_WINDOW_S = 2.0    # Einsatz faellt auf 0 nahe Strassenwechsel = Einsammeln, keine Aktion
# PokerTH schaltet die Handnummer um, bevor der Tisch aufgeraeumt ist (Marker, Einsaetze, Labels der Vorhand
# stehen noch kurz da). Bis Marker und Blinds stehen (hoechstens SETTLE_S), werden Sitz-Ereignisse gepuffert.
SETTLE_S = 2.5
# Fold/Einsatz kurz nach dem Strassenwechsel gehoert zur vorigen Strasse, wenn der Spieler dort noch dran war
LATE_S = 1.5
# Handnummer, die so kurz nach einem am Bild erkannten Handwechsel kommt, gehoert zur neuen Hand
ADOPT_S = 30.0
MIN_HAND_S = 4.0        # Dealerwechsel so kurz nach einem Handbeginn ist das Nachziehen des Buttons, keine neue Hand
_SETTLE_PROPS = ("bet", "folded", "action_label", "active", "stack")


@dataclass
class Action:
    t: float
    street: str
    seat: int
    name: str | None
    type: str                   # post_sb, post_bb, fold, check, call, bet, raise, collect, unknown
    amount_to: int | None = None    # Gesamteinsatz dieser Strasse nach der Aktion
    added: int | None = None        # zusaetzlich gesetzte Chips
    allin: bool = False
    source: str = ""
    confidence: float = 0.0
    frames: list[int] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class SeatInfo:
    seat: int
    name: str | None = None
    start_stack: int | None = None
    end_stack: int | None = None
    cards: list[str] | None = None
    cards_source: str | None = None
    folded: bool = False
    allin: bool = False


@dataclass
class Hand:
    game_no: int | None
    hand_no: int | None
    t_start: float
    t_end: float | None = None
    boundary: str = "observed"          # 'observed' (Handnummer) | 'inferred'
    dealer: int | None = None
    sb_seat: int | None = None
    bb_seat: int | None = None
    blinds: list[int] | None = None
    seats: dict[int, SeatInfo] = field(default_factory=dict)
    board: list[str | None] = field(default_factory=lambda: [None] * 5)
    actions: list[Action] = field(default_factory=list)
    pot_observations: list[dict] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    status: str = "open"
    status_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["seats"] = {str(k): asdict(v) for k, v in sorted(self.seats.items())}
        return d


class _StreetState:
    def __init__(self, name: str, t: float):
        self.name = name
        self.t_start = t
        self.bets: dict[int, int] = {}
        self.max_bet = 0
        self.acted: set[int] = set()
        self.last_actor: int | None = None


class Reconstructor:
    def __init__(self, num_seats: int = NUM_SEATS):
        self.n = num_seats
        self.cur: dict[str, Any] = {}
        self.hands: list[Hand] = []
        self.hand: Hand | None = None
        self.street: _StreetState | None = None
        self.last_street_change_t = -1e9
        self.active_seat: int | None = None
        self.active_since: float = 0.0
        self.pending_turn: dict | None = None
        self.unassigned: list[dict] = []
        self.settling: dict | None = None          # {"until": t, "buffer": [...], "markers": set()}
        self.prev_street: _StreetState | None = None
        self.board_votes: list[dict[str, int]] = [{} for _ in range(5)]
        self.card_votes: dict[int, dict[tuple, int]] = {}
        self.stack_dips: dict[int, list[tuple[int, int]]] = {}
        self.pending_close: tuple | None = None

    # ---- Hilfen ----------------------------------------------------------

    def _name(self, seat: int) -> str | None:
        return self.cur.get(f"seat.{seat}.name")

    def _in_hand(self, seat: int) -> bool:
        if self.hand is None:
            return False
        si = self.hand.seats.get(seat)
        if si is None or si.folded or si.allin:
            return False
        return bool(self.cur.get(f"seat.{seat}.present"))

    def _seat_info(self, seat: int) -> SeatInfo:
        si = self.hand.seats.get(seat)
        if si is None:
            si = SeatInfo(seat, name=self._name(seat))
            self.hand.seats[seat] = si
        return si

    def _add_action(self, ev: dict, seat: int, typ: str, source: str, conf: float, **kw) -> Action:
        if self.pending_turn and self.pending_turn["seat"] != seat and typ != "collect":
            # Ein anderer Spieler handelt: offene Zugabgabe zuerst als Check werten
            self._resolve_pending(ev.get("t_first", 0.0), force=True)
        a = Action(t=ev.get("t_first", 0.0), street=self.street.name if self.street else "preflop", seat=seat,
                   name=self._name(seat), type=typ, source=source, confidence=round(conf, 3),
                   frames=[f for f in (ev.get("frame_first"), ev.get("frame_confirmed")) if f is not None],
                   evidence=[ev["evidence"]] if ev.get("evidence") else [], **kw)
        self._check_order(a)
        self.hand.actions.append(a)
        if self.street and typ not in ("collect", "unknown"):
            self.street.acted.add(seat)
            self.street.last_actor = seat
        if self.pending_turn and self.pending_turn["seat"] == seat:
            self.pending_turn = None
        return a

    # ---- Reihenfolge -----------------------------------------------------

    def _first_to_act(self) -> int | None:
        h = self.hand
        if self.street is None or h is None:
            return None
        if self.street.name == "preflop":
            start = h.bb_seat
        else:
            start = h.dealer
        if start is None:
            return None
        for k in range(1, self.n + 1):
            s = (start + k) % self.n
            if self._in_hand(s):
                return s
        return None

    def _check_order(self, a: Action):
        """Sitze zwischen letzter und aktueller Aktion, die noch im Spiel sind und nicht
        gehandelt haben, werden als nicht beobachtete Aktion markiert."""
        if self.street is None or a.type in ("post_sb", "post_bb", "collect", "unknown"):
            return
        prev = self.street.last_actor
        if prev is None:
            first = self._first_to_act()
            if first is None:
                return
            prev = (first - 1) % self.n
            if prev == a.seat:
                return
        # Handelt derselbe Spieler erneut (prev == a.seat), wird eine volle Runde geprueft
        s = (prev + 1) % self.n
        guard = 0
        while guard < self.n - 1 and s != a.seat:
            guard += 1
            if self._in_hand(s) and s not in self.street.acted:
                to_call = self.street.max_bet - self.street.bets.get(s, 0)
                guess = "vermutlich Check" if to_call <= 0 else "Fold/Call nicht gesehen"
                miss = Action(t=a.t, street=self.street.name, seat=s, name=self._name(s), type="unknown",
                              source="inferred_gap", confidence=0.0,
                              note=f"Aktion laut Reihenfolge erwartet, nicht beobachtet ({guess})")
                self.hand.actions.append(miss)
                self.hand.gaps.append(f"{self.street.name}: Aktion von Sitz {s} nicht beobachtet")
                self.street.acted.add(s)
            s = (s + 1) % self.n

    # ---- Hand- und Strassenwechsel ---------------------------------------

    def _start_hand(self, ev: dict, game_hand, boundary: str):
        self._finish_hand(ev.get("t_first", 0.0))
        g, h = (game_hand or [None, None])
        self.hand = Hand(game_no=g, hand_no=h, t_start=ev.get("t_first", 0.0), boundary=boundary)
        self.street = _StreetState("preflop", self.hand.t_start)
        self.last_street_change_t = self.hand.t_start
        self.pending_turn = None
        self.active_seat = None
        for s in range(self.n):
            if self.cur.get(f"seat.{s}.present"):
                si = self._seat_info(s)
                stack = self.cur.get(f"seat.{s}.stack")
                bet = self.cur.get(f"seat.{s}.bet") or 0
                if isinstance(stack, int):
                    si.start_stack = stack + (bet if isinstance(bet, int) else 0)
                if self.cur.get(f"seat.{s}.folded"):
                    # Sitzt aus oder Panel noch aus der Vorhand ausgeblendet -> unsicher
                    pass
        if self.cur.get("info.blinds"):
            self.hand.blinds = self.cur["info.blinds"]
        self.prev_street = None
        self.pending_close = None
        self.board_votes = [{} for _ in range(5)]
        self.card_votes = {}
        self.stack_dips = {}
        self.settling = {"until": self.hand.t_start + SETTLE_S, "buffer": [], "markers": set(), "board0": False,
                         "ev": ev, "bets0": {s: self.cur.get(f"seat.{s}.bet") for s in range(self.n)}}

    def _settle(self, t: float):
        """Einschwingen beendet: Marker, Startstacks und Blinds aus dem aktuellen Tischzustand, danach die
        gepufferten Sitz-Ereignisse (ohne Einsatz-/Stackwerte - die stecken schon im Tischzustand)."""
        st = self.settling
        self.settling = None
        h = self.hand
        for kind, attr in (("D", "dealer"), ("SB", "sb_seat"), ("BB", "bb_seat")):
            v = self.cur.get(f"marker.{kind}")
            if v is not None:
                setattr(h, attr, v)
        if self.cur.get("info.blinds"):
            h.blinds = self.cur["info.blinds"]
        present = [s for s in range(self.n) if self.cur.get(f"seat.{s}.present")]
        if h.bb_seat is not None and h.sb_seat is not None and len(present) >= 3 and "marker.SB" not in st["markers"]:
            expect = next((h.bb_seat - k) % self.n for k in range(1, self.n) if (h.bb_seat - k) % self.n in present)
            if h.sb_seat != expect:
                h.sb_seat = None      # alter Marker der Vorhand -> unten aus dem BB ableiten
        if h.sb_seat is None and h.bb_seat is not None and len(present) >= 2:
            if len(present) == 2 and h.dealer is not None:
                h.sb_seat = h.dealer
            else:
                h.sb_seat = next((h.bb_seat - k) % self.n for k in range(1, self.n)
                                 if (h.bb_seat - k) % self.n in present)
            h.status_reasons.append("SB-Platz aus BB abgeleitet")
        for s in range(self.n):
            if self.cur.get(f"seat.{s}.present"):
                si = self._seat_info(s)
                stack, bet = self.cur.get(f"seat.{s}.stack"), self.cur.get(f"seat.{s}.bet") or 0
                if isinstance(stack, int):
                    si.start_stack = stack + (bet if isinstance(bet, int) else 0)
        # Blinds, die schon beim Handwechsel sichtbar waren
        ev0 = dict(st["ev"])
        blinds = h.blinds or [None, None]
        for s, amount in ((h.sb_seat, blinds[0]), (h.bb_seat, blinds[1])):
            b0 = st["bets0"].get(s) if s is not None else None
            if isinstance(b0, int) and b0 > 0 and b0 == amount:
                self._bet_change(ev0, s, 0, b0)
        # Danach die gepufferten Ereignisse in zeitlicher Reihenfolge
        seen_bet_change: set[int] = set()
        for bev in st["buffer"]:
            seat, prop = int(bev["field"].split(".")[1]), bev["field"].split(".", 2)[2]
            new = bev.get("new")
            if prop == "bet":
                if new == 0 and seat not in seen_bet_change:
                    continue          # Einsatz der Vorhand wird eingesammelt
                if new == st["bets0"].get(seat) and seat not in seen_bet_change:
                    continue          # unveraenderter Rest der Vorhand
                seen_bet_change.add(seat)
            elif prop == "stack":
                old = bev.get("_old")
                if isinstance(new, int) and isinstance(old, int) and new > old and self.hands and \
                        not any(a.type not in ("post_sb", "post_bb", "unknown") for a in h.actions):
                    prev = self.hands[-1]  # Pot der Vorhand, nach dem Handwechsel gutgeschrieben
                    prev.actions.append(Action(t=bev.get("t_first", t), street=prev.actions[-1].street if prev.actions
                                               else "river", seat=seat, name=self._name(seat), type="collect",
                                               added=new - old, source="derived_stack", confidence=0.4,
                                               note="nach dem Handwechsel gutgeschrieben"))
                    if prev.seats.get(seat) is not None:
                        prev.seats[seat].end_stack = new
                continue          # Startstacks stammen schon aus dem Tischzustand
            elif prop == "folded" and not self.cur.get(bev["field"]):
                continue          # Fold-Ausblendung der Vorhand, inzwischen aufgehoben
            self._seat_event(bev, seat, prop, bev.get("_old"), new)

    def _finish_hand(self, t: float):
        h = self.hand
        if h is None:
            return
        if self.settling is not None:
            self._settle(t)               # Hand endet noch im Einschwingen: Gepuffertes nicht verlieren
        self._flush_close()
        self._resolve_pending(t, force=True)
        live = [s for s, si in h.seats.items() if not si.folded and self.cur.get(f"seat.{s}.present")]
        if self.street is not None and len(live) >= 2 and all(c is not None for c in h.board):
            self._close_street(self.street, t)
        h.t_end = t
        for s, si in h.seats.items():
            st = self.cur.get(f"seat.{s}.stack")
            if isinstance(st, int):
                si.end_stack = st
            # Stackbilanz: Start = Ende - Gewinne + eingesetzte Chips (nur mit beobachteten Aktionen)
            acts = [a for a in h.actions if a.seat == s]
            if si.end_stack is None or any(a.type == "unknown" for a in acts):
                continue
            committed = sum(a.added or 0 for a in acts if a.type != "collect")
            collected = sum(a.added or 0 for a in acts if a.type == "collect")
            derived = si.end_stack - collected + committed
            if si.start_stack is None:
                si.start_stack = derived
            elif si.start_stack != derived:
                h.contradictions.append(
                    f"Stackbilanz Sitz {s}: Start {si.start_stack}, aus Aktionen {derived} "
                    f"(Ende {si.end_stack}, gesetzt {committed}, gewonnen {collected})")
        reasons = []
        if h.boundary != "observed":
            reasons.append("Handgrenze nur abgeleitet")
        if h.dealer is None:
            reasons.append("Dealer nicht gesehen")
        if h.sb_seat is None or h.bb_seat is None:
            reasons.append("Blind-Positionen nicht gesehen")
        if not any(a.type == "post_bb" for a in h.actions):
            reasons.append("Big Blind nicht beobachtet (Handbeginn verpasst?)")
        if h.gaps:
            reasons.append(f"{len(h.gaps)} Luecke(n) in der Aktionsfolge")
        if h.contradictions:
            reasons.append(f"{len(h.contradictions)} Widerspruch/Widersprueche")
        if not any(a.type == "collect" for a in h.actions):
            reasons.append("Gewinner nicht beobachtet")
        h.status = "complete" if not reasons else "partial"
        h.status_reasons = reasons
        self.hands.append(h)
        self.hand = None
        self.street = None

    def _close_street(self, st: _StreetState, t: float, showdown: bool = True):
        """Nicht gesehene Aktionen am Strassenende erschliessen (siehe inferred_street_end)."""
        if self.hand is None or st is None or not showdown:
            return
        can_act = [s for s, si in self.hand.seats.items() if not si.folded and not si.allin
                   and self.cur.get(f"seat.{s}.present")]
        if len(can_act) <= 1 and st.max_bet == 0:
            return            # alle anderen all-in: auf dieser Strasse wurde nicht mehr gesetzt
        for s in range(self.n):
            si = self.hand.seats.get(s)
            if si is None or si.folded or si.allin or not self.cur.get(f"seat.{s}.present"):
                continue
            own = [a for a in self.hand.actions if a.seat == s and a.street == st.name]
            voluntary = [a for a in own if a.type not in ("post_sb", "post_bb", "unknown", "collect")]
            unknown = [a for a in own if a.type == "unknown"]
            bet = st.bets.get(s, 0)
            if bet < st.max_bet:
                typ = "call"
            elif voluntary:
                continue
            else:
                typ = "check"
            if voluntary and typ == "call" and voluntary[-1].type in ("call",) and voluntary[-1].amount_to == st.max_bet:
                continue
            a = unknown[-1] if unknown else None
            if a is None:
                a = Action(t=t, street=st.name, seat=s, name=self._name(s), type=typ)
                self.hand.actions.append(a)
            a.type, a.source, a.confidence = typ, "inferred_street_end", 0.6
            a.note = "am Strassenende erschlossen (noch in der Hand)"
            if typ == "call":
                a.amount_to, a.added = st.max_bet, st.max_bet - bet
                st.bets[s] = st.max_bet
            gap = f"{st.name}: Aktion von Sitz {s} nicht beobachtet"
            if gap in self.hand.gaps:
                self.hand.gaps.remove(gap)

    def _flush_close(self):
        if self.pending_close is not None:
            st, t = self.pending_close
            self.pending_close = None
            self._close_street(st, t)

    def _new_street(self, ev: dict, name: str):
        if self.street and self.street.name == name:
            return
        t = ev.get("t_first", 0.0)
        self._resolve_pending(t, force=True)
        if self.street and self.street.name in STREETS and name in STREETS:
            i_old, i_new = STREETS.index(self.street.name), STREETS.index(name)
            if i_new < i_old:
                self.hand.contradictions.append(f"Strasse rueckwaerts: {self.street.name} -> {name}")
            elif i_new > i_old + 1:
                self.hand.gaps.append(f"Strasse(n) uebersprungen: {self.street.name} -> {name}")
            if i_new > i_old:
                self._flush_close()
                self.pending_close = (self.street, t)
            # Am Strassenende sollten alle verbliebenen Spieler gleich viel gesetzt haben
            if self.street:
                live = [s for s in range(self.n) if self._in_hand(s)]
                unequal = [s for s in live if self.street.bets.get(s, 0) != self.street.max_bet]
                if unequal and self.street.max_bet > 0:
                    self.hand.contradictions.append(
                        f"{self.street.name}: ungleiche Einsaetze am Strassenende bei Sitz {unequal}")
        self.prev_street = self.street
        self.street = _StreetState(name, t)
        self.last_street_change_t = t
        self.pending_turn = None

    # ---- Aktionen ---------------------------------------------------------

    def _bet_change(self, ev: dict, seat: int, old, new):
        if self.hand is None or self.street is None or not isinstance(new, int):
            return
        if new > 0 and self.prev_street is not None and self._late_for_prev(ev, seat) and \
                new > self.prev_street.bets.get(seat, 0):
            saved, saved_t = self.street, self.last_street_change_t
            self.street, self.last_street_change_t = self.prev_street, -1e9
            self._bet_change_now(ev, seat, old, new)
            if self.hand.actions and self.hand.actions[-1].seat == seat:
                self.hand.actions[-1].note = (self.hand.actions[-1].note + "; " if self.hand.actions[-1].note else "") + \
                    "verspaetet gelesen, der vorigen Strasse zugeordnet"
            self.street, self.last_street_change_t = saved, saved_t
            return
        self._bet_change_now(ev, seat, old, new)

    def _bet_change_now(self, ev: dict, seat: int, old, new):
        t = ev.get("t_first", 0.0)
        prev = self.street.bets.get(seat, 0)
        if new < prev:
            if new == 0 and abs(t - self.last_street_change_t) <= SWEEP_WINDOW_S:
                return
            if new == 0:
                # Einsaetze werden eingesammelt, bevor die Strasse als gewechselt erkannt ist
                return
            self.hand.contradictions.append(f"Sitz {seat}: Einsatz sinkt {prev} -> {new} ohne Strassenwechsel")
            return
        if new == prev:
            return
        added = new - prev
        stack = self.cur.get(f"seat.{seat}.stack")
        allin = isinstance(stack, int) and stack == 0
        street_max = self.street.max_bet
        h = self.hand
        conf = ev.get("confidence", 0.5)
        if self.street.name == "preflop" and seat not in self.street.acted:
            blinds = h.blinds or [None, None]
            if seat == h.sb_seat and (blinds[0] is None or new == blinds[0]) and street_max == 0:
                self._apply_bet(seat, new)
                self._add_action(ev, seat, "post_sb", "derived_bet", conf, amount_to=new, added=added, allin=allin)
                return
            if seat == h.bb_seat and (blinds[1] is None or new == blinds[1]) and street_max <= (blinds[0] or new):
                self._apply_bet(seat, new)
                self._add_action(ev, seat, "post_bb", "derived_bet", conf, amount_to=new, added=added, allin=allin)
                return
        if new > street_max:
            typ = "bet" if street_max == 0 else "raise"
            note = ""
        elif new == street_max:
            typ, note = "call", ""
        else:
            typ = "call"
            note = "unter dem Hoechstgebot" + (" (All-in)" if allin else " - Einsatz evtl. noch nicht fertig gelesen")
            if not allin:
                conf *= 0.5
        self._apply_bet(seat, new)
        if allin:
            self._seat_info(seat).allin = True
        self._add_action(ev, seat, typ, "derived_bet", conf, amount_to=new, added=added, allin=allin, note=note)

    def _apply_bet(self, seat: int, amount: int):
        self.street.bets[seat] = amount
        self.street.max_bet = max(self.street.max_bet, amount)

    def _late_for_prev(self, ev: dict, seat: int) -> bool:
        """Gehoert ein Ereignis kurz nach dem Strassenwechsel noch zur vorigen Strasse? Ja, wenn der Spieler
        dort noch einen offenen Einsatz hatte und auf der neuen Strasse noch nichts getan hat."""
        ps = self.prev_street
        if ps is None or self.street is None or seat in self.street.acted:
            return False
        if ev.get("t_first", 0.0) - self.last_street_change_t > LATE_S:
            return False
        return ps.bets.get(seat, 0) < ps.max_bet

    def _fold(self, ev: dict, seat: int, source: str):
        if self.hand is None:
            return
        si = self._seat_info(seat)
        if si.folded:
            return
        si.folded = True
        if self._late_for_prev(ev, seat):
            saved = self.street
            self.street = self.prev_street
            a = self._add_action(ev, seat, "fold", source, ev.get("confidence", 0.5))
            a.note = "verspaetet gelesen, der vorigen Strasse zugeordnet"
            self.street = saved
            return
        self._add_action(ev, seat, "fold", source, ev.get("confidence", 0.5))

    def _label(self, ev: dict, seat: int, label: str | None):
        if self.hand is None or label is None or self.street is None:
            return
        if label == "check":
            if self.street.bets.get(seat, 0) < self.street.max_bet:
                self.hand.contradictions.append(f"Sitz {seat}: 'Check' gelesen, aber offener Einsatz")
            if not any(a.seat == seat and a.street == self.street.name and a.type == "check"
                       for a in self.hand.actions):
                self._add_action(ev, seat, "check", "observed_label", ev.get("confidence", 0.5))
        elif label == "fold":
            self._fold(ev, seat, "observed_label")
        else:
            # Beschriftung bestaetigt abgeleitete Aktion
            for a in reversed(self.hand.actions):
                if a.seat == seat and a.street == self.street.name:
                    if a.type == label or (label == "allin" and a.allin):
                        a.source += "+observed_label"
                        a.confidence = min(1.0, a.confidence + 0.2)
                    else:
                        self.hand.contradictions.append(
                            f"Sitz {seat}: Beschriftung '{label}' passt nicht zu abgeleitet '{a.type}'")
                    break

    def _active_change(self, ev: dict, seat: int, active: bool):
        t = ev.get("t_first", 0.0)
        if active:
            if self.pending_turn and self.pending_turn["seat"] != seat:
                self._resolve_pending(t, force=True)
            self.active_seat, self.active_since = seat, t
        elif self.active_seat == seat and self.hand is not None and self.street is not None:
            # Spieler gibt Zug ab: kam keine Einsatz-/Fold-Aenderung, war es vermutlich Check
            self.pending_turn = {"seat": seat, "t": t, "since": self.active_since, "street": self.street.name, "ev": ev}
            self.active_seat = None

    def _resolve_pending(self, t: float, force: bool = False):
        p = self.pending_turn
        if not p or self.hand is None:
            return
        if not force and t - p["t"] < TURN_GRACE_S:
            return
        self.pending_turn = None
        seat = p["seat"]
        si = self.hand.seats.get(seat)
        if si and si.folded:
            return
        street_bets = self.street.bets if self.street and self.street.name == p["street"] else {}
        max_bet = self.street.max_bet if self.street and self.street.name == p["street"] else 0
        if street_bets.get(seat, 0) >= max_bet:
            # Hat der Spieler seit Beginn seiner Hervorhebung schon sichtbar gehandelt?
            already = any(a.seat == seat and a.street == p["street"] and a.t >= p["since"] - 0.2 and
                          a.type not in ("unknown", "post_sb", "post_bb") for a in self.hand.actions)
            if not already:
                saved = self.street
                if self.street and self.street.name != p["street"]:
                    self.street = _StreetState(p["street"], p["t"])  # nur fuer die Zuordnung
                self._add_action(p["ev"], seat, "check", "derived_turn", 0.4,
                                 note="Hervorhebung wechselte ohne Einsatzaenderung")
                self.street = saved

    def _stack_change(self, ev: dict, seat: int, old, new):
        if self.hand is None or not isinstance(new, int) or not isinstance(old, int):
            return
        dips = self.stack_dips.setdefault(seat, [])
        bet_now = self.cur.get(f"seat.{seat}.bet") or 0
        if new < old:
            dips.append((old, bet_now))      # Absinken merken (Einsatz oder Lesefehler)
            return
        if dips and dips[-1][0] == new and dips[-1][1] == bet_now:
            dips.pop()                        # zurueck auf den alten Wert ohne Einsatzaenderung: Lesefehler
            return
        voluntary = any(a.type not in ("post_sb", "post_bb", "unknown") for a in self.hand.actions)
        if new > old and not voluntary and self.hands and ev.get("t_first", 0.0) - self.hand.t_start < 6.0:
            # Pot der Vorhand wird erst nach dem Handwechsel gutgeschrieben -> dort verbuchen
            prev = self.hands[-1]
            prev.actions.append(Action(t=ev.get("t_first", 0.0), street=prev.actions[-1].street if prev.actions else "river",
                                       seat=seat, name=self._name(seat), type="collect", added=new - old,
                                       source="derived_stack", confidence=round(ev.get("confidence", 0.5) * 0.8, 3),
                                       note="nach dem Handwechsel gutgeschrieben"))
            psi = prev.seats.get(seat)
            if psi is not None:
                psi.end_stack = new
            si = self._seat_info(seat)
            if si.start_stack is not None:
                si.start_stack += new - old
            return
        if new > old:
            self._add_action(ev, seat, "collect", "derived_stack", ev.get("confidence", 0.5) * 0.8,
                             added=new - old, note="Stackzuwachs (Gewinn oder Rueckgabe nicht gecallter Chips)")

    # ---- Ereignisschleife ------------------------------------------------

    def feed(self, ev: dict):
        if ev.get("kind") not in ("change", "unknown"):
            return
        f = ev["field"]
        old = self.cur.get(f)
        new = ev.get("new") if ev["kind"] == "change" else None
        self.cur[f] = new
        t = ev.get("t_first", 0.0)
        if self.settling is not None and self.hand is not None:
            stl = self.settling
            if f == "board.count" and new == 0:
                stl["board0"] = True
            if t >= stl["until"] or ({"marker.SB", "marker.BB"} <= stl["markers"] and stl["board0"]
                                     and not f.startswith("marker.")):
                self._settle(t)
        self._resolve_pending(t)
        if self.pending_close is not None and t - self.pending_close[1] > LATE_S:
            self._flush_close()

        if f == "info.game_hand" and new is not None:
            h = self.hand
            if h is not None and h.boundary == "inferred" and h.hand_no is None and t - h.t_start <= ADOPT_S:
                # Handwechsel schon am Bild erkannt, die Nummer kommt verspaetet: gehoert zu dieser Hand
                h.game_no, h.hand_no = (new or [None, None])
                h.boundary = "observed"
                h.status_reasons.append("Handnummer verspaetet gelesen")
                return
            self._start_hand(ev, new, "observed")
            return
        if f == "table.found" and new is False:
            if self.hand:
                self.hand.gaps.append(f"Tisch nicht sichtbar ab t={t:.2f}s")
            return
        if self.hand is None:
            # Ohne Handnummer: neue Hand erkennen, wenn das Board leer wird und Blinds erscheinen
            if f == "board.count" and new == 0:
                self._start_hand(ev, None, "inferred")
            return

        if f == "info.street" and new in STREETS:
            self._new_street(ev, new)
        elif f == "board.count" and new in BOARD_TO_STREET:
            target = BOARD_TO_STREET[new]
            if new == 0 and self.street and self.street.name != "preflop":
                # Board leer nach Flop/Turn/River = neue Hand, auch wenn die Handnummer (noch) die alte zeigt
                self._start_hand(ev, None, "inferred")
            elif self.street is None or STREETS.index(target) > STREETS.index(self.street.name):
                self._new_street(ev, target)
        elif f == "board.cards" and isinstance(new, list):
            # Mehrheit der bestaetigten Lesungen je Platz (einzelne Fehllesungen ueberstimmen nichts)
            for i, c in enumerate(new[:5]):
                if c is not None and c != "??":
                    votes = self.board_votes[i]
                    votes[c] = votes.get(c, 0) + 1
                    best = max(votes, key=votes.get)
                    if self.hand.board[i] not in (None, best) and len(votes) > 1:
                        self.hand.contradictions.append(f"Boardkarte {i + 1}: {self.hand.board[i]} -> {best}")
                    self.hand.board[i] = best
        elif f.startswith("marker.") and new is not None:
            attr = {"marker.D": "dealer", "marker.SB": "sb_seat", "marker.BB": "bb_seat"}[f]
            if self.settling is not None:
                self.settling["markers"].add(f)
            elif f == "marker.D" and self.hand.dealer is not None and self.hand.dealer != new and                     t - self.hand.t_start >= MIN_HAND_S and                     any(a.type not in ("post_sb", "post_bb", "unknown") for a in self.hand.actions):
                # Dealer-Button gewandert, Handnummer unveraendert: neue Hand (Nummer kommt spaeter)
                self._start_hand(ev, None, "inferred")
                self.settling["markers"].add(f)
                self.hand.dealer = new
            else:
                prev = getattr(self.hand, attr)
                if prev is not None and prev != new:
                    self.hand.contradictions.append(f"{attr} wechselt innerhalb der Hand: {prev} -> {new}")
                setattr(self.hand, attr, new)
        elif f == "info.blinds" and new:
            self.hand.blinds = self.hand.blinds or new
        elif f == "pot.total" and new is not None:
            self.hand.pot_observations.append({"t": t, "pot": new, "street": self.street.name if self.street else None})
        elif f == "hero.to_act":
            self._active_change(ev, 0, bool(new))
        elif f.startswith("seat."):
            _, s, prop = f.split(".", 2)
            seat = int(s)
            if self.settling is not None and prop in _SETTLE_PROPS:
                self.settling["buffer"].append(dict(ev, _old=old))
                return
            self._seat_event(ev, seat, prop, old, new)

    def _seat_event(self, ev: dict, seat: int, prop: str, old, new):
        if self.hand is None:
            return
        if True:
            if prop == "bet":
                self._bet_change(ev, seat, old, new)
            elif prop == "folded" and new:
                self._fold(ev, seat, "observed_fold")
            elif prop == "action_label":
                self._label(ev, seat, new)
            elif prop == "active":
                self._active_change(ev, seat, bool(new))
            elif prop == "stack":
                if new == 0 and self._seat_info(seat).start_stack:
                    self._seat_info(seat).allin = True      # Stack 0 mitten in der Hand: all-in, handelt nicht mehr
                elif isinstance(new, int) and new > 0 and old == 0 and self._seat_info(seat).allin \
                        and not any(a.seat == seat and a.allin for a in self.hand.actions):
                    self._seat_info(seat).allin = False     # '$O'-Verleser: war gar nicht all-in
                self._stack_change(ev, seat, old, new)
            elif prop == "cards" and isinstance(new, list):
                si = self._seat_info(seat)
                if all(c and c != "??" for c in new):
                    votes = self.card_votes.setdefault(seat, {})
                    key = tuple(sorted(new))
                    votes[key] = votes.get(key, 0) + 1
                    best = list(max(votes, key=votes.get))
                    if si.cards and sorted(si.cards) != best and len(votes) > 1:
                        self.hand.contradictions.append(f"Sitz {seat}: Karten {si.cards} -> {best}")
                    si.cards = best
                    si.cards_source = "visible_hole_cards" if seat == 0 else "visible_showdown"
            elif prop == "name" and new:
                self._seat_info(seat).name = new
            elif prop == "present" and new and self.hand:
                self._seat_info(seat)

    def finish(self, t_end: float | None = None) -> list[Hand]:
        if self.hand is not None:
            self._finish_hand(t_end if t_end is not None else self.hand.t_start)
        return self.hands


_FIELD_PRIORITY = [
    ("table.", 0), ("info.game_hand", 1), ("marker.", 2), ("info.blinds", 3), ("info.street", 4),
    ("board.", 5), ("seat.", 7), ("hero.", 8),
]


def _priority(field_name: str) -> int:
    """Gleichzeitig sichtbar gewordene Felder (z. B. Einstieg mitten in einer Hand) werden
    so geordnet, dass Hand, Positionen und Blinds vor den Einsaetzen bekannt sind."""
    if field_name.endswith(".present") or field_name.endswith(".name"):
        return 6
    for prefix, p in _FIELD_PRIORITY:
        if field_name.startswith(prefix):
            return p
    return 9


def reconstruct(events: list[dict]) -> list[Hand]:
    r = Reconstructor()
    last_t = 0.0
    usable = (e for e in events if "seq" in e)
    for ev in sorted(usable, key=lambda e: (e.get("t_first", 0.0), _priority(e.get("field", "")), e["seq"])):
        r.feed(ev)
        last_t = max(last_t, ev.get("t_confirmed", 0.0) or 0.0)
    return r.finish(last_t)
