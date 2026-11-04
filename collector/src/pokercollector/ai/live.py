"""Live-Anbindung Collector -> Bot: Vorschlaege mit Handverlauf und Gegnermodell.

Waehrend der Partie laeuft ein Reconstructor mit (dieselbe Rekonstruktion wie nach der Sitzung):
- Jede fertige Hand fuettert das Gegnermodell (opponents.OpponentTracker) - beim Bot selbst, wenn er
  eins hat (Netze ab feat-3), und immer in einer eigenen Kopie fuer die Anzeige.
- Der Verlauf der laufenden Hand (wer hat gesetzt, erhoeht, gecallt) kommt in die Observation.
  Ohne ihn saehe der Bot live keine Raises vor sich.
Quelle bleibt ausschliesslich das, was der Collector im Bild erkannt hat. Es wird nichts geklickt.
Die Rekonstruktion kann der Wirklichkeit um Sekundenbruchteile nachhinken (spaete Folds/Einsaetze);
das steht dann in Observation.uncertain.
"""

from __future__ import annotations

import threading
from dataclasses import replace

from ..reconstruct import Reconstructor
from .observation import Action, Observation, PublicAction
from .opponents import OpponentTracker
from .replay import observation_from_table_state

HISTORY_KINDS = ("post_sb", "post_bb", "fold", "check", "call", "bet", "raise")
SETTLE_S = 0.7          # so lange muss die Lage ruhig sein, bevor ein Vorschlag erscheint
BUST_S = 20.0           # eigener Stack so lange 0 ohne neue Hand -> ausgeschieden (All-in-Ausspielen dauert kuerzer)
SAME_AMOUNT = 0.25      # neuer Vorschlag gleicher Art innerhalb derselben Strasse erst ab 25 % anderem Betrag


def fix_dollar_misreads(state: dict, chips: int | None) -> dict:
    """Unplausible Zahlen im Bild gegen die Chips des Turniers pruefen.
    1. '$1000' wird gelegentlich als 51000 gelesen (Dollarzeichen als 5). Ein Stack ueber allen Chips des
       Turniers, der mit 5 beginnt und ohne die 5 passt, ist so ein Fall.
    2. Ein Einsatz, der zusammen mit dem Stack desselben Platzes ueber allen Chips liegt, ist kein Einsatz
       (29.10. abends: am Endbildschirm wurde der Siegerstack '$13408' als Einsatz von Platz 5 gelesen und blieb
       das ganze naechste Turnier im Zustand stehen -> Pot 13438 statt 30 in jeder Hand, Vorschlaege wertlos).
       Er wird auf unbekannt gesetzt (zaehlt als 0)."""
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
    """Einsaetze im Bild, zu denen die laufende Hand keine Aktion des Platzes kennt, sind Reste einer frueheren
    Hand (oder ein fremder Text im Einsatzfeld, 29.10.: Siegerstack '$13408' am Endbildschirm, blieb das ganze
    naechste Turnier stehen). Jede echte Einzahlung erzeugt im Rekonstruktor eine Aktion (auch Blinds). Ein
    gleich gebliebener Blind erzeugt kein Ereignis, darum bleiben Betraege bis zum Big Blind bzw. bis zum
    hoechsten Betrag der Hand stehen."""
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
    unc = list(obs.uncertain) + ["Einsatz ohne Aktion in dieser Hand ignoriert"]
    to_call, can_check = obs.to_call, obs.can_check
    if "zu callender Betrag aus Einsaetzen geschaetzt" in unc:      # sonst stammt er vom Call-Button
        to_call = min(max(0, max(bets) - bets[obs.seat]), obs.stacks[obs.seat])
        can_check = to_call == 0
    return replace(obs, bets=bets, committed=committed, uncertain=unc, to_call=to_call, can_check=can_check)


def sane(sug, obs):
    """Vorschlag an die gelesene Lage anpassen: Raise nie ueber den eigenen Stack (dann All-in), Raise nicht
    unter/auf den Hoechsteinsatz (dann Call bzw. Check), und Raise sinnlos, wenn alle Gegner schon All-in sind."""
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
    """Die Aktionsbuttons bieten Call oder Check an (nur 'Fold' = Vorauswahl)."""
    return any(b.get("action") in ("call", "check") for b in (buttons or []))


def is_decision(state: dict, hero_seat: int = 0) -> bool:
    """Du bist dran: eigener Platz hervorgehoben UND Call/Check-Buttons sichtbar. Die Buttons allein
    reichen nicht (Vorauswahl, waehrend andere handeln), 'hero.to_act' bleibt oft dauerhaft gesetzt."""
    return state.get(f"seat.{hero_seat}.active") is True and decision_buttons(state.get("hero.buttons"))


def public_history(hand: dict, num_seats: int = 10) -> list[PublicAction]:
    """Oeffentlicher Verlauf einer (laufenden) rekonstruierten Hand im Format der Engine."""
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
    """Erkennt das Turnierende aus den fertig rekonstruierten Haenden (nur Bildinhalt):
    - eigener Stack nach der Hand 0 -> ausgeschieden; Platz = 1 + Gegner, die danach noch Chips haben.
      Bestaetigt, sobald die naechste Hand ohne eigene Chips startet oder die Sitzung endet (ein
      einzelner OCR-Aussetzer '0' soll kein Turnier beenden).
    - nur noch man selbst hat Chips -> Platz 1.
    - Endbildschirm: Nach dem letzten All-in sind oft weder Stacks noch Gewinner lesbar. Dann zaehlt, wenn
      ein Stack im Bild alle Chips des Turniers zeigt (Summe der Startstacks, +-3 %): der eigene -> Platz 1,
      ein fremder -> Platz 2.
    - Eigener Stack BUST_S Sekunden lang 0, ohne dass eine neue Hand beginnt (PokerTH teilt nach dem eigenen
      Ausscheiden oft nicht weiter aus) -> ausgeschieden; Platz = 1 + Gegner mit Chips im Bild.
    - Zwei Haende in Folge ohne eigene Chips (nach einer Hand mit Chips) -> ausgeschieden, auch wenn das
      Ausscheiden selbst nicht zu sehen war.
    Je Spiel (info.game_hand) wird hoechstens ein Ergebnis gemeldet."""

    def __init__(self, hero_seat: int = 0):
        self.hero = hero_seat
        self.game = None
        self.field = 0
        self.first_hand_no = None
        self.hands = 0
        self.reported = False
        self.pending: dict | None = None
        self.chips: int | None = None          # alle Chips im Turnier (Summe der Startstacks)
        self.missing = 0                       # Haende in Folge ohne eigene Chips
        self.last: dict | None = None
        self.zero_since: tuple | None = None   # (Zeit, Hand, Gegner) seit der der eigene Stack 0 zeigt
        self.last_no = None                    # letzte gesehene Handnummer (Ruecksprung = neues Spiel)
        self.pending_since: float | None = None
        self.before: dict[int, int] = {}       # Stack+Einsatz je Platz, zuletzt als man selbst noch Chips zeigte
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
        """Eine fertige Hand (Reconstructor-Dict). Liefert ein Ergebnis, sobald es feststeht."""
        game = h.get("game_no")
        no = h.get("hand_no")
        seats = {int(k): v for k, v in (h.get("seats") or {}).items()}
        starts = [si.get("start_stack") for si in seats.values()]
        equal_starts = (len(seats) >= 2 and all(isinstance(v, int) and v > 0 for v in starts)
                        and len(set(starts)) == 1)
        # Ruecksprung der Handnummer = neues Spiel, aber nur plausibel (Nummer 1/2 oder alle Stacks gleich):
        # ein einzelner OCR-Verleser '12' -> '1' darf die Zaehlung nicht zuruecksetzen
        restart = (no is not None and self.last_no is not None and no < self.last_no
                   and (no <= 2 or equal_starts))
        if (game is not None and game != self.game) or restart:
            out = self.flush()                     # neues Spiel: offenes Ergebnis des alten gilt
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
            # Startstacks der naechsten Hand sind eingeschwungen (Gewinne nach dem Handwechsel gutgeschrieben)
            if not me_alive:
                return self._result(1 + sum(1 for s in start_alive if s != self.hero), self.pending["hand"])
            self.pending, self.pending_since = None, None   # doch noch Chips bzw. Gegner noch dabei: Lesefehler
        if not me_alive:
            if self.hands:
                self.missing += 1
                if self.missing == 1:
                    self.missing_place = 1 + sum(1 for s in start_alive if s != self.hero)
                if self.missing >= 2:
                    return self._result(self.missing_place, self.last or h)
            return None                             # nicht (mehr) dabei oder unbekannt
        self.missing = 0
        self.last = h
        self.hands += 1
        if self.chips is None and len(seats) >= 2 and all(isinstance(v, int) and v > 0 for v in starts) \
                and ((no is not None and no <= 2) or equal_starts):
            self.chips = sum(starts)        # nur, wenn sicher alle Plaetze gelesen sind (Turnierstart)
        self.field = max(self.field, len(start_alive))
        if self.first_hand_no is None:
            self.first_hand_no = h.get("hand_no")
        end_alive = {s: _alive(si, "end_stack") for s, si in seats.items()}
        if end_alive.get(self.hero) is False:
            others = sum(1 for s, a in end_alive.items() if s != self.hero and a is not False)
            self.pending = {"platz": others + 1, "hand": h}
        elif end_alive.get(self.hero) and len(seats) >= 2 and all(a is False for s, a in end_alive.items()
                                                                 if s != self.hero):
            self.pending = {"platz": 1, "hand": h}  # bestaetigt nach BUST_S ohne neue Hand (on_state) oder am Ende
            self.pending_since = None
        return None

    def on_state(self, state: dict, now: float | None = None) -> dict | None:
        """Tischzustand nach jedem Ereignis: zeigt ein Stack alle Chips des Turniers, ist es vorbei; bleibt
        der eigene Stack BUST_S Sekunden 0 ohne neue Hand, ist man ausgeschieden."""
        if self.reported or not self.hands:
            return None
        opp_chips = [int(k.split(".")[1]) for k, v in state.items() if k.startswith("seat.")
                     and k.endswith(".stack") and isinstance(v, int) and v > 0 and int(k.split(".")[1]) != self.hero
                     and state.get(k[:-len("stack")] + "present") is True]
        if self.pending is not None and self.pending["platz"] == 1 and opp_chips:
            # Der All-in-Gewinner stand beim Handwechsel noch auf 0 (Pot wird spaeter gutgeschrieben): kein Sieg
            self.pending, self.pending_since = None, None
        if now is not None and self.pending is not None and self.pending["platz"] == 1:
            if self.pending_since is None:
                self.pending_since = now
            elif now - self.pending_since >= BUST_S:
                return self._result(1, self.pending["hand"])
        mine = state.get(f"seat.{self.hero}.stack")
        hand = state.get("info.game_hand")
        if now is not None:
            # 0 gelesen, danach oft gar nichts mehr (Tisch weg): unlesbar haelt die Uhr nicht an
            if mine == 0 or (mine is None and self.zero_since is not None):
                if self.zero_since is None or self.zero_since[1] != hand:
                    # Gegner JETZT zaehlen (danach verschwindet der Tisch oft): Ausgeschiedene raeumt PokerTH vom
                    # Tisch, wer noch sitzt, ist dabei - auch wenn sein Stack gerade 0 zeigt (eigenes All-in)
                    # Wer eben noch Chips hatte, zaehlt mit (ein All-in-Gewinner zeigt kurz kein Panel)
                    seated = {int(k.split(".")[1]) for k, v in state.items() if k.startswith("seat.")
                              and k.endswith(".present") and v is True}
                    seated |= {s for s, v in self.before.items() if v > 0}
                    # ... und wer nach der letzten fertigen Hand noch Chips hatte (Stack eben unlesbar/All-in)
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
                        # Heads-up-All-in, man deckt den Gegner: ausscheiden kann nur er -> gewonnen (der
                        # Endbildschirm kommt, bevor der Pot gutgeschrieben ist)
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
                # +-3 % nur, wenn sonst niemand Chips zeigt (mitten in der Hand hat der Gegner noch 150)
                others_have = [s for s in opp_chips if s != seat] or (
                    [self.hero] if seat != self.hero and isinstance(mine, int) and mine > 0 else [])
                if v == self.chips or not others_have:
                    return self._result(1 if seat == self.hero else 2, self.last or {})
        return None

    def activity(self, field: str, value) -> None:
        """Spielaktivitaet eines Gegners (Einsatz, Hervorhebung, Aktionslabel) oder eigene Buttons: die Hand
        laeuft noch, die Ausscheide-Uhr (eigener Stack 0 nach All-in) darf nicht weiterzaehlen."""
        if not value or self.zero_since is None:
            return
        parts = field.split(".")
        if field == "hero.buttons" or (len(parts) == 3 and parts[0] == "seat" and parts[1] != str(self.hero)
                                       and parts[2] in ("bet", "active", "action_label")):
            self.zero_since = None

    def flush(self) -> dict | None:
        """Sitzungsende: ein noch unbestaetigtes Ausscheiden zaehlt."""
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
        self.tracker = OpponentTracker(fuzzy=True)   # fuer die Anzeige (und Bots ohne eigenes Modell)
        if getattr(agent, "tracker", None) is not None:
            agent.tracker.fuzzy = True                # live: verrauschte Namen zusammenfuehren
        self.done = 0
        self.deciding = False
        self.last_key = None
        self.last_shown: tuple | None = None      # (Hand, Strasse, Art, Betrag) des zuletzt gezeigten Vorschlags
        self.pending_since: float | None = None
        self.state: dict = {}
        self._lock = threading.RLock()            # on_event/poll kommen aus Analyse- und Hauptthread

    def _relevant(self, f: str) -> bool:
        """Felder, nach deren Aenderung ein Vorschlag neu berechnet wird, solange man dran ist."""
        return (f.startswith("board.") or f in (f"seat.{self.hero}.cards", f"seat.{self.hero}.stack")
                or f.endswith(".bet") or f in ("info.game_hand", "pot.total", "info.street")
                or f.endswith(".folded"))

    def on_event(self, ev: dict, state: dict, now: float):
        """Ein Ereignis verarbeiten (now = Zeit in Sekunden, gleiche Uhr wie bei poll()).
        Die Buttons zeigen an, ob man dran ist. Karten, Board und Einsaetze werden manchmal erst kurz
        nach den Buttons erkannt; deshalb erscheint ein Vorschlag erst, wenn die Lage SETTLE_S ruhig
        ist (poll), und wird neu berechnet, wenn sich danach noch etwas aendert."""
        with self._lock:
            self.feed(ev)
            self.state = state
            f = ev.get("field", "")
            self.watch.activity(f, ev.get("new"))
            was = self.deciding
            # Tisch weg: alte Buttons/Hervorhebung bleiben im Zustand stehen, zaehlen aber nicht
            self.deciding = state.get("table.found") is not False and is_decision(state, self.hero)
            if not self.deciding:
                self.pending_since = None
                self.last_key = None
            elif not was or f == "hero.buttons" or self._relevant(f):
                self.pending_since = now
            return self.poll(now)

    def poll(self, now: float):
        """Liefert (Vorschlag, Observation, Gegner), sobald eine neue Entscheidungslage ruhig ist, sonst None.
        Wird je analysiertem Bild aufgerufen - auch ohne neue Ereignisse (z. B. nach dem eigenen Ausscheiden)."""
        with self._lock:
            res = self.watch.on_state(self.state, now)
            if res and self.on_result:
                self.on_result(res)
            if not self.deciding or self.pending_since is None or now - self.pending_since < SETTLE_S:
                return None
            if not self.playable(self.state):
                return None                               # pending_since bleibt: naechstes Bild prueft erneut
            self.pending_since = None
            obs = self.observation(self.state)
            # billige Pruefungen VOR dem Agenten (die Suche rechnet Sekunden)
            if not obs.hole_cards:
                return None                               # keine eigenen Karten (z. B. schon gefoldet)
            if set(obs.hole_cards) & set(obs.board) or len(obs.board) not in (0, 3, 4, 5):
                return None                               # Zwischenzustand (z. B. Handwechsel)
            if not any(obs.in_hand[s] and not obs.folded[s] for s in range(obs.num_seats) if s != obs.seat):
                return None                               # alle anderen gefoldet: Hand gewonnen, nichts zu tun
            sug = sane(self.agent.act(obs), obs)
            key = (obs.hand_id, tuple(obs.hole_cards), tuple(obs.board), obs.to_call, str(sug))
            if key == self.last_key or self.same_as_shown(sug, obs):
                return None
            self.last_key = key
            self.last_shown = (obs.hand_id, tuple(obs.hole_cards), obs.street, sug.kind,
                               sug.amount if sug.kind == "raise" else obs.to_call)
            return sug, obs, self.opponents(obs)

    def playable(self, state: dict) -> bool:
        """Nur echte Entscheidungen: Tisch erkannt und eigener Stack lesbar > 0. Nach dem eigenen All-in, nach
        Handende (Endbildschirm, Tisch weg) und bei unlesbarem Stack gibt es keinen Vorschlag."""
        if state.get("table.found") is False:
            return False
        st = state.get(f"seat.{self.hero}.stack")
        return isinstance(st, int) and st > 0

    def same_as_shown(self, sug, obs) -> bool:
        """Gleiche Strasse, gleiche Art, Betrag kaum anders: die Leiste nicht neu anstossen (kein Flackern
        durch nachhinkende Einsaetze/Pots)."""
        if self.last_shown is None or sug is None:
            return False
        hand, cards, street, kind, amount = self.last_shown
        # Karten mit im Schluessel: die Handnummer wird manchmal ueber mehrere Haende nicht neu gelesen
        if (hand, cards, street, kind) != (obs.hand_id, tuple(obs.hole_cards), obs.street, sug.kind):
            return False
        # Betrag: bei Raise der Zielbetrag, sonst der zu zahlende Betrag (ein Re-Raise des Gegners ist eine
        # neue Entscheidung, auch wenn die Antwort wieder 'Call' heisst)
        cur = sug.amount if kind == "raise" else obs.to_call
        return abs((cur or 0) - (amount or 0)) <= SAME_AMOUNT * max(cur or 0, amount or 0, 1)

    def feed(self, ev: dict):
        """Jedes Collector-Ereignis (wie in observations.jsonl) in Eingangsreihenfolge."""
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
        """Sitzungsende: offene Hand abschliessen und ein unbestaetigtes Ergebnis melden."""
        with self._lock:
            if self.rec.hand is not None:
                self.rec.finish()
                self._drain()
            res = self.watch.flush()
            if res and self.on_result:
                self.on_result(res)

    def session_ended(self):
        """Aufnahme beendet (Tisch laenger weg): offenes Ergebnis melden, Rekonstruktion fuer die naechste
        Aufnahme frisch starten. Eine laufende Ausscheide-Uhr gilt als abgelaufen (der Tisch ist weg)."""
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
        if by_board and by_board != obs.street:          # Strassenanzeige hinkt nach, Boardkarten nicht
            obs = replace(obs, street=by_board)
        h = self.rec.hand
        if h is None:
            return obs
        hd = h.to_dict()
        hist = public_history(hd, self.n)
        order = ("preflop", "flop", "turn", "river")
        if hist and order.index(hist[-1].street) > order.index(obs.street):
            return obs                            # Rekonstruktion und Bild uneins: lieber ohne Verlauf
        unc = [u for u in obs.uncertain if u != "Aktionsverlauf live nicht enthalten"]
        unc.append("Verlauf aus Live-Rekonstruktion (kann kurz nachhinken)")
        obs = drop_stale_bets(obs, hd)
        committed = obs.committed
        hist_pot = sum(a.added for a in hist)
        if hist_pot > 0 and obs.pot < 0.9 * hist_pot:
            # Pot im Bild fehlt/zu klein (z. B. 'Gesamt: $O'): aus dem rekonstruierten Verlauf nehmen
            committed = list(obs.bets)
            committed[obs.button] += max(0, hist_pot - sum(obs.bets))
            unc = [u for u in unc if u != "Pot unbekannt oder widerspruechlich"] + ["Pot aus Live-Verlauf"]
        return replace(obs, history=hist, uncertain=unc, committed=committed)

    def opponents(self, obs: Observation) -> list[tuple[str, dict]]:
        """Gegner in der Hand mit ihren Statistiken (Name, Werte) fuer die Anzeige."""
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
    """Spielt eine aufgezeichnete Sitzung wie live ab: liefert jeden Vorschlag, den man live gesehen
    haette (Vorschlag, Observation, Gegnerliste, Ereignis). Zustand = Felder bis zu diesem Ereignis."""
    bot = LiveBot(agent, hero_seat)
    state: dict = {}
    # wie live: Reihenfolge des Journals (seq), nur stabile Werte ('change') bzw. Unlesbares ('unknown')
    usable = [e for e in events if "seq" in e and e.get("kind") in ("change", "unknown")]
    for ev in sorted(usable, key=lambda e: e["seq"]):
        t = ev.get("t_first", 0.0)
        out = bot.poll(t)                     # Ruhezeit seit dem letzten Ereignis vergangen?
        if out:
            yield (*out, ev)
        state[ev["field"]] = ev.get("new") if ev.get("kind") == "change" else None
        out = bot.on_event(ev, dict(state), t)
        if out:
            yield (*out, ev)
    out = bot.poll(float("inf"))
    if out:
        yield (*out, {"seq": "Ende"})
