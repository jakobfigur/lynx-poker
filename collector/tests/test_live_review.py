"""Tests zu den Befunden des Code-Reviews vom 29.10.2026 (Live-Pfad)."""
from pokercollector.ai.live import BUST_S, LiveBot, TournamentWatch, fix_dollar_misreads, sane
from pokercollector.ai.observation import Action, Observation
from pokercollector.ai.replay import observation_from_table_state


def _hand(game, no, stacks):
    return {"game_no": game, "hand_no": no,
            "seats": {str(s): {"start_stack": a, "end_stack": b} for s, (a, b) in stacks.items()}}


def _obs(**kw):
    base = dict(seat=0, num_seats=3, hole_cards=["As", "Kd"], board=[], street="preflop", button=0, sb_seat=1,
                bb_seat=2, big_blind=20, small_blind=10, stacks=[1000, 500, 800], bets=[0, 10, 60],
                committed=[0, 10, 60], folded=[False, False, False], allin=[False, False, False],
                in_hand=[True, True, True], history=[], to_call=60, can_check=False, can_raise=True,
                min_raise_to=120, max_raise_to=1000, hand_id="[1, 5]")
    base.update(kw)
    return Observation(**base)


class _Agent:
    def __init__(self, action):
        self.action = action

    def act(self, obs):
        return self.action


def _state(hero_stack=1000, buttons=True, **extra):
    st = {"table.found": True, "info.game_hand": [1, 5], "info.blinds": [10, 20], "info.street": "preflop",
          "board.cards": [None] * 5, "marker.D": 0, "marker.SB": 1, "marker.BB": 2,
          "seat.0.present": True, "seat.0.active": True, "seat.0.stack": hero_stack, "seat.0.bet": 0,
          "seat.0.cards": ["As", "Kd"], "seat.0.cards_state": "faces",
          "seat.1.present": True, "seat.1.stack": 500, "seat.1.bet": 10, "seat.1.cards_state": "backs",
          "seat.2.present": True, "seat.2.stack": 800, "seat.2.bet": 60, "seat.2.cards_state": "backs",
          "hero.buttons": [{"action": "fold", "amount": None, "primary": True},
                           {"action": "call", "amount": 60, "primary": True}] if buttons else []}
    st.update(extra)
    return st


def _ev(field, new, t):
    return {"seq": int(t * 100), "field": field, "new": new, "kind": "change", "t_first": t}


def test_rereraise_ist_neue_entscheidung_auch_bei_call():
    """2.1: 'Call 60' gezeigt, Gegner erhoeht auf 300 -> wieder 'Call', aber mit neuem Betrag -> anzeigen."""
    bot = LiveBot(_Agent(Action("call")))
    st = _state()
    bot.on_event(_ev("hero.buttons", st["hero.buttons"], 1.0), st, 1.0)
    out = bot.poll(2.0)
    assert out is not None and str(out[0]) == "call"
    st2 = dict(st, **{"seat.2.bet": 300, "hero.buttons": [{"action": "call", "amount": 300, "primary": True}]})
    bot.on_event(_ev("seat.2.bet", 300, 3.0), st2, 3.0)
    out = bot.poll(4.0)
    assert out is not None and out[1].to_call == 300
    # gleicher Betrag +-25 %: kein Neuanstoss
    st3 = dict(st2, **{"hero.buttons": [{"action": "call", "amount": 310, "primary": True}]})
    bot.on_event(_ev("hero.buttons", st3["hero.buttons"], 5.0), st3, 5.0)
    assert bot.poll(6.0) is None


def test_unlesbarer_stack_verbraucht_entscheidung_nicht():
    """2.3: Stack kurz unlesbar beim Ablauf der Ruhezeit -> Vorschlag kommt, sobald er wieder lesbar ist."""
    bot = LiveBot(_Agent(Action("call")))
    st = _state(hero_stack=None)
    bot.on_event(_ev("hero.buttons", st["hero.buttons"], 1.0), st, 1.0)
    assert bot.poll(2.0) is None
    assert bot.pending_since is not None
    st2 = dict(st, **{"seat.0.stack": 1000})
    out = bot.on_event(_ev("seat.0.stack", 1000, 2.1), st2, 2.1) or bot.poll(3.0)
    assert out is not None


def test_tisch_weg_keine_entscheidung():
    bot = LiveBot(_Agent(Action("call")))
    st = _state(**{"table.found": False})
    bot.on_event(_ev("table.found", False, 1.0), st, 1.0)
    assert not bot.deciding and bot.poll(5.0) is None


def test_agent_wird_nicht_ohne_karten_gefragt():
    calls = []

    class A:
        def act(self, obs):
            calls.append(obs)
            return Action("fold")
    bot = LiveBot(A())
    st = _state(**{"seat.0.cards": None, "seat.0.cards_state": "folded"})
    bot.on_event(_ev("hero.buttons", st["hero.buttons"], 1.0), st, 1.0)
    assert bot.poll(2.0) is None and calls == []


def test_sieg_wird_verworfen_wenn_gegner_wieder_chips_zeigt():
    """2.2: All-in-Gewinner steht beim Handwechsel noch auf 0, dann wird der Pot gutgeschrieben."""
    w = TournamentWatch(0)
    w.on_hand(_hand(1, 1, {0: (3000, 3000), 1: (3000, 3000)}))
    w.on_hand(_hand(1, 2, {0: (3000, 2500), 1: (3000, 0)}))       # Gegner zeigt 0 (Pot noch nicht gutgeschrieben)
    assert w.pending and w.pending["platz"] == 1
    assert w.on_state({"seat.0.stack": 2500, "seat.1.stack": None, "seat.1.present": True}, 10.0) is None
    assert w.on_state({"seat.0.stack": 2500, "seat.1.stack": 3500, "seat.1.present": True}, 12.0) is None
    assert w.pending is None
    assert w.on_state({"seat.0.stack": 2500, "seat.1.stack": 3500, "seat.1.present": True}, 40.0) is None


def test_alle_chips_regel_nicht_mitten_in_der_hand():
    """2.4: 5850 von 6000 ist kein Sieg, solange der Gegner noch 150 zeigt."""
    w = TournamentWatch(0)
    w.on_hand(_hand(1, 1, {0: (3000, 3000), 1: (3000, 3000)}))
    st = {"seat.0.present": True, "seat.1.present": True, "seat.0.stack": 5850, "seat.1.stack": 150}
    assert w.on_state(st, 5.0) is None
    st = {"seat.0.present": True, "seat.1.present": True, "seat.0.stack": 5850, "seat.1.stack": None}
    assert w.on_state(st, 6.0)["platz"] == 1


def test_ausscheide_uhr_stoppt_bei_spielaktivitaet():
    """2.5: eigener Stack 0 nach All-in, die Hand laeuft aber weiter (Gegner setzen) -> kein Ausscheiden."""
    w = TournamentWatch(0)
    w.on_hand(_hand(1, 1, {0: (1000, 1000), 1: (1000, 1000), 2: (1000, 1000)}))
    base = {"seat.0.present": True, "seat.1.present": True, "seat.2.present": True, "info.game_hand": [1, 2],
            "seat.1.stack": 900, "seat.2.stack": 900}
    assert w.on_state({**base, "seat.0.stack": 0}, 10.0) is None
    w.activity("seat.1.bet", 200)                           # Gegner handelt noch
    assert w.zero_since is None
    assert w.on_state({**base, "seat.0.stack": 0}, 31.0) is None   # Uhr neu gestartet
    assert w.on_state({**base, "seat.0.stack": 0}, 31.0 + BUST_S)["platz"] == 3


def test_handnummer_verleser_setzt_nicht_zurueck():
    """2.6: '12' -> '1' als OCR-Verleser mitten im Turnier (ungleiche Stacks) ist kein neues Spiel."""
    w = TournamentWatch(0)
    w.on_hand(_hand(1, 1, {0: (1000, 1000), 1: (1000, 1000), 2: (1000, 1000)}))
    w.on_hand(_hand(1, 12, {0: (1500, 1600), 1: (700, 600), 2: (800, 800)}))
    w.on_hand(_hand(1, 5, {0: (1600, 1600), 1: (600, 600), 2: (800, 800)}))     # Verleser
    assert w.hands == 3 and w.field == 3
    w.on_hand(_hand(1, 1, {0: (1000, 1000), 1: (1000, 1000)}))                   # echter Neustart
    assert w.hands == 1 and w.field == 2


def test_chips_nur_bei_sicherem_start():
    w = TournamentWatch(0)
    w.on_hand(_hand(1, 7, {0: (1500, 1500), 1: (700, 700)}))      # Einstieg mitten im Spiel, evtl. Plaetze fehlen
    assert w.chips is None
    w2 = TournamentWatch(0)
    w2.on_hand(_hand(1, 1, {0: (1000, 1000), 1: (1000, 1000)}))
    assert w2.chips == 2000


def test_dollar_fix_schneidet_keine_echten_werte():
    assert fix_dollar_misreads({"seat.1.stack": 5000}, 4000) == {"seat.1.stack": 5000}
    assert fix_dollar_misreads({"seat.1.stack": 51000}, 6000) == {"seat.1.stack": 1000}


def test_unlesbarer_gegnerstack_ist_kein_allin():
    """2.7 / 2.9: Stack None -> nicht all-in; Strasse 'showdown' -> aus dem Board."""
    st = _state(**{"seat.2.stack": None, "info.street": "showdown"})
    obs = observation_from_table_state(st, 0, 3)
    assert obs.allin == [False, False, False] and obs.street == "preflop"
    assert "Stack eines Spielers unlesbar" in obs.uncertain
    assert str(sane(Action("raise", 400), obs)) == "raise 400"


def test_session_ended_meldet_offenes_ausscheiden_und_startet_frisch():
    got = []
    bot = LiveBot(_Agent(Action("fold")), on_result=got.append)
    bot.watch.on_hand(_hand(1, 1, {0: (1000, 1000), 1: (1000, 1000)}))
    bot.state = {"seat.0.present": True, "seat.1.present": True, "seat.0.stack": 0, "seat.1.stack": 1500,
                 "info.game_hand": [1, 2]}
    bot.watch.on_state(bot.state, 10.0)
    assert bot.watch.zero_since is not None
    bot.session_ended()
    assert got and got[0]["platz"] == 2
    assert bot.rec.hand is None and bot.done == 0 and not bot.deciding
