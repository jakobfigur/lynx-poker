import numpy as np

from pokercollector.ai.engine import Hand
from pokercollector.ai.features import MIN_RAISE, action_mask, features, from_action, to_action
from pokercollector.ai.nn_agent import NNAgent, build_net, forward_np, numpy_weights, widen_net
from pokercollector.ai.observation import Action, clamp_action


def _obs():
    h = Hand([2000, 2000, 2000], 0, 10, 20, seed=3, names=["a", "b", "c"])
    return h.observation(h.to_act)


def test_mask_and_actions_8():
    obs = _obs()
    m6, m8 = action_mask(obs), action_mask(obs, 8)
    assert len(m6) == 6 and len(m8) == 8 and (m8[:6] == m6).all()
    assert m8[MIN_RAISE] and not m8[6]                   # 1/3 pot preflop would be = min-raise
    assert to_action(obs, MIN_RAISE) == Action.raise_to(obs.min_raise_to)
    third = to_action(obs, 6).amount
    half = to_action(obs, 2).amount
    assert obs.min_raise_to <= third <= half
    assert from_action(obs, Action.raise_to(obs.min_raise_to), 8) == MIN_RAISE
    assert from_action(obs, Action.raise_to(obs.min_raise_to), 6) in (2, 3, 4, 5)


def test_widen_actions_keeps_old_ratios():
    import torch
    torch.manual_seed(1)
    net = build_net(32, "feat-2")
    wide = widen_net(net, "feat-3", 8)
    assert wide.pi.out_features == 8
    obs = _obs()
    p6, _ = forward_np(numpy_weights(net), features(obs, version="feat-2"), action_mask(obs))
    p8, _ = forward_np(numpy_weights(wide), features(obs, version="feat-3"), action_mask(obs, 8))
    assert p8[6:].sum() < 0.35                              # new actions initially rare
    assert np.allclose(p8[:6] / p8[:6].sum(), p6, atol=1e-5)  # old ratios remain


def test_nn_agent_with_8_actions_plays_legal():
    import torch
    torch.manual_seed(2)
    agent = NNAgent(numpy_weights(widen_net(build_net(16, "feat-2"), "feat-3", 8)), seed=1)
    for s in range(20):
        h = Hand([2000, 2000, 2000], s % 3, 10, 20, seed=s)
        while not h.done:
            obs = h.observation(h.to_act)
            a = agent.act(obs)
            assert clamp_action(obs, a) == a
            h.apply(h.to_act, a)
