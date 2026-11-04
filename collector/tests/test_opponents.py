import numpy as np

from pokercollector.ai.agents import make_agent
from pokercollector.ai.engine import play_hand
from pokercollector.ai.features import FEATURE_SIZES, action_mask, features
from pokercollector.ai.nn_agent import build_net, forward_np, numpy_weights, widen_net
from pokercollector.ai.opponents import DEFAULT_FEATURES, OpponentTracker


def _hands(agents, n=60):
    recs = []
    stacks = [2000] * len(agents)
    for i in range(n):
        recs.append(play_hand(agents, list(stacks), i % len(agents), 10, 20, seed=100 + i, hand_id=f"h{i}"))
    return recs


def test_tracker_separates_styles():
    agents = [make_agent("rock:me", 1), make_agent("maniac:wild", 1), make_agent("rock:tight", 1)]
    t = OpponentTracker()
    for rec in _hands(agents):
        t.update(rec, 0)
    wild, tight = t.stats("wild"), t.stats("tight")
    assert "me" not in t.c
    assert wild["hands"] == tight["hands"] == 60
    assert wild["vpip"] > tight["vpip"] + 0.2 and wild["pfr"] > tight["pfr"]
    assert 0 < tight["conf"] < 1


def test_features_default_without_history():
    agents = [make_agent("rock:a", 1), make_agent("tag:b", 1)]
    from pokercollector.ai.engine import Hand
    h = Hand([2000, 2000], 0, 10, 20, seed=5, names=["a", "b"])
    obs = h.observation(h.to_act)
    f = OpponentTracker().features(obs)
    assert np.allclose(f, DEFAULT_FEATURES)
    assert len(features(obs, version="feat-3")) == FEATURE_SIZES["feat-3"]
    assert np.allclose(features(obs, version="feat-3")[:49], features(obs, version="feat-2"))


def test_widen_keeps_policy():
    import torch
    torch.manual_seed(0)
    net = build_net(32, "feat-2")
    wide = widen_net(net, "feat-3")
    from pokercollector.ai.engine import Hand
    h = Hand([2000, 2000, 2000], 0, 10, 20, seed=7, names=["a", "b", "c"])
    obs = h.observation(h.to_act)
    m = action_mask(obs)
    p2, v2 = forward_np(numpy_weights(net), features(obs, version="feat-2"), m)
    opp = np.array([0.9, 0.6, 0.8, 0.1, 0.9, 0.7, 0.7, 0.2], np.float32)   # arbitrary opponent values
    p3, v3 = forward_np(numpy_weights(wide), features(obs, version="feat-3", opp=opp), m)
    assert np.allclose(p2, p3, atol=1e-6) and abs(v2 - v3) < 1e-5
