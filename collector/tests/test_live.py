from pokercollector.ai.live import is_decision, public_history
from pokercollector.ai.opponents import OpponentTracker

BUTTONS = [{"action": "fold"}, {"action": "call", "amount": 20}, {"action": "raise", "amount": 40}]


def test_is_decision_needs_highlight_and_call_or_check():
    assert is_decision({"seat.0.active": True, "hero.buttons": BUTTONS})
    assert not is_decision({"seat.0.active": False, "hero.buttons": BUTTONS})        # Preselection
    assert not is_decision({"seat.0.active": True, "hero.buttons": [{"action": "fold"}]})


HAND = {
    "seats": {"0": {"name": "me", "start_stack": 1000}, "1": {"name": "Wild", "start_stack": 1000},
              "2": {"name": "Rock", "start_stack": 1000}},
    "actions": [
        {"street": "preflop", "seat": 1, "type": "post_sb", "amount_to": 10},
        {"street": "preflop", "seat": 2, "type": "post_bb", "amount_to": 20},
        {"street": "preflop", "seat": 0, "type": "call", "amount_to": 20},
        {"street": "preflop", "seat": 1, "type": "raise", "amount_to": 80},
        {"street": "preflop", "seat": 2, "type": "fold"},
        {"street": "preflop", "seat": 0, "type": "call", "amount_to": 80},
        {"street": "flop", "seat": 1, "type": "bet", "amount_to": 100},
        {"street": "flop", "seat": 0, "type": "unknown"},
    ],
}


def test_public_history_from_collector_hand():
    h = public_history(HAND)
    assert [(a.street, a.seat, a.kind, a.amount_to) for a in h][:4] == [
        ("preflop", 1, "post_sb", 10), ("preflop", 2, "post_bb", 20), ("preflop", 0, "call", 20),
        ("preflop", 1, "raise", 80)]
    assert h[-1].street == "flop" and h[-1].added == 100 and len(h) == 7      # 'unknown' eliminated


def test_tracker_from_collector_hand():
    t = OpponentTracker()
    t.update_collector(HAND, 0)
    wild, rock = t.c["Wild"], t.c["Rock"]
    assert wild["hands"] == rock["hands"] == 1 and "me" not in t.c
    assert wild["vpip"] == wild["pfr"] == 1 and wild["aggr"] == 1
    assert rock["vpip"] == 0 and rock["pfr"] == 0


def test_live_pot_quellen():
    from pokercollector.ai.replay import live_pot
    unc = []
    # Middle matches total + bets
    assert live_pot({"pot.total": 280, "info.total": 260}, [20, 0], 20, unc) == 280 and not unc
    # Middle with OCR outlier (9280 instead of 280) -> total + bets
    assert live_pot({"pot.total": 9280, "info.total": 260}, [20, 0], 20, unc) == 280 and unc
    # Middle completely missing (some tables) -> total + bets
    assert live_pot({"info.total": 172}, [40, 40], 20, []) == 252
    # nothing known
    assert live_pot({}, [10, 20], 20, []) is None


def _hand(game, no, stacks):
    'stacks: {seat: (start, end)}'
    return {"game_no": game, "hand_no": no,
            "seats": {str(s): {"start_stack": a, "end_stack": b} for s, (a, b) in stacks.items()}}


def test_turnier_ausgeschieden_platz_aus_naechster_hand():
    from pokercollector.ai.live import TournamentWatch
    w = TournamentWatch(0)
    assert w.on_hand(_hand(1, 1, {0: (5000, 4000), 1: (5000, 6000), 2: (5000, 5000), 3: (5000, 5000)})) is None
    assert w.on_hand(_hand(1, 2, {0: (4000, 0), 1: (6000, 10000), 2: (5000, 5000), 3: (5000, 0)})) is None
    # next hand: me without chips, two opponents left -> 3rd place (seat 3 is out in the same hand)
    res = w.on_hand(_hand(1, 3, {0: (0, 0), 1: (10000, 9000), 2: (5000, 6000)}))
    assert res["platz"] == 3 and res["spieler"] == 4 and res["haende"] == 2 and not res["start_verpasst"]
    assert w.on_hand(_hand(1, 4, {1: (9000, 0), 2: (6000, 15000)})) is None      # only once per game


def test_turnier_ocr_null_ist_kein_ende():
    from pokercollector.ai.live import TournamentWatch
    w = TournamentWatch(0)
    w.on_hand(_hand(1, 1, {0: (5000, 0), 1: (5000, 5000)}))       # '0' misread
    assert w.pending is not None
    assert w.on_hand(_hand(1, 2, {0: (5000, 5000), 1: (5000, 5000)})) is None
    assert w.pending is None and w.flush() is None


def test_turnier_sieg_bei_sitzungsende_und_neues_spiel():
    from pokercollector.ai.live import TournamentWatch
    w = TournamentWatch(0)
    w.on_hand(_hand(1, 7, {0: (6000, 6000), 1: (2000, 2000), 2: (2000, 2000)}))
    w.on_hand(_hand(1, 8, {0: (6000, 10000), 1: (2000, 0), 2: (2000, 0)}))
    res = w.flush()
    assert res["platz"] == 1 and res["spieler"] == 3 and res["start_verpasst"]
    # new game: elimination reported on change
    w.on_hand(_hand(2, 1, {0: (5000, 0), 1: (5000, 10000)}))
    res = w.on_hand(_hand(3, 1, {0: (5000, 5000), 1: (5000, 5000)}))
    assert res["platz"] == 2 and res["spiel"] == 2


def test_livebot_meldet_ergebnis_beim_schliessen():
    from pokercollector.ai.live import LiveBot
    got = []
    bot = LiveBot(agent=object(), on_result=got.append)
    bot.watch.on_hand(_hand(1, 1, {0: (5000, 0), 1: (5000, 10000)}))
    bot.close()
    assert got and got[0]["platz"] == 2


def test_turnier_endbildschirm_alle_chips():
    from pokercollector.ai.live import TournamentWatch
    w = TournamentWatch(0)
    w.on_hand(_hand(1, 1, {0: (3000, 3000), 1: (3000, 3000)}))
    assert w.chips == 6000
    assert w.on_state({"seat.0.stack": 3055, "seat.1.stack": 2465}) is None
    assert w.on_state({"seat.0.stack": 6000, "seat.1.stack": None})["platz"] == 1
    w2 = TournamentWatch(0)
    w2.on_hand(_hand(1, 1, {0: (3000, 3000), 1: (3000, 3000)}))
    assert w2.on_state({"seat.1.stack": 5990})["platz"] == 2


def test_turnier_zwei_haende_ohne_eigene_chips():
    from pokercollector.ai.live import TournamentWatch
    w = TournamentWatch(0)
    w.on_hand(_hand(1, 1, {0: (2000, 2000), 1: (2000, 2000), 2: (2000, 2000)}))   # end not readable
    assert w.on_hand(_hand(1, 2, {1: (3000, 3000), 2: (3000, 3000)})) is None
    res = w.on_hand(_hand(1, 3, {1: (3000, 3000), 2: (3000, 3000)}))
    assert res["platz"] == 3


def _obs(**kw):
    from pokercollector.ai.observation import Observation
    base = dict(seat=0, num_seats=3, hole_cards=["As", "Kd"], board=[], street="preflop", button=0, sb_seat=1,
                bb_seat=2, big_blind=20, small_blind=10, stacks=[1000, 500, 0], bets=[0, 10, 600],
                committed=[0, 10, 600], folded=[False, False, False], allin=[False, False, True],
                in_hand=[True, True, True], history=[], to_call=600, can_check=False, can_raise=True,
                min_raise_to=1200, max_raise_to=1000)
    base.update(kw)
    return Observation(**base)


def test_sane_vorschlag():
    from pokercollector.ai.live import sane
    from pokercollector.ai.observation import Action
    o = _obs()
    assert str(sane(Action("raise", 5000), o)) == "raise 1000"          # never more than own stack
    assert str(sane(Action("raise", 0), o)) == "call"                   # 'raise 0' -> call
    o2 = _obs(folded=[False, True, False])                              # only opponent already all-in
    assert str(sane(Action("raise", 1000), o2)) == "call"
    assert str(sane(Action("fold"), o)) == "fold"


def test_livebot_keine_vorschlaege_ohne_stack_oder_tisch():
    from pokercollector.ai.live import LiveBot
    bot = LiveBot(agent=object())
    assert not bot.playable({"seat.0.stack": 0})
    assert not bot.playable({"seat.0.stack": None})
    assert not bot.playable({"seat.0.stack": 500, "table.found": False})
    assert bot.playable({"seat.0.stack": 500, "table.found": True})


def test_turnier_headsup_allin_man_deckt_gegner():
    from pokercollector.ai.live import TournamentWatch
    w = TournamentWatch(0)
    w.on_hand(_hand(1, 1, {0: (3000, 3000), 4: (3000, 3000)}))
    base = {"seat.0.present": True, "seat.4.present": True, "info.game_hand": [1, 24]}
    w.on_state({**base, "seat.0.stack": 3040, "seat.4.stack": 400}, 10.0)
    w.on_state({**base, "seat.0.stack": 0, "seat.4.stack": 0}, 11.0)       # both all-in, final screen
    assert w.on_state({**base, "seat.0.stack": None, "seat.4.stack": None}, 40.0)["platz"] == 1
    w2 = TournamentWatch(0)
    w2.on_hand(_hand(1, 1, {0: (3000, 3000), 4: (3000, 3000)}))
    w2.on_state({**base, "seat.0.stack": 400, "seat.4.stack": 3040}, 10.0)
    w2.on_state({**base, "seat.0.stack": 0, "seat.4.stack": 0}, 11.0)
    assert w2.on_state({**base, "seat.0.stack": None}, 40.0)["platz"] == 2


def test_dollar_als_fuenf_gelesen():
    from pokercollector.ai.live import fix_dollar_misreads
    st = {"seat.4.stack": 51920, "seat.1.stack": 900, "seat.2.bet": 5400}
    assert fix_dollar_misreads(st, 6000) == {"seat.4.stack": 1920, "seat.1.stack": 900, "seat.2.bet": 5400}
    assert fix_dollar_misreads(st, None) is st


def test_siegerstack_als_einsatz_gelesen_zaehlt_nicht():
    "October 29 evening: on the final screen, the winning stack '$13408' was read as a bet from seat 5 and remained\n    throughout the next tournament -> pot 13438 instead of 30. bet + stack over all chips = no bet."
    from pokercollector.ai.live import fix_dollar_misreads
    st = {"seat.5.bet": 13408, "seat.5.stack": 2000, "seat.0.bet": 20, "seat.0.stack": 1980, "info.total": 10}
    out = fix_dollar_misreads(st, 12000)
    assert out["seat.5.bet"] is None and out["seat.0.bet"] == 20 and st["seat.5.bet"] == 13408
    # plausible large bet (all-in) remains
    ok = {"seat.5.bet": 5000, "seat.5.stack": 0}
    assert fix_dollar_misreads(ok, 12000) is ok


def test_einsatz_ohne_aktion_in_der_hand_wird_ignoriert():
    ' The same glitch one level higher: the reconstructor has no action for seat 5, the bet 13408\n    in the image is a remnant -> remove from pot and bets. Blinds without event (unchanged) remain.'
    from pokercollector.ai.live import drop_stale_bets
    from pokercollector.ai.replay import observation_from_table_state
    st = {"seat.0.cards": ["2d", "5c"], "seat.0.present": True, "seat.0.stack": 980, "seat.0.bet": 20,
          "seat.1.present": True, "seat.1.cards_state": "backs", "seat.1.stack": 990, "seat.1.bet": 10,
          "seat.5.present": True, "seat.5.cards_state": "backs", "seat.5.stack": 1000, "seat.5.bet": 13408,
          "info.total": 0, "info.blinds": [10, 20], "marker.D": 1,
          "hero.buttons": [{"action": "call", "amount": 0}, {"action": "check"}]}
    obs = observation_from_table_state(st, 0, 6)
    assert obs.pot == 13438
    hand = {"actions": [{"seat": 1, "type": "post_sb", "amount_to": 10, "street": "preflop"},
                        {"seat": 0, "type": "post_bb", "amount_to": 20, "street": "preflop"}]}
    out = drop_stale_bets(obs, hand)
    assert out.bets[5] == 0 and out.pot == 30 and out.bets[1] == 10 and out.bets[0] == 20
    assert "Bet without action in this hand ignored" in out.uncertain
    # no actions (hand just started) nothing is changed
    assert drop_stale_bets(obs, {"actions": []}) is obs
    # a real bet with action remains, even if large
    hand2 = {"actions": hand["actions"] + [{"seat": 5, "type": "raise", "amount_to": 13408, "street": "preflop"}]}
    assert drop_stale_bets(obs, hand2) is obs


def test_turnier_sieg_nach_timer_und_neustart_gleiche_spielnummer():
    from pokercollector.ai.live import TournamentWatch
    w = TournamentWatch(0)
    w.on_hand(_hand(1, 30, {0: (5400, 5400), 1: (600, 600)}))
    w.on_hand(_hand(1, 31, {0: (5400, 6000), 1: (600, 0)}))
    assert w.on_state({"seat.0.stack": None}, 100.0) is None          # final screen, clock starts
    assert w.on_state({"seat.0.stack": None}, 110.0) is None
    assert w.on_state({}, 121.0)["platz"] == 1                          # confirmed after BUST_S
    # next game: same game number, hand number jumps back -> fresh tournament
    assert w.on_hand(_hand(1, 1, {0: (1000, 1000), 1: (1000, 1000), 2: (1000, 1000)})) is None
    assert w.hands == 1 and w.field == 3 and not w.reported


def test_turnier_sieg_offen_dann_neustart_ohne_timer():
    from pokercollector.ai.live import TournamentWatch
    w = TournamentWatch(0)
    w.on_hand(_hand(1, 9, {0: (5400, 6000), 1: (600, 0)}))
    res = w.on_hand(_hand(1, 1, {0: (1000, 1000), 1: (1000, 1000)}))   # restart announces open victory
    assert res["platz"] == 1
