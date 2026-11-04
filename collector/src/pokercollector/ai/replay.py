"""Bridge Collector -> Observation.

- decision_points(hand): reconstructed hand (hands.json) -> player perspective before each
  own decision + actual action. This allows any agent to evaluate your true
  decisions in replay.
- observation_from_table_state(state): stabilized live state -> player perspective.

What is not clearly extractable from the data is stored in Observation.uncertain.
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
        uncertain_base.append('Hand incomplete: ' + "; ".join(hand.get("status_reasons", [])))
    if len(hole) != 2 or any(c in (None, "??") for c in hole):
        uncertain_base.append('own cards unknown')
        hole = []
    in_hand = [s in seats for s in range(num_seats)]
    start = [seats.get(s, {}).get("start_stack") for s in range(num_seats)]
    if any(in_hand[s] and start[s] is None for s in range(num_seats)):
        uncertain_base.append('Starting stack(s) unknown')
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
                unc.append('Action sequence has gaps')
            board = [c for c in board_all[:BOARD_COUNT[street]] if c]
            if len(board) != BOARD_COUNT[street]:
                unc.append('Board cards incomplete')
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
        #Advance state
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
    """Pot including ongoing bets. Two sources in the image: the pot display in center of the table (pot.total,
    missing entirely on some tables and has OCR outliers like 9280 instead of 280) and 'total' in the info field
    (info.total = collected pot WITHOUT ongoing street bets). Center is valid if it matches
    total + bets; otherwise total + bets count."""
    center = st.get("pot.total")
    if center is not None and center < sum(bets):
        center = None
    total = st.get("info.total")
    est = total + sum(bets) if isinstance(total, int) else None
    if center is not None and (est is None or abs(center - est) <= max(0.1 * est, bb or 0)):
        return center
    if est is not None and est > 0:
        unc.append("Pot from 'Total' + bets")
        return est
    return center


def observation_from_table_state(st: dict, hero_seat: int = 0, num_seats: int = 10) -> Observation:
    """Live: player perspective from the stabilized field state of the collector.
    The action history of the current hand is not included here (-> uncertain)."""
    unc = ['Action history not included live']
    hole = st.get(f"seat.{hero_seat}.cards") or []
    if len(hole) != 2 or "??" in hole:
        unc.append('own cards unknown')
        hole = []
    board = [c for c in (st.get("board.cards") or []) if c and c != "??"]
    street = st.get("info.street")
    if street not in ("preflop", "flop", "turn", "river"):      # missing or 'showdown'
        street = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}.get(len(board), "preflop")
    in_hand = [bool(st.get(f"seat.{s}.present")) and st.get(f"seat.{s}.cards_state") in ("backs", "faces")
               or (s == hero_seat and bool(hole)) for s in range(num_seats)]
    folded = [bool(st.get(f"seat.{s}.folded")) for s in range(num_seats)]
    raw_stacks = [st.get(f"seat.{s}.stack") for s in range(num_seats)]
    stacks = [v if isinstance(v, int) else 0 for v in raw_stacks]
    if any(st.get(f"seat.{s}.present") and raw_stacks[s] is None for s in range(num_seats)):
        unc.append('Stack of a player unreadable')
    bets = [st.get(f"seat.{s}.bet") or 0 for s in range(num_seats)]
    pot = live_pot(st, bets, (st.get("info.blinds") or [0, 0])[1], unc)
    committed = list(bets)
    if pot is not None and pot >= sum(bets):
        # Previously posted chips are not visible per player: not attributed to the Hero field
        # but counted as 'dead' sum at the button (only for pot size).
        committed[st.get("marker.D") or 0] += pot - sum(bets)
    else:
        unc.append('Pot unknown or inconsistent')
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
        unc.append('Amount to call estimated from bets')
    blinds = st.get("info.blinds") or [0, 0]
    max_to = bets[hero_seat] + stacks[hero_seat]
    if min_to is not None and blinds[1]:
        min_to = min(max_to, max(min_to, max(bets) + blinds[1]))     # Button amount may be read too low
    alive = [s for s in range(num_seats) if st.get(f"seat.{s}.present") and (stacks[s] > 0 or bets[s] > 0)]
    extra = st.get("info.blinds_extra")
    tournament = {
        "sb": blinds[0], "bb": blinds[1], "players_left": len(alive),
        "average_stack": round(sum(stacks[s] + bets[s] for s in alive) / len(alive)) if alive else None,
        # Display '↑8' next to blinds: probably hands until next level (unchecked)
        "hands_to_next_level": int(extra) if isinstance(extra, str) and extra.isdigit() else None,
    }
    if tournament["hands_to_next_level"] is not None:
        unc.append("Hands until blind raise interpreted from '↑' display (unchecked)")
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
    """Asks the agent at each own decision and compares proposal and true action."""
    rows = []
    for h in hands:
        for obs, actual in decision_points(h, hero_seat):
            if not obs.hole_cards:
                rows.append({"hand": obs.hand_id, "street": obs.street, "actual": actual["type"],
                             "suggested": None, "note": 'own cards unknown', "uncertain": obs.uncertain})
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
