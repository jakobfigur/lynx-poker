"""Temperature of the net bot (Oct 31): nn?run=...&temp=T sharpens the mixed strategy between sampling (1) and greedy (0)."""
import numpy as np
import pytest

from pokercollector.ai.engine import Hand
from pokercollector.ai.nn_agent import NNAgent, build_net, numpy_weights, sharpen
from pokercollector.ai.observation import clamp_action


def test_sharpen_grenzfaelle():
    p = np.array([0.5, 0.3, 0.2, 0.0])
    assert np.allclose(sharpen(p, 1.0), p)
    assert np.allclose(sharpen(p, 0.0), [1, 0, 0, 0])
    q = sharpen(p, 0.5)
    assert np.isclose(q.sum(), 1.0) and q[3] == 0.0
    assert q[0] > p[0] and q[2] < p[2]                  # sharper: peak up, edge down
    assert np.allclose(q, p ** 2 / (p ** 2).sum())      # 1/T = 2
    assert sharpen(p, 3.0)[0] < p[0]                    # T > 1 flattens out


def test_temp_bot_spielt_legal_und_temp0_wie_greedy():
    import torch
    torch.manual_seed(3)
    w = numpy_weights(build_net(16, "feat-2"))
    warm, greedy = NNAgent(w, seed=1, temp=0.5), NNAgent(w, seed=1, greedy=True)
    cold = NNAgent(w, seed=1, temp=0.0)
    for s in range(10):
        h = Hand([2000, 2000], s % 2, 10, 20, seed=s)
        while not h.done:
            obs = h.observation(h.to_act)
            a = warm.act(obs)
            assert clamp_action(obs, a) == a
            assert cold.act(obs) == greedy.act(obs)
            h.apply(h.to_act, a)


def test_spec_temp_wird_geparst(monkeypatch):
    from pokercollector.ai import nn_agent
    monkeypatch.setattr(nn_agent, "load_weights", lambda run, ck: numpy_weights(build_net(8, "feat-2")))
    assert nn_agent.make_nn_agent("run=x@1&temp=0.5").temp == 0.5
    assert nn_agent.make_nn_agent("run=x@1").temp == 1.0
    with pytest.raises(ValueError):
        nn_agent.make_nn_agent("run=x@1&temperatur=0.5")
