import random

import numpy as np

from pokercollector.ai.agents import make_agent
from pokercollector.ai.engine import Hand
from pokercollector.ai.nn_agent import build_net, rl_root, save_checkpoint
from pokercollector.ai.observation import clamp_action
from pokercollector.ai.search import SearchAgent, play_out, world_from_obs
from pokercollector.ai.tournament import BlindSchedule, TournamentConfig, play_tournament


def _snapshots(n_hands=40):
    """Echte Spielstaende aus Haenden mit gemischten Bots: (Original-Hand-Kopie, Beobachtung)."""
    rng = random.Random(7)
    bots = [make_agent(f"{s}:b{i}", i) for i, s in enumerate(["maniac", "lag", "station", "tag", "maniac", "lag"])]
    out = []
    for k in range(n_hands):
        n = rng.choice([2, 3, 6])
        stacks = [rng.choice([0, 300, 1500, 4000]) if i > 1 else rng.choice([300, 4000]) for i in range(n)]
        h = Hand(stacks, rng.randrange(n), 10, 20, seed=k, hand_id=f"h{k}")
        while not h.done:
            s = h.to_act
            obs = h.observation(s)
            if rng.random() < 0.4:
                out.append((h.clone(), obs))
            h.apply(s, clamp_action(obs, bots[s].act(obs)))
    return out


def test_world_matches_real_state():
    snaps = _snapshots()
    assert len(snaps) > 30
    for orig, obs in snaps:
        true_hands = {s: orig.hole[s] for s in range(orig.n)
                      if s != obs.seat and orig.in_hand[s] and not orig.folded[s]}
        w = world_from_obs(obs, true_hands, random.Random(1))
        assert w.to_act == orig.to_act and w.street == orig.street and w.board == orig.board
        assert w.stacks == orig.stacks and w.bets == orig.bets and w.committed == orig.committed
        assert w.legal(obs.seat) == orig.legal(obs.seat) and w.folded == orig.folded
        assert all(w.hole[s] == true_hands[s] for s in true_hands)
        assert w.full_board[:len(orig.board)] == orig.board


def test_play_out_zero_sum():
    rng = random.Random(3)
    bot = make_agent("tag:x", 1)
    for orig, obs in _snapshots(15)[:10]:
        w = world_from_obs(obs, {}, rng)
        start = [r for r in w.start]
        play_out(w, bot, obs.seat)
        assert sum(w.stacks) == sum(start)


def test_search_agent_plays(tmp_path, monkeypatch):
    monkeypatch.setenv("POKERCOLLECTOR_DATA", str(tmp_path))
    save_checkpoint(rl_root() / "bp" / "ckpt_000000.pt", build_net(8), {"phase": "test"})
    agent = make_agent("search?bp=bp@0,worlds=5:s", 1)
    assert isinstance(agent, SearchAgent)
    tiny = TournamentConfig(start_stack=300, blinds=BlindSchedule(10, 20, 4))
    play_tournament([agent, make_agent("station:a", 1), make_agent("maniac:b", 1)], tiny, seed=5)
    assert agent.searches > 0 and agent.last_q is not None and np.isfinite(agent.last_q[agent.last_q > -np.inf]).all()
