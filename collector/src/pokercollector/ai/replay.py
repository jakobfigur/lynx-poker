"""Bruecke Collector -> Observation.

- decision_points(hand): rekonstruierte Hand (hands.json) -> Spielerblick vor jeder
  eigenen Entscheidung + tatsaechliche Aktion. Damit kann jeder Agent deine echten
  Entscheidungen im Replay bewerten.
- observation_from_table_state(state): stabilisierter Live-Zustand -> Spielerblick.

Was aus den Daten nicht sicher hervorgeht, steht in Observation.uncertain.
"""

from __future__ import annotations

from .observation import Observation, PublicAction

BOARD_COUNT = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}
DECISION_TYPES = ("fold", "check", "call", "bet", "raise")


def decision_points(hand: dict, hero_seat: int = 0, num_seats: int = 10) -> list[tuple[Observation, dict]]:
    seats = {int(k): v for k, v in hand.get("seats", {}).items()}
    hero = seats.get(hero_seat, {})
    hole = hero.get("cards") or []
    blinds = hand.get("blinds") or [None, None]
    uncertain_base = []
    if hand.get("status") != "complete":
        uncertain_base.append("Hand unvollstaendig: " + "; ".join(hand.get("status_reasons", [])))
    if len(hole) != 2 or any(c in (None, "??") for c in hole):
        uncertain_base.append("eigene Karten unbekannt")
        hole = []
    in_hand = [s in seats for s in range(num_seats)]
    start = [seats.get(s, {}).get("start_stack") for s in range(num_seats)]
    if any(in_hand[s] and start[s] is None for s in range(num_seats)):
        uncertain_base.append("Startstack(s) unbekannt")
    stacks = [start[s] or 0 for s in range(num_seats)]
    bets = [0] * num_seats
    committed = [0] * num_seats
    folded = [False] * num_seats
    allin = [False] * num_seats
    history: list[PublicAction] = []
    street = "preflop"
    current_bet = 0
    min_inc = blinds[1] or 0
    board_all = hand.get("board") or [None] * 5
    out = []
    for a in hand.get("actions", []):
        if a["street"] != street:
            street = a["street"]
            bets = [0] * num_seats
            current_bet = 0
            min_inc = blinds[1] or 0
        s = a["seat"]
        typ = a["type"]
        if s == hero_seat and typ in DECISION_TYPES:
            to_call = max(0, current_bet - bets[s])
            unc = list(uncertain_base)
            if any(x["type"] == "unknown" for x in hand.get("actions", [])):
                unc.append("Aktionsfolge hat Luecken")
            board = [c for c in board_all[:BOARD_COUNT[street]] if c]
            if len(board) != BOARD_COUNT[street]:
                unc.append("Boardkarten unvollstaendig")
            max_to = bets[s] + stacks[s]
            obs = Observation(
                seat=s, num_seats=num_seats, hole_cards=list(hole), board=board, street=street,
                button=hand.get("dealer") if hand.get("dealer") is not None else 0,
                sb_seat=hand.get("sb_seat"), bb_seat=hand.get("bb_seat"),
                big_blind=blinds[1] or 0, small_blind=blinds[0] or 0, stacks=list(stacks), bets=list(bets),
                committed=list(committed), folded=list(folded), allin=list(allin), in_hand=list(in_hand),
                history=list(history), to_call=min(to_call, stacks[s]), can_check=to_call == 0,
                can_raise=max_to > current_bet, min_raise_to=min(current_bet + max(min_inc, 1), max_to),
                max_raise_to=max_to, hand_id=f"{hand.get('game_no')}-{hand.get('hand_no')}",
                names=[seats.get(x, {}).get("name") for x in range(num_seats)], source="replay", uncertain=unc)
            out.append((obs, a))
        # Zustand fortschreiben
        if typ == "fold":
            folded[s] = True
            history.append(PublicAction(street, s, "fold", None, 0))
        elif typ in ("check",):
            history.append(PublicAction(street, s, "check", bets[s], 0))
        elif typ in ("post_sb", "post_bb", "call", "bet", "raise"):
            added = a.get("added") or 0
            to = a.get("amount_to") if a.get("amount_to") is not None else bets[s] + added
            added = to - bets[s]
            if typ in ("bet", "raise"):
                inc = to - current_bet
                if inc >= min_inc:
                    min_inc = inc
            stacks[s] -= added
            bets[s] = to
            committed[s] += added
            current_bet = max(current_bet, to)
            if a.get("allin") or stacks[s] <= 0:
                allin[s] = True
            history.append(PublicAction(street, s, typ, to, added, allin[s]))
    return out


def live_pot(st: dict, bets: list[int], bb: int, unc: list[str]) -> int | None:
    """Pot inkl. laufender Einsaetze. Zwei Quellen im Bild: die Pot-Anzeige in der Tischmitte (pot.total,
    fehlt bei manchen Tischen ganz und hat OCR-Ausreisser wie 9280 statt 280) und 'Gesamt' im Infofeld
    (info.total = eingesammelter Pot OHNE die Einsaetze der laufenden Strasse). Die Mitte gilt, wenn sie
    zu Gesamt + Einsaetze passt; sonst zaehlt Gesamt + Einsaetze."""
    center = st.get("pot.total")
    if center is not None and center < sum(bets):
        center = None
    total = st.get("info.total")
    est = total + sum(bets) if isinstance(total, int) else None
    if center is not None and (est is None or abs(center - est) <= max(0.1 * est, bb or 0)):
        return center
    if est is not None and est > 0:
        unc.append("Pot aus 'Gesamt' + Einsaetzen")
        return est
    return center


def observation_from_table_state(st: dict, hero_seat: int = 0, num_seats: int = 10) -> Observation:
    """Live: Spielerblick aus dem stabilisierten Feldzustand des Collectors.
    Der Aktionsverlauf der laufenden Hand ist hier nicht enthalten (-> uncertain)."""
    unc = ["Aktionsverlauf live nicht enthalten"]
    hole = st.get(f"seat.{hero_seat}.cards") or []
    if len(hole) != 2 or "??" in hole:
        unc.append("eigene Karten unbekannt")
        hole = []
    board = [c for c in (st.get("board.cards") or []) if c and c != "??"]
    street = st.get("info.street")
    if street not in ("preflop", "flop", "turn", "river"):      # fehlt oder 'showdown'
        street = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}.get(len(board), "preflop")
    in_hand = [bool(st.get(f"seat.{s}.present")) and st.get(f"seat.{s}.cards_state") in ("backs", "faces")
               or (s == hero_seat and bool(hole)) for s in range(num_seats)]
    folded = [bool(st.get(f"seat.{s}.folded")) for s in range(num_seats)]
    raw_stacks = [st.get(f"seat.{s}.stack") for s in range(num_seats)]
    stacks = [v if isinstance(v, int) else 0 for v in raw_stacks]
    if any(st.get(f"seat.{s}.present") and raw_stacks[s] is None for s in range(num_seats)):
        unc.append("Stack eines Spielers unlesbar")
    bets = [st.get(f"seat.{s}.bet") or 0 for s in range(num_seats)]
    pot = live_pot(st, bets, (st.get("info.blinds") or [0, 0])[1], unc)
    committed = list(bets)
    if pot is not None and pot >= sum(bets):
        # Frueher eingezahlte Chips sind nicht pro Spieler sichtbar: dem Hero-Feld nicht
        # zurechnen, sondern als 'tote' Summe beim Button fuehren (nur fuer Pot-Groesse).
        committed[st.get("marker.D") or 0] += pot - sum(bets)
    else:
        unc.append("Pot unbekannt oder widerspruechlich")
    buttons = st.get("hero.buttons") or []
    to_call, can_check, min_to = None, False, None
    for b in buttons:
        if b.get("action") == "call":
            to_call = b.get("amount")
        elif b.get("action") == "check":
            to_call, can_check = 0, True
        elif b.get("action") in ("raise", "bet"):
            min_to = b.get("amount")
    if to_call is None:
        to_call = max(0, max(bets) - bets[hero_seat])
        can_check = to_call == 0
        unc.append("zu callender Betrag aus Einsaetzen geschaetzt")
    blinds = st.get("info.blinds") or [0, 0]
    max_to = bets[hero_seat] + stacks[hero_seat]
    if min_to is not None and blinds[1]:
        min_to = min(max_to, max(min_to, max(bets) + blinds[1]))     # Button-Betrag kann zu klein gelesen sein
    alive = [s for s in range(num_seats) if st.get(f"seat.{s}.present") and (stacks[s] > 0 or bets[s] > 0)]
    extra = st.get("info.blinds_extra")
    tournament = {
        "sb": blinds[0], "bb": blinds[1], "players_left": len(alive),
        "average_stack": round(sum(stacks[s] + bets[s] for s in alive) / len(alive)) if alive else None,
        # Anzeige '↑8' neben den Blinds: vermutlich Haende bis zur naechsten Stufe (ungeprueft)
        "hands_to_next_level": int(extra) if isinstance(extra, str) and extra.isdigit() else None,
    }
    if tournament["hands_to_next_level"] is not None:
        unc.append("Haende bis Blinderhoehung aus '↑'-Anzeige gedeutet (ungeprueft)")
    return Observation(
        seat=hero_seat, num_seats=num_seats, hole_cards=hole, board=board, street=street,
        button=st.get("marker.D") or 0, sb_seat=st.get("marker.SB"), bb_seat=st.get("marker.BB"),
        big_blind=blinds[1], small_blind=blinds[0], stacks=stacks, bets=bets, committed=committed,
        folded=folded, allin=[in_hand[s] and raw_stacks[s] == 0 for s in range(num_seats)], in_hand=in_hand,
        history=[], to_call=to_call, can_check=can_check, can_raise=min_to is not None,
        min_raise_to=min_to, max_raise_to=max_to if min_to is not None else None,
        hand_id=str(st.get("info.game_hand")), names=[st.get(f"seat.{s}.name") for s in range(num_seats)],
        source="live", uncertain=unc, tournament=tournament)


def review_hands(hands: list[dict], agent, hero_seat: int = 0) -> list[dict]:
    """Fragt den Agenten an jeder eigenen Entscheidung und stellt Vorschlag und echte Aktion gegenueber."""
    rows = []
    for h in hands:
        for obs, actual in decision_points(h, hero_seat):
            if not obs.hole_cards:
                rows.append({"hand": obs.hand_id, "street": obs.street, "actual": actual["type"],
                             "suggested": None, "note": "eigene Karten unbekannt", "uncertain": obs.uncertain})
                continue
            sug = agent.act(obs)
            actual_kind = {"bet": "raise", "raise": "raise"}.get(actual["type"], actual["type"])
            rows.append({
                "hand": obs.hand_id, "street": obs.street, "cards": obs.hole_cards, "board": obs.board,
                "pot": obs.pot, "to_call": obs.to_call,
                "actual": actual["type"] + (f" {actual.get('amount_to')}" if actual["type"] in ("bet", "raise") else ""),
                "suggested": str(sug), "same": sug.kind == actual_kind, "uncertain": obs.uncertain,
            })
    return rows
