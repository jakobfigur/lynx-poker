' end-to-end against the real PokerTH web screenshot (Windows OCR necessary).'

from pathlib import Path

import cv2
import pytest

from pokercollector.profile import Profile

IMG = Path(__file__).parent.parent / "testdata" / "pokerth_preflop_hand1.png"


@pytest.fixture(scope="module")
def snap():
    try:
        from pokercollector.pipeline import make_analyzer
        an = make_analyzer(Profile.load())
    except Exception as e:  # no Windows / no OCR language
        pytest.skip(f"Windows-OCR nicht verfuegbar: {e}")
    return an.analyze(cv2.imread(str(IMG)))


def test_layout(snap):
    lay = snap.layout
    assert lay.found and len(lay.seats) == 10 and lay.action_bar is not None
    assert abs(lay.scale - 1.0) < 0.03
    assert snap.get("marker.D") == 0 and snap.get("marker.SB") == 1 and snap.get("marker.BB") == 2


def test_info_row_and_pot(snap):
    assert snap.get("info.game_hand") == [1, 1]
    assert snap.get("info.street") == "preflop"
    assert snap.get("info.blinds") == [10, 20]
    assert snap.get("info.bets") == 30
    assert snap.get("info.total") == 0
    assert snap.get("pot.total") == 30
    assert snap.get("board.count") == 0


EXPECTED = {
    0: ("jakob", 3000, 0), 1: ("Calling Carl", 2990, 10), 2: ("Lucky Luna", 2980, 20),
    3: ("Re-raise Ro...", 3000, 0), 4: ("Falcon Fay", 3000, 0), 5: ("All-in Annie", 3000, 0),
    6: ("Tilt Master", 3000, 0), 7: ("Sniper Sam", 3000, 0), 8: ("Bluff Bot", 3000, 0),
    9: ("Sharp Shooter", 3000, 0),
}


@pytest.mark.parametrize("seat", range(10))
def test_seats(snap, seat):
    name, stack, bet = EXPECTED[seat]
    assert snap.get(f"seat.{seat}.name") == name
    assert snap.get(f"seat.{seat}.stack") == stack
    assert snap.get(f"seat.{seat}.bet") == bet
    assert snap.get(f"seat.{seat}.folded") == (seat == 3)
    assert snap.get(f"seat.{seat}.active") == (seat == 4)
    if seat not in (0, 3):
        assert snap.get(f"seat.{seat}.cards_state") == "backs"


def test_hero_cards_and_buttons(snap):
    assert snap.get("seat.0.cards") == ["6s", "9h"]
    assert snap.get("hero.to_act") is True
    buttons = {b["action"]: b["amount"] for b in snap.get("hero.buttons")}
    assert buttons == {"fold": None, "call": 20, "raise": 40}


@pytest.mark.parametrize("factor", [0.85, 1.25])
def test_other_window_sizes(factor):
    ' window size changed (simulated by scaling). Below ~0.8 it becomes unreliable.'
    try:
        from pokercollector.pipeline import make_analyzer
        an = make_analyzer(Profile.load())
    except Exception as e:
        pytest.skip(f"Windows-OCR nicht verfuegbar: {e}")
    img = cv2.imread(str(IMG))
    img = cv2.resize(img, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA if factor < 1 else cv2.INTER_CUBIC)
    s = an.analyze(img)
    assert len(s.layout.seats) == 10
    assert (s.get("marker.D"), s.get("marker.SB"), s.get("marker.BB")) == (0, 1, 2)
    assert s.get("seat.0.cards") == ["6s", "9h"]
    assert [s.get(f"seat.{n}.stack") for n in range(10)] == [3000, 2990, 2980] + [3000] * 7
    assert (s.get("seat.1.bet"), s.get("seat.2.bet"), s.get("pot.total")) == (10, 20, 30)