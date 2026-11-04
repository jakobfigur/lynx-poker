import pytest

from pokercollector.advisor import GameState, advise
from pokercollector.poker import equity_vs_random, evaluate, pot_odds


def ev(s):
    return evaluate(s.split())


def test_categories():
    assert ev('As Ks Qs Js Ts 2d 3c')[0] == 8          # Royal/Straight Flush
    assert ev('9h 9d 9s 9c 2d 3c 4h')[0] == 7
    assert ev('9h 9d 9s 2c 2d 3c 4h')[0] == 6
    assert ev('Ah 9h 7h 4h 2h Kd Qc')[0] == 5
    assert ev('Ah 2d 3c 4s 5h Kd Qc') == (4, 3)        # Wheel
    assert ev('Td Jc Qs Kh Ah 2c 3d') == (4, 12)
    assert ev('9h 9d 9s Ac Kd 3c 4h')[0] == 3
    assert ev('9h 9d 8s 8c Kd 3c 4h')[0] == 2
    assert ev('9h 9d 8s 7c Kd 3c 4h')[0] == 1
    assert ev('Ah Jd 8s 7c 5d 3c 2h')[0] == 0


def test_tiebreaks():
    assert ev('Ah Ad Ks 7c 5d 3c 2h') > ev('Ah Ad Qs 7c 5d 3c 2h')    # Kicker
    assert ev('Kh Kd Ks Qc Qd 2c 2h') == (6, 11, 10)                  # best full house
    assert ev('9h 9d 9s 8c 8d 8h 2c') == (6, 7, 6)                    # two sets
    assert ev('2h 3h 4h 5h 6h 7h 8d')[0:2] == (8, 5)                  # highest straight flush
    assert ev('Ah Ad Kc Kd Qs Qh 2c') == (2, 12, 11, 10)              # three pairs -> best two + kicker


def test_equity_sanity():
    aa = equity_vs_random(["As", "Ah"], [], 1, iterations=4000, seed=1)
    assert 0.82 < aa.equity < 0.88                     # AA vs random ~85 %
    nuts = equity_vs_random(["As", "Ks"], ["Qs", "Js", "Ts"], 3, iterations=500, seed=1)
    assert nuts.equity == pytest.approx(1.0)
    with pytest.raises(ValueError):
        equity_vs_random(["As", "As"], [], 1)


def test_pot_odds_and_advice():
    assert pot_odds(20, 30) == pytest.approx(0.4)
    a = advise(GameState(["6s", "9h"], [], 8, 30, 20, 3000, 20))
    assert a.recommendation == "fold" and a.equity is not None
    b = advise(GameState(["As", "Ah"], [], 1, 30, 10, 3000, 20))
    assert b.recommendation == "raise"
    c = advise(GameState(["As"], [], 1, 30, 10, 3000, 20, issues=['own cards not recognized reliably']))
    assert c.recommendation is None
