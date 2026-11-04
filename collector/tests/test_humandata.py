import numpy as np

from pokercollector.ai.humandata import CLASS_ID, FEATURES, N_ACTIONS, replay_handhq
from pokercollector.ai.features import FEATURE_SIZES


def _hand(shown=("p3",), hu=False):
    """25NL-Hand wie in HandHQ: p1 SB 0.10, p2 BB 0.25, p3 Button (3-max) bzw. heads-up p1 SB/Button."""
    if hu:
        return {"variant": "NT", "antes": [0, 0], "blinds_or_straddles": [0.10, 0.25], "min_bet": 0.25,
                "starting_stacks": [25.0, 30.0], "players": ["A", "B"],
                "actions": ["d dh p1 ????", "d dh p2 ????", "p1 cbr 0.75", "p2 cc", "d db AhKd7c", "p2 cc",
                            "p1 cbr 1.00", "p2 cc", "d db 2s", "p2 cc", "p1 cc", "d db 9h", "p2 cc", "p1 cc",
                            "p1 sm QsQd", "p2 sm AsTc"]}
    acts = ["d dh p1 ????", "d dh p2 ????", "d dh p3 ????", "p3 cbr 0.75", "p1 f", "p2 cc", "d db AhKd7c",
            "p2 cc", "p3 cbr 1.00", "p2 cc", "d db 2s", "p2 cc", "p3 cc", "d db 9h", "p2 cbr 2.50", "p3 cc"]
    cards = {"p2": "AsTc", "p3": "QsQd"}
    for p in shown:
        acts.append(f"{p} sm {cards[p]}")
    return {"variant": "NT", "antes": [0, 0, 0], "blinds_or_straddles": [0.10, 0.25, 0], "min_bet": 0.25,
            "starting_stacks": [25.0, 30.0, 40.0], "players": ["A", "B", "C"], "actions": acts}


def test_nur_gezeigte_spieler_liefern_zeilen():
    ok, problem, rows = replay_handhq(_hand(shown=("p3",)), 1)
    assert ok, problem
    # p3 handelt: preflop raise, flop bet, turn check, river call = 4 Entscheidungen
    assert len(rows) == 4
    x, mask, a, meta = rows[0]
    assert x.shape == (FEATURE_SIZES[FEATURES],) and mask.shape == (N_ACTIONS,) and mask[a]
    assert meta["street"] == 0 and meta["kind"] == 3 and meta["hole_class"] == CLASS_ID["QQ"] and meta["player"] == "C"
    assert meta["position"] == 0                                 # Button
    assert abs(meta["amount_bb"] - 3.0) < 1e-6                   # 0.75 $ = 3 BB
    kinds = [m["kind"] for _, _, _, m in rows]
    assert kinds == [3, 3, 1, 2]                                 # raise, raise(bet), check, call
    assert rows[3][3]["street"] == 3 and abs(rows[3][3]["to_call_bb"] - 10.0) < 1e-6


def test_beide_gezeigt_und_heads_up():
    ok, problem, rows = replay_handhq(_hand(shown=("p2", "p3")), 2)
    assert ok, problem
    assert len(rows) == 4 + 5                                    # p2: call, check, call, check, bet
    assert {m["player"] for _, _, _, m in rows} == {"B", "C"}
    ok, problem, rows = replay_handhq(_hand(hu=True), 3)
    assert ok, problem                                           # heads-up: p1 ist SB und Button
    assert all(m["n_players"] == 2 for _, _, _, m in rows) and len(rows) == 9   # p1 4 + p2 5 Entscheidungen


def test_ohne_karten_oder_kaputt_wird_uebersprungen():
    ok, problem, rows = replay_handhq(_hand(shown=()), 4)
    assert not ok and problem == "keine Karten" and rows == []
    h = _hand(); h["actions"].insert(3, "p1 cc")                 # falsche Reihenfolge
    ok, problem, _ = replay_handhq(h, 5)
    assert not ok and problem == "Reihenfolge"
    h = _hand(); h["blinds_or_straddles"] = [0.10, 0.25, 0.50]   # Straddle
    assert replay_handhq(h, 6)[1] == "Antes/Straddles"


def test_oeffentliche_zeilen_enthalten_folds():
    from pokercollector.ai.humandata import public_rows
    ok, problem, rows = public_rows(_hand(shown=("p3",)), 9)
    assert ok, problem
    kinds = [r["kind"] for r in rows]
    assert kinds[0] == 3 and kinds[1] == 0                       # p3 raist, p1 foldet (ohne Karten!)
    assert rows[1]["hole_class"] == -1 and rows[0]["hole_class"] >= 0
    assert rows[1]["facing"] == 1 and rows[1]["raises_pre"] == 1 and rows[1]["street"] == 0
    assert len(rows) == 10                                       # alle Entscheidungen aller Spieler
    assert rows[-1]["board_high"] >= 0 and rows[-1]["street"] == 3
