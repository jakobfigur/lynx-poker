from pokercollector.ai.agents import make_agent
from pokercollector.ai.engine import play_hand
from pokercollector.ai.humanbots import measure, record_to_phh
from pokercollector.ai.humans import HumanStats

HAND = {  # real HandHQ hand (PokerStars 25NL): all-in with '????' in the middle of the hand, cards only at the end
    "variant": "NT", "antes": [0] * 6, "blinds_or_straddles": [0.1, 0.25, 0, 0, 0, 0],
    "starting_stacks": [16.1, 32.65, 38.95, 21.35, 31.3, 51.65],
    "actions": ['d dh p1 ????', 'd dh p2 ????', 'd dh p3 ????', 'd dh p4 ????', 'd dh p5 ????', 'd dh p6 ????',
                'p3 cbr 1.00', "p4 f", 'p5 cbr 3.00', "p6 f", "p1 f", "p2 f", 'p3 cbr 8.00', 'p5 cbr 31.30',
                'p3 cc', 'p5 sm ????', 'p3 sm ????', 'd db Ts7cTh', 'p3 sm ????', 'p5 sm ????', 'd db 2s',
                'p3 sm ????', 'p5 sm ????', 'd db Qs', 'p3 sm KsKh', 'p5 sm KcKd'],
    "players": ["a", "b", "c", "d", "e", "f"], "winnings": [0, 0, 0, 0, 0, 0],
}


def test_handhq_allin_split_is_zero_sum():
    hs = HumanStats()
    hs.add_hand(HAND)
    net = {p: c["net_bb_x100"] for p, c in hs.c.items()}
    assert abs(sum(net.values())) <= 1                       # without rake: zero sum
    assert net["c"] == net["e"] == round((0.1 + 0.25) / 2 / 0.25 * 100)   # KK versus KK: split
    st = hs.stats()
    assert st["c"]["vpip"] == 1 and st["e"]["threebet"] == 1 and st["c"]["f3b"] == 0


def test_engine_hands_through_phh_are_zero_sum():
    agents = [make_agent(f"{s}:{s}{i}", 1) for i, s in enumerate(["tag", "lag", "station", "rock"])]
    hs = HumanStats()
    for k in range(40):
        rec = play_hand(agents, [2000] * 4, k % 4, 10, 20, seed=k, hand_id=f"h{k}", names=[a.name for a in agents])
        hs.add_hand(record_to_phh(rec))
    assert hs.used == 40
    assert abs(sum(c["net_bb_x100"] for c in hs.c.values())) <= 40      # just rounding


def test_respect_makes_bots_fold_more():
    base = ("tag?vpip=0.18&pfr=0.13&value_margin=0.1&raise_margin=0.25&call_slack=0&bluff=0.1&bet_size=0.66"
            "&open_size=3&push_bb=0&nash_stack_factor=1")
    lo = measure(base + "&respect=0", hands=200, seed=3)
    hi = measure(base + "&respect=1", hands=200, seed=3)
    assert hi["ftb"] > lo["ftb"] + 0.2
