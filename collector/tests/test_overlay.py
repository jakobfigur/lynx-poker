import numpy as np

from pokercollector.ai.engine import Hand
from pokercollector.ai.observation import Action
from pokercollector.overlay import advice_from, alternatives


def _obs_preflop():
    h = Hand([2000, 2000, 2000], 0, 10, 20, deck=None, hand_id="t")
    return h.observation(h.to_act)


def test_texte_und_farben():
    obs = _obs_preflop()                     # button acts first, to pay 20
    assert advice_from(Action.fold(), obs).text == "FOLD"
    a = advice_from(Action.call(), obs)
    assert a.kind == "call" and a.text.startswith("CALL 20") and "1.0 BB" in a.text
    a = advice_from(Action.raise_to(60), obs)
    assert a.kind == "raise" and a.text.startswith("RAISE to 60") and "3.0 BB" in a.text
    a = advice_from(Action.raise_to(obs.max_raise_to), obs)
    assert a.kind == "allin" and a.text.startswith("ALL-IN")
    assert advice_from(None, obs).kind == "none"


def test_check_statt_fold():
    h = Hand([2000, 2000], 0, 10, 20, deck=None, hand_id="t2")
    h.apply(h.to_act, Action.call())         # SB limps, BB can check
    obs = h.observation(h.to_act)
    assert obs.can_check
    assert advice_from(Action.fold(), obs).text == "CHECK"


def test_alternativen():
    class Net:
        last_probs = np.array([0.1, 0.6, 0.3, 0, 0, 0])
    assert alternatives(Net()) == [("Call", 0.6), ("½ Pot", 0.3), ("Fold", 0.1)]

    class Such:
        last = {"actions": [("check", None), ("raise", 300)], "probs": np.array([0.25, 0.75])}
    assert alternatives(Such()) == [("300", 0.75), ("Check", 0.25)]


def test_live_uncertainty_is_visible_in_english():
    from pokercollector.ai.replay import observation_from_table_state

    obs = observation_from_table_state(
        {"seat.0.cards": ["As", "Ks"], "info.blinds": [10, 20]},
        num_seats=2,
    )
    advice = advice_from(Action.check(), obs)
    assert "Pot not recognized" in advice.detail
    assert "Call amount estimated" in advice.detail
