import numpy as np

from pokercollector.ai.agents import make_agent
from pokercollector.ai.deepcfr import DeepCFRConfig, Reservoir, strategy_from_adv, train_deepcfr
from pokercollector.ai.features import N_ACTIONS, N_FEATURES
from pokercollector.ai.tournament import BlindSchedule, TournamentConfig, play_tournament


def test_strategy_from_adv():
    m = np.array([True, True, False, False, False, True])
    assert np.allclose(strategy_from_adv(np.array([1.0, 3.0, 9.0, 0, 0, -1.0]), m), [0.25, 0.75, 0, 0, 0, 0])
    s = strategy_from_adv(np.array([-3.0, -1.0, 5.0, 0, 0, -2.0]), m)     #everything <= 0: best allowed
    assert s[1] == 1.0 and s.sum() == 1.0


def test_reservoir_uniform_and_bounded():
    r = Reservoir(1000, np.random.default_rng(1))
    for t in range(1, 11):                                   #10 packets of 1000, capacity 1000
        x = np.full((1000, N_FEATURES), t, np.float32)
        r.add(x, np.ones((1000, N_ACTIONS), bool), np.zeros((1000, N_ACTIONS), np.float32), t)
    assert r.n == 1000 and r.seen == 10_000
    counts = np.bincount(r.t.astype(int), minlength=11)[1:]
    assert counts.min() > 50 and counts.max() < 160            #each iteration roughly equally represented (~100)
    assert (r.x[:, 0] == r.t).all()                            #rows remain together


def test_train_resume_and_play(tmp_path, monkeypatch):
    monkeypatch.setenv("POKERCOLLECTOR_DATA", str(tmp_path))
    from pokercollector.ai.nn_agent import rl_root
    run = rl_root() / "d1"
    cfg = DeepCFRConfig(hidden=16, traversals=10, adv_capacity=5000, strat_capacity=5000, adv_steps=20,
                        strat_steps=20, batch=256, snapshot_every=2)
    seen = []
    last = train_deepcfr(run, 2, cfg, workers=2, on_snapshot=lambda t, e, ex: seen.append(t))
    assert seen == [2] and last["adv_samples"] > 0 and (run / "ckpt_000002.pt").exists()
    last = train_deepcfr(run, 3, cfg, workers=2)              #continue from adv.pt + buffers.npz
    assert last["iteration"] == 3 and last["adv_seen"] > 0
    tiny = TournamentConfig(start_stack=300, blinds=BlindSchedule(10, 20, 4))
    bot = make_agent("nn?run=d1@3:dcfr", 1)
    play_tournament([bot, make_agent("rock:r", 1), make_agent("station:s", 1)], tiny, seed=2)
