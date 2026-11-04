from helpers import EventStream, standard_hand, table

from pokercollector.reconstruct import reconstruct


def summary(h):
    return [(a.street, a.seat, a.type, a.amount_to if a.type != "collect" else a.added, a.source.split("+")[0])
            for a in h.actions]


def test_standard_hand_is_complete():
    es = table(EventStream())
    standard_hand(es)
    es.at(12.0, info__game_hand=[1, 2])
    hands = reconstruct(es.events)
    h = hands[0]
    assert summary(h) == [
        ("preflop", 1, "post_sb", 10, "derived_bet"),
        ("preflop", 2, "post_bb", 20, "derived_bet"),
        ("preflop", 3, "fold", None, "observed_fold"),
        ("preflop", 0, "call", 20, "derived_bet"),
        ("preflop", 1, "raise", 60, "derived_bet"),
        ("preflop", 2, "fold", None, "observed_fold"),
        ("preflop", 0, "call", 60, "derived_bet"),
        ("flop", 1, "check", None, "derived_turn"),
        ("flop", 0, "bet", 100, "derived_bet"),
        ("flop", 1, "fold", None, "observed_fold"),
        ("flop", 0, "collect", 240, "derived_stack"),
    ]
    assert h.status == "complete", h.status_reasons
    assert (h.dealer, h.sb_seat, h.bb_seat, h.blinds) == (0, 1, 2, [10, 20])
    assert h.board[:3] == ["Ah", "7c", "2d"]
    assert h.seats[0].start_stack == 3000 and h.seats[1].start_stack == 3000
    assert h.contradictions == [] and h.gaps == []
    # Zweite Hand wurde begonnen, aber nicht beendet -> partiell
    assert hands[1].hand_no == 2 and hands[1].status == "partial"


def test_missed_action_is_reported_not_invented():
    es = table(EventStream())
    standard_hand(es, skip_hero_flop=True)
    es.at(12.0, info__game_hand=[1, 2])
    h = reconstruct(es.events)[0]
    flop = [(a.seat, a.type, a.source) for a in h.actions if a.street == "flop"]
    # Hero-Aktion auf dem Flop fehlt im Bild: als unbekannt markiert, nicht erfunden
    assert (0, "unknown", "inferred_gap") in flop
    assert h.status == "partial"
    assert any("nicht beobachtet" in g for g in h.gaps)


def test_bet_decrease_without_street_change_is_contradiction():
    es = table(EventStream())
    es.at(0.0, marker__D=0, marker__SB=1, marker__BB=2, info__blinds=[10, 20])
    es.at(0.1, info__game_hand=[1, 1])
    es.at(0.3, seat__1__bet=10)
    es.at(0.35, seat__2__bet=20)
    es.at(5.0, seat__0__bet=60)
    es.at(9.0, seat__0__bet=40)
    h = reconstruct(es.events)[0]
    assert any("sinkt" in c for c in h.contradictions)


def test_check_label_is_observed():
    es = table(EventStream())
    es.at(0.0, marker__D=0, marker__SB=1, marker__BB=2, info__blinds=[10, 20])
    es.at(0.1, info__game_hand=[1, 1])
    es.at(0.3, seat__1__bet=10)
    es.at(0.35, seat__2__bet=20)
    es.at(1.0, seat__3__folded=True)
    es.at(1.5, seat__0__bet=20)
    es.at(2.0, seat__1__bet=20)
    es.at(2.5, seat__2__action_label="check")
    h = reconstruct(es.events)[0]
    assert ("preflop", 2, "check", None, "observed_label") in summary(h)


def test_stale_bet_from_previous_hand_is_ignored():
    # Hand 1 endet mit Einsatz 300 von Sitz 0; die Zeile steht nach dem Handwechsel noch kurz da
    es = table(EventStream())
    standard_hand(es)
    es.at(10.5, seat__0__bet=300)
    es.at(12.0, info__game_hand=[1, 2], marker__D=1)
    es.at(12.6, marker__SB=2, marker__BB=3, board__count=0)
    es.at(12.8, seat__2__bet=10, seat__3__bet=20)
    es.at(14.0, seat__0__bet=0)
    es.at(16.0, seat__0__bet=60)
    h = reconstruct(es.events)[1]
    pre = [(a.seat, a.type, a.amount_to) for a in h.actions if a.street == "preflop" and a.type != "unknown"]
    assert (2, "post_sb", 10) in pre and (3, "post_bb", 20) in pre
    assert (0, "raise", 60) in pre and not any(a[2] == 300 for a in pre)
    assert (h.dealer, h.sb_seat, h.bb_seat) == (1, 2, 3)


def test_late_fold_goes_to_previous_street_and_calls_are_inferred():
    es = table(EventStream())
    es.at(0.0, marker__D=0, marker__SB=1, marker__BB=2, info__blinds=[10, 20])
    es.at(0.1, info__game_hand=[1, 1], board__count=0)
    es.at(0.3, seat__1__bet=10, seat__2__bet=20)
    es.at(3.0, seat__0__bet=60)
    es.at(4.0, seat__1__folded=True)
    # Sitz 2 callt (nicht gesehen, Einsaetze sofort eingesammelt), Sitz 3 foldet - erst nach dem Flop gelesen
    es.at(6.0, board__count=3, board__cards=["Ah", "7c", "2d", None, None], info__street="flop",
          seat__0__bet=0, seat__1__bet=0, seat__2__bet=0)
    es.at(6.5, seat__3__folded=True)
    es.at(9.0, seat__2__action_label="check")
    h = reconstruct(es.events)[0]
    pre = [(a.seat, a.type, a.source.split("+")[0]) for a in h.actions if a.street == "preflop"]
    assert (3, "fold", "observed_fold") in pre                       # verspaeteter Fold in der richtigen Strasse
    assert (2, "call", "inferred_street_end") in pre                 # abschliessender Call erschlossen
    assert not any(a.street == "flop" and a.seat == 3 for a in h.actions)


def test_board_majority_vote():
    es = table(EventStream())
    standard_hand(es)
    es.at(6.5, board__cards=["Ah", "1c", "2d", None, None])          # einmalige Fehllesung
    es.at(7.0, board__cards=["Ah", "7c", "2d", None, None])
    es.at(7.5, board__cards=["Ah", "7c", "2d", None, None])
    h = reconstruct(es.events)[0]
    assert h.board[:3] == ["Ah", "7c", "2d"]


def test_seat_memory_keeps_numbers_when_a_player_leaves():
    from pokercollector.layout import SeatMemory
    m = SeatMemory(0.06)
    six = [(0.5, 0.7), (0.25, 0.65), (0.15, 0.3), (0.5, 0.1), (0.85, 0.3), (0.75, 0.65)]
    assert m.assign(six, hero=0) == [0, 1, 2, 3, 4, 5]               # im Uhrzeigersinn ab dem eigenen Platz
    five = [c for i, c in enumerate(six) if i != 3]                  # Spieler oben ist ausgeschieden
    assert m.assign(five, hero=0) == [0, 1, 2, 4, 5]
