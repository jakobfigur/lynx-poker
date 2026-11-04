"""GTO-Wizard integration: translation game state <-> engine without network (the API itself is not called here)."""
import pytest

from pokercollector.ai import gtow
from pokercollector.ai.gtow import (CLIENT, GtowError, client_pos, history_to_text, parse_cards, play_hand,
                                    rebuild, split_players, summarize, to_act_request)
from pokercollector.ai.observation import Action


def test_history_to_text():
    assert history_to_text(["b300", "c", "_", "k", "b500"]) == "b300c/kb500"
    assert history_to_text([]) == ""
    assert history_to_text(["c", "_"]) == "c/"
    with pytest.raises(GtowError):
        history_to_text(["x"])


def test_parse_cards_und_position():
    assert parse_cards("AhKd") == ["Ah", "Kd"]
    assert parse_cards('Ah Kd') == ["Ah", "Kd"]
    assert parse_cards("Qs,Tc,2d") == ["Qs", "Tc", "2d"]
    assert parse_cards('10h 9s') == ["Th", "9s"]
    assert parse_cards(None) == [] and parse_cards("") == []
    assert client_pos("SB") == 1 and client_pos("BTN") == 1 and client_pos("BB") == 0 and client_pos("big_blind") == 0
    with pytest.raises(GtowError):
        client_pos("UTG")


def _resp(history, board="", hole="AsKd", pos="BB", bot_hole=None, over=False, to_act="user", legal=None,
          rr=None, winnings=None, aivat=None):
    return {"hand_id": 7, "game": {"game_name": 'HUNL 200BB', "starting_stack": 20000, "blinds": [50, 100]},
            "game_state": {"street": "preflop", "common_pot": 0, "total_pot": 150, "board_cards": board,
                           "is_hand_over": over, "player_to_act": to_act,
                           "players": [{"name": "lynx", "stack": 19900, "position": pos, "hole_cards": hole},
                                       {"name": 'GTO Wizard', "stack": 19950, "position": "SB" if pos == "BB" else "BB",
                                        "hole_cards": bot_hole}],
                           "legal_actions": legal if legal is not None else ["f", "c", "b"],
                           "raise_range": rr if rr is not None else {"min": 600, "max": 20000},
                           "action_history": history, "has_gto_wizard_folded": False,
                           "winnings": winnings, "aivat_score": aivat}}


def test_split_players_ueber_namen_oder_karten():
    me, bot = split_players(_resp(["b300"])["game_state"]["players"])
    assert me["name"] == "lynx" and bot["name"] == 'GTO Wizard'
    players = [{"name": "p1", "position": "SB", "hole_cards": None}, {"name": "p2", "position": "BB", "hole_cards": "AsKd"}]
    me, bot = split_players(players)
    assert me["name"] == "p2"


def test_rebuild_und_act_request():
    r = _resp(["b300"])                                   #we are BB, opponent raised to 300
    h, me, bot = rebuild(r)
    assert not h.done and h.to_act == CLIENT
    obs = h.observation(CLIENT)
    assert obs.to_call == 200
    gs = r["game_state"]
    assert to_act_request(obs, Action.call(), gs) == {"action": "c"}
    assert to_act_request(obs, Action.fold(), gs) == {"action": "f"}
    assert to_act_request(obs, Action.raise_to(900), gs) == {"action": "b", "amount": 900}
    assert to_act_request(obs, Action.raise_to(400), gs)["amount"] == 600          #below raise_range.min
    gs2 = dict(gs, legal_actions=["f", "c"], raise_range=None)                  #bet not allowed
    assert to_act_request(obs, Action.raise_to(900), gs2) == {"action": "c"}


def test_rebuild_postflop_check():
    r = _resp(["c", "_"], board="Qs8c6h", pos="BB", legal=["k", "b"])              #SB limps, we check; flop
    h, *_ = rebuild(r)
    #preflop: SB calls, BB must still act (check) - the history ends with '_' only after the check
    r = _resp(["c", "k", "_"], board="Qs8c6h", pos="BB", legal=["k", "b"])
    h, *_ = rebuild(r)
    assert h.to_act == CLIENT and h.observation(CLIENT).street == "flop"
    assert to_act_request(h.observation(CLIENT), Action.check(), r["game_state"]) == {"action": "k"}


class _Agent:
    def __init__(self, actions):
        self.actions = list(actions)

    def act(self, obs):
        return self.actions.pop(0)


def test_play_hand_mit_nachgestellter_api(monkeypatch):
    calls = []
    states = [
        _resp(["b300"]),                                                     #new hand: opponent raises, our turn
        _resp(["b300", "b900", "c", "_"], board="Qs8c6h", legal=["k", "b"], to_act="user"),   #we 3-bet, he calls
        _resp(["b300", "b900", "c", "_", "b900", "f"], board="Qs8c6h", over=True, to_act=None,
              winnings=900, aivat=412.5),                                    #we bet, he folds
    ]

    def fake(method, path, data=None, key=None, retries=8):
        calls.append((method, path, data))
        return states.pop(0)
    monkeypatch.setattr(gtow, "_request", fake)
    out = play_hand(_Agent([Action.raise_to(900), Action.raise_to(900)]), "k" * 32, seed=1)
    assert calls[0] == ("POST", "/hands", {"game_name": 'HUNL 200BB'})
    assert calls[1] == ("POST", "/hands/7/act", {"action": "b", "amount": 900})
    assert calls[2] == ("POST", "/hands/7/act", {"action": "b", "amount": 900})
    assert out["winnings"] == 900 and out["aivat"] == 412.5 and out["decisions"] == 2
    assert out["engine_net"] == 900                     #Opponent folds -> engine reaches the same result
    s = summarize([out, dict(out, winnings=-300, aivat=-100.0, engine_net=-300)])
    assert s["hands"] == 2 and s["engine_mismatch"] == 0
    assert s["aivat"]["bb100"] == pytest.approx((412.5 - 100) / 2 * 100 / 100, abs=0.1)
