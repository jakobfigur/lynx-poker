import random

import numpy as np

from pokercollector.ai.agents import make_agent
from pokercollector.ai.cfr import (_RADIX, _Worker, decode, infokey, random_hand, regret_matching, train_cfr)
from pokercollector.ai.engine import Hand
from pokercollector.ai.observation import Action
from pokercollector.ai.tournament import BlindSchedule, TournamentConfig, play_tournament


def test_regret_matching():
    m = np.array([False, True, True, False, False, True])
    assert np.allclose(regret_matching(None, m), m / 3)
    p = regret_matching(np.array([5.0, 2.0, -1.0, 9.0, 0.0, 6.0]), m)
    assert np.allclose(p, [0, 0.25, 0, 0, 0, 0.75])        # nur erlaubte, nur positive Bedauern
    assert np.allclose(regret_matching(np.array([0, -1.0, -2, 0, 0, -3]), m), m / 3)


def test_clone_is_independent():
    h = Hand([1000] * 4, 0, 10, 20, seed=3)
    c = h.clone()
    c.apply(c.to_act, Action.raise_to(80))
    assert h.history != c.history and h.bets != c.bets and h.to_act != c.to_act
    h.apply(h.to_act, Action.fold())                           # Original laeuft unabhaengig weiter
    assert not c.folded[h.history[-1].seat]


def test_infokey_roundtrip_and_traversal_zero_sum():
    rng = random.Random(4)
    w = _Worker({}, rng)
    for _ in range(30):
        h = random_hand(rng)
        obs = h.observation(h.to_act)
        k = infokey(obs, {})
        d = decode(k)
        assert d["street"] == 0 and 0 <= d["hand"] < _RADIX[1]
        w.traverse(h, rng.randrange(h.n))
    assert w.d_regret and w.d_strategy
    for v in w.d_regret.values():
        assert np.isfinite(v).all()


def test_train_and_play(tmp_path, monkeypatch):
    monkeypatch.setenv("POKERCOLLECTOR_DATA", str(tmp_path))
    from pokercollector.ai.nn_agent import rl_root
    run = rl_root() / "c1"
    last = train_cfr(run, rounds=5, traversals=20, workers=2)
    assert last["round"] == 5 and last["infosets"] > 50 and (run / "cfr_avg.npz").exists()
    last = train_cfr(run, rounds=6, traversals=20, workers=2)          # fortsetzen
    assert last["round"] == 6
    tiny = TournamentConfig(start_stack=300, blinds=BlindSchedule(10, 20, 4))
    bot = make_agent("cfr?run=c1:gleich", 1)
    play_tournament([bot, make_agent("rock:r", 1), make_agent("station:s", 1)], tiny, seed=2)
    assert bot.hits + bot.misses > 0 and bot.hits > 0
