import random

import pytest

from pokercollector.ai.agents import make_agent
from pokercollector.ai.engine import Hand, IllegalAction, play_hand
from pokercollector.ai.observation import Action, clamp_action
from pokercollector.poker import FULL_DECK


def deck_with(holes: dict[int, list[str]], board: list[str]) -> list[str]:
    """Build deck so that seat i gets the cards holes[i] and the board `board`."""
    used = set(board) | {c for h in holes.values() for c in h}
    rest = [c for c in FULL_DECK if c not in used]
    deck = []
    for i in range(10):
        deck += holes.get(i) or [rest.pop(), rest.pop()]
    deck += board
    deck += rest
    return deck


def test_blinds_and_preflop_order():
    h = Hand([1000] * 4, button=0, small_blind=5, big_blind=10, seed=1)
    assert (h.sb_seat, h.bb_seat) == (1, 2)
    assert h.bets == [0, 5, 10, 0]
    assert h.to_act == 3                         #UTG
    o = h.observation(3)
    assert (o.to_call, o.min_raise_to, o.max_raise_to) == (10, 20, 1000)


def test_heads_up_order():
    h = Hand([1000, 1000], button=0, small_blind=5, big_blind=10, seed=1)
    assert (h.sb_seat, h.bb_seat, h.to_act) == (0, 1, 0)     #Button = SB, acts first preflop
    h.apply(0, Action.call())
    assert h.to_act == 1                                     #BB has option
    assert h.observation(1).can_raise
    h.apply(1, Action.check())
    assert h.street == "flop" and h.to_act == 1              #postflop BB acts first


def test_big_blind_option_and_min_raise():
    h = Hand([1000] * 3, button=0, small_blind=5, big_blind=10, seed=1)
    h.apply(0, Action.raise_to(30))              #Raise by 20
    with pytest.raises(IllegalAction):
        h.apply(1, Action.raise_to(40))          #Minimum reraise is 50
    h.apply(1, Action.raise_to(50))
    assert h.observation(2).min_raise_to == 70
    h.apply(2, Action.call())
    h.apply(0, Action.call())
    assert h.street == "flop" and h.committed == [50, 50, 50]


def test_everyone_folds_bb_wins_uncontested():
    h = Hand([1000] * 3, button=0, small_blind=5, big_blind=10, seed=1)
    h.apply(0, Action.fold())
    h.apply(1, Action.fold())
    assert h.done and h.stacks == [1000, 995, 1005]
    assert not h.record.went_to_showdown


def test_uncalled_bet_is_returned():
    h = Hand([1000] * 2, button=0, small_blind=5, big_blind=10, seed=1)
    h.apply(0, Action.raise_to(1000))           #All-in
    h.apply(1, Action.fold())
    assert h.stacks == [1010, 990]


def test_short_allin_does_not_reopen_betting():
    #A opens to 100, B goes all-in with 150 (only +50, less than full raise of 90)
    h = Hand([1000, 150, 1000, 1000], button=3, small_blind=5, big_blind=10, seed=1)
    #Button 3 -> SB 0, BB 1? We want simple order: seat 2 is UTG
    assert (h.sb_seat, h.bb_seat, h.to_act) == (0, 1, 2)
    h.apply(2, Action.raise_to(100))
    h.apply(3, Action.call())
    h.apply(0, Action.call())
    h.apply(1, Action.raise_to(150))            #BB all-in, incomplete raise
    o = h.observation(2)
    assert o.to_call == 50 and not o.can_raise  #already acted, not reopened
    h.apply(2, Action.call())
    assert not h.observation(3).can_raise
    h.apply(3, Action.call())
    h.apply(0, Action.call())
    assert h.street == "flop"


def test_full_raise_reopens_betting():
    h = Hand([1000] * 3, button=0, small_blind=5, big_blind=10, seed=1)
    h.apply(0, Action.raise_to(30))
    h.apply(1, Action.call())
    h.apply(2, Action.raise_to(100))            #full raise
    assert h.observation(0).can_raise


def test_side_pots_three_way_allin():
    #Seat 0 short (100), seat 1 medium (300), seat 2 big (1000).
    #Seat 0 has the best hand, seat 1 the second best.
    deck = deck_with({0: ["As", "Ah"], 1: ["Ks", "Kh"], 2: ["7c", "2d"]}, ["Ad", "Kd", "9c", "5s", "3h"])
    h = Hand([100, 300, 1000], button=2, small_blind=5, big_blind=10, deck=deck)
    #Button 2 -> SB 0, BB 1, Button acts first
    h.apply(2, Action.raise_to(1000))
    h.apply(0, Action.call())
    h.apply(1, Action.call())
    assert h.done and h.record.went_to_showdown
    #Main pot 300 (3x100) -> seat 0; side pot 400 (2x200) -> seat 1; remainder 700 returned to seat 2
    assert h.stacks == [300, 400, 700]
    amounts = [(p["amount"], p["winners"]) for p in h.record.pots]
    assert amounts == [(300, [0]), (400, [1]), (700, [2])]


def test_split_pot_odd_chip_goes_left_of_button():
    #Both play the board (royal flush on the board)
    deck = deck_with({0: ["2c", "3d"], 1: ["2d", "3c"], 2: ["4c", "4d"]}, ["As", "Ks", "Qs", "Js", "Ts"])
    h = Hand([1000, 1000, 1000], button=2, small_blind=5, big_blind=10, deck=deck)
    h.apply(2, Action.fold())                   #Pot: SB 5 + BB 10
    h.apply(0, Action.call())
    h.apply(1, Action.check())
    for _ in range(3):
        h.apply(0, Action.check())
        h.apply(1, Action.check())
    #Pot 20, split 10/10
    assert h.stacks == [1000, 1000, 1000]
    deck = deck_with({0: ["2c", "3d"], 1: ["2d", "3c"], 2: ["4c", "4d"]}, ["As", "Ks", "Qs", "Js", "Ts"])
    h = Hand([1000, 1000, 1000], button=2, small_blind=5, big_blind=10, deck=deck)
    h.apply(2, Action.fold())
    h.apply(0, Action.fold())                   #Pot 15 only for BB, no split
    assert h.stacks == [995, 1005, 1000]


def test_odd_chip_goes_to_first_winner_left_of_button():
    #Pot 25 (SB 5 total + 2x10), split between seat 0 (Button) and seat 2 -> 12/13.
    #First winner to the left of the button is seat 2 -> gets the odd chip.
    deck = deck_with({0: ["2c", "3d"], 1: ["2d", "3c"], 2: ["2h", "3h"]}, ["As", "Ks", "Qs", "Js", "Ts"])
    h = Hand([1000, 1000, 1000], button=0, small_blind=5, big_blind=10, deck=deck)
    h.apply(0, Action.call())
    h.apply(1, Action.fold())
    h.apply(2, Action.check())
    for _ in range(3):
        h.apply(2, Action.check())
        h.apply(0, Action.check())
    assert h.stacks == [1002, 995, 1003]


def test_blind_allin_short_stack():
    h = Hand([1000, 3, 1000], button=0, small_blind=5, big_blind=10, seed=1)
    assert h.bets[1] == 3 and h.allin[1]        #SB posts only 3
    assert h.current_bet == 10


def test_illegal_actions_rejected():
    h = Hand([1000] * 3, button=0, small_blind=5, big_blind=10, seed=1)
    with pytest.raises(IllegalAction):
        h.apply(1, Action.call())               #not to act
    with pytest.raises(IllegalAction):
        h.apply(0, Action.check())              #open bet
    with pytest.raises(IllegalAction):
        h.apply(0, Action.raise_to(5000))       #over stack


def test_clamp_action():
    h = Hand([1000] * 3, button=0, small_blind=5, big_blind=10, seed=1)
    o = h.observation(0)
    assert clamp_action(o, Action.raise_to(99999)) == Action.raise_to(1000)
    assert clamp_action(o, Action.raise_to(1)) == Action.raise_to(20)
    assert clamp_action(o, Action.check()) == Action.call()


def test_observation_hides_other_cards():
    h = Hand([1000] * 3, button=0, small_blind=5, big_blind=10, seed=1)
    o = h.observation(0)
    assert o.hole_cards == h.hole[0] and o.board == []
    assert not any(c in str(o.__dict__) for c in h.hole[1] + h.hole[2])


@pytest.mark.parametrize("n", [2, 3, 6, 10])
def test_fuzz_chip_conservation_and_termination(n):
    rng = random.Random(n)
    agents = [make_agent(rng.choice(["random", "maniac", "station", "caller"]) + f":a{i}", i) for i in range(n)]
    for k in range(150):
        stacks = [rng.choice([0, 7, 50, 400, 2000]) for _ in range(n)]
        if sum(1 for s in stacks if s > 0) < 2:
            stacks[0] = stacks[1] = 500
        rec = play_hand(agents, stacks, k % n, 5, 10, seed=k, hand_id=str(k), on_illegal="clamp")
        assert sum(r.end_stack for r in rec.results) == sum(stacks)
        assert all(r.end_stack >= 0 for r in rec.results)
        assert sum(p["amount"] for p in rec.pots) == sum(r.won for r in rec.results)
        assert rec.board == [] or len(rec.board) in (3, 4, 5)


def test_short_allin_big_blind_needs_no_action_from_bigger_small_blind():
    #Regression: SB posts 640, BB has only 340 (all-in). SB has nothing more to do,
    #Showdown for 680, 300 go back to SB.
    h = Hand([1500, 340], button=0, small_blind=640, big_blind=1280, seed=3)
    assert h.done and h.record.went_to_showdown
    assert sum(h.stacks) == 1840
    assert h.stacks[0] >= 1500 - 340                        #SB risks at most 340


def test_multiway_short_allin_side_pot_returns_overbet_to_bettor():
    #Seat 0 raises to 500, seat 1 calls all-in 100, BB folds: main pot 210, surplus 400 returned to seat 0
    h = Hand([1000, 100, 1000], button=0, small_blind=5, big_blind=10, seed=1)
    h.apply(0, Action.raise_to(500))
    h.apply(1, Action.call())
    h.apply(2, Action.fold())
    assert h.done and sum(h.stacks) == 2100
    assert h.stacks[0] in (900, 1110) and h.stacks[1] in (0, 210)
    assert h.stacks[2] == 990