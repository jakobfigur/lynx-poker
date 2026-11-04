import json

import numpy as np
import pytest

from pokercollector.ai.agents import make_agent
from pokercollector.ai.features import (N_ACTIONS, N_FEATURES, action_mask, eff_stack_bb, features, from_action,
                                        to_action)
from pokercollector.ai.observation import clamp_action
from pokercollector.ai.tournament import BlindSchedule, TournamentConfig, play_tournament

torch = pytest.importorskip("torch")

TINY = TournamentConfig(start_stack=300, blinds=BlindSchedule(10, 20, 4))


class Probe:
    """Spielt wie ein Stil-Bot und prueft nebenbei Merkmale und Aktionsabbildung."""

    def __init__(self, inner):
        self.inner, self.name, self.n = inner, inner.name, 0

    def act(self, obs):
        x = features(obs)
        assert x.shape == (N_FEATURES,) and np.isfinite(x).all()
        others = [obs.stacks[s] + obs.bets[s] for s in range(obs.num_seats)
                  if s != obs.seat and obs.in_hand[s] and not obs.folded[s]]
        eff = min(obs.my_stack + obs.my_bet, max(others)) / obs.big_blind
        assert abs(eff_stack_bb(x) - eff) < 1e-3 * max(1, eff)
        m = action_mask(obs)
        assert m[1] and m.dtype == bool
        for i in range(N_ACTIONS):
            if m[i]:
                a = to_action(obs, i)
                assert clamp_action(obs, a) == a              # jede erlaubte Aktion ist regelkonform
                assert to_action(obs, from_action(obs, a)) == a   # Rueckabbildung trifft dieselbe Aktion
        self.n += 1
        return self.inner.act(obs)


def test_features_and_actions_on_real_situations():
    probes = [Probe(make_agent(f"{s}:p{i}", i)) for i, s in enumerate(["maniac", "lag", "tag", "station"])]
    for sd in range(6):
        play_tournament(probes, TINY, seed=sd)
    assert sum(p.n for p in probes) > 200


def test_gae_per_hand():
    from pokercollector.ai.rl import gae
    r = np.array([0, 2.0, -1.0], np.float32)
    v = np.array([0.5, 1.0, 0.0], np.float32)
    done = np.array([False, True, True])
    adv, ret = gae(r, v, done, lam=1.0)
    assert np.allclose(ret, [2.0, 2.0, -1.0])       # gamma=lambda=1: Ziel = Handergebnis
    assert np.allclose(adv, [1.5, 1.0, -1.0])


def test_bc_ppo_resume_and_league_spec(tmp_path, monkeypatch):
    monkeypatch.setenv("POKERCOLLECTOR_DATA", str(tmp_path))
    from pokercollector.ai.nn_agent import rl_root
    from pokercollector.ai.rl import RLConfig, behavior_clone, train_ppo
    run = rl_root() / "t1"
    meta = behavior_clone(run, teacher="rock", tournaments=8, epochs=2, hidden=16, config=TINY, workers=2)
    assert meta["decisions"] > 50 and (run / "ckpt_000000.pt").exists()
    cfg = RLConfig(hidden=16, tournaments=4, minibatch=64, snapshot_every=2, eval_every=2, eval_schemes=2)
    res = train_ppo(run, 2, ["station", "random"], cfg, config=TINY, workers=2)
    assert res["snapshots"] == [0, 2] and (run / "ckpt_000002.pt").exists()
    log = [json.loads(line) for line in (run / "log.jsonl").read_text("utf-8").splitlines()]
    assert [e["iteration"] for e in log] == [1, 2] and log[0]["decisions"] > 0
    assert (run / "eval.jsonl").exists()
    res = train_ppo(run, 3, ["station", "random"], cfg, config=TINY, workers=2)      # fortsetzen
    assert [json.loads(line)["iteration"] for line in (run / "log.jsonl").read_text("utf-8").splitlines()] == [1, 2, 3]
    bot = make_agent("nn?run=t1@3:netz", 1)
    assert bot.name == "netz"
    r1 = play_tournament([bot, make_agent("rock:r", 1), make_agent("station:s", 1)], TINY, seed=3)
    bot2 = make_agent("nn?run=t1:netz", 1)
    r2 = play_tournament([bot2, make_agent("rock:r", 1), make_agent("station:s", 1)], TINY, seed=3)
    assert r1.payouts == r2.payouts                   # reproduzierbar (Duplicate-fair)


PLURIBUS_HAND_11 = """
variant = 'NT'
ante_trimming_status = true
antes = [0, 0, 0, 0, 0, 0]
blinds_or_straddles = [50, 100, 0, 0, 0, 0]
min_bet = 100
starting_stacks = [10000, 10000, 10000, 10000, 10000, 10000]
actions = ['d dh p1 4hAc', 'd dh p2 Ah6s', 'd dh p3 4cKh', 'd dh p4 2s4s', 'd dh p5 2c9c', 'd dh p6 4dKc', 'p3 f', 'p4 f', 'p5 f', 'p6 f', 'p1 cc', 'p2 cc', 'd db 5d6h2h', 'p1 cc', 'p2 cbr 130', 'p1 cc', 'd db 3h', 'p1 cc', 'p2 cbr 300', 'p1 cc', 'd db Js', 'p1 cc', 'p2 cc', 'p1 sm 4hAc', 'p2 sm']
hand = 11
players = ['Pluribus', 'MrBlue', 'MrBlonde', 'MrWhite', 'MrPink', 'MrBrown']
finishing_stacks = [10530, 9470, 10000, 10000, 10000, 10000]
"""


def test_phh_replay_matches_engine():
    import tomllib
    from pokercollector.ai.phh import replay
    hand = tomllib.loads(PLURIBUS_HAND_11)
    res = replay(hand)
    assert res.ok, res.problem
    assert len(res.samples) == 14 and res.samples[0][0] == "MrBlonde"
    assert [s[4] for s in res.samples if s[0] == "Pluribus"][0] == 5.3     # +530 Chips = +5,3 BB
    bad = dict(hand, finishing_stacks=[10000] * 6)
    assert not replay(bad).ok                         # falsche Endstacks werden erkannt
    swapped = dict(hand, actions=[a.replace("p3 f", "p4 f", 1) if a == "p3 f" else a for a in hand["actions"]])
    assert "Reihenfolge" in replay(swapped).problem


def test_ppo_with_anchor(tmp_path, monkeypatch):
    monkeypatch.setenv("POKERCOLLECTOR_DATA", str(tmp_path))
    from pokercollector.ai.nn_agent import rl_root
    from pokercollector.ai.rl import RLConfig, train_ppo
    run = rl_root() / "a1"
    cfg = RLConfig(hidden=16, tournaments=3, minibatch=64, snapshot_every=5, eval_every=5, eval_schemes=1,
                   anchor_coef=0.5)
    train_ppo(run, 1, ["station", "random"], cfg, config=TINY, workers=2)
    e = json.loads((run / "log.jsonl").read_text("utf-8").splitlines()[0])
    assert "kl_anchor" in e and e["kl_anchor"] >= -1e-6


def test_exploit_test_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("POKERCOLLECTOR_DATA", str(tmp_path))
    from pokercollector.ai.nn_agent import build_net, rl_root, save_checkpoint
    from pokercollector.ai.rl import exploit_test
    init = rl_root() / "init" / "ckpt_000000.pt"
    save_checkpoint(init, build_net(16), {"phase": "test"})
    r = exploit_test("random", init, iterations=2, schemes=4, config=TINY, workers=2, run_dir=rl_root() / "ex")
    assert r["schemes"] == 4 and len(r["ci95"]) == 2 and (rl_root() / "ex" / "exploit.json").exists()


def test_random_style_bots_and_pool():
    import random as _r
    from pokercollector.ai.optimize import LeaguePool, random_style_spec
    a, b = random_style_spec(_r.Random(3)), random_style_spec(_r.Random(3))
    assert a == b and a.startswith("tag?") and make_agent(a + ":z", 1).style.vpip > 0
    lp = LeaguePool([("a", "rock", 1.0), ("b", "tag", 0.0), ("c", "lag", 0.0)], table=3, self_play=0,
                    random_share=1.0)
    t = lp.sample(_r.Random(1))
    assert all(s.startswith("tag?vpip=") for s in t) and len(set(t)) == 3
    lp.add("x", "station")
    assert "x" in lp.shares()


def test_ppo_with_random_bots_and_exploiter(tmp_path, monkeypatch):
    monkeypatch.setenv("POKERCOLLECTOR_DATA", str(tmp_path))
    from pokercollector.ai.nn_agent import build_net, rl_root, save_checkpoint
    from pokercollector.ai.optimize import LeaguePool
    from pokercollector.ai.rl import RLConfig, train_ppo
    run = rl_root() / "rx"
    save_checkpoint(run / "ckpt_000000.pt", build_net(16), {"phase": "test"})
    pool = LeaguePool([("s", "station", 0.0), ("r", "random", 0.0), ("k", "rock", 0.0)], table=2)
    cfg = RLConfig(hidden=16, tournaments=3, minibatch=64, snapshot_every=5, eval_every=5, eval_schemes=1,
                   bench_every=0, random_share=0.5, exploit_every=2, exploit_iters=1, exploit_tournaments=2)
    train_ppo(run, 2, pool, cfg, config=TINY, workers=2)
    ex = json.loads((run / "exploiters.json").read_text("utf-8"))
    assert len(ex) == 1 and ex[0]["spec"].startswith("nn?run=rx/expl-000002@")
    assert make_agent(ex[0]["spec"] + ":e", 1).name == "e"          # Ausbeuter ist spielbar
    assert any(n == "expl-2" for n, _, _ in pool.players)
    train_ppo(run, 3, LeaguePool([("s", "station", 0.0), ("r", "random", 0.0)], table=2), cfg, config=TINY,
              workers=2)                                             # fortsetzen: Ausbeuter wieder im Pool


def test_random_formats_in_training(tmp_path, monkeypatch):
    import random as _r
    from pokercollector.ai.tournament import random_config, random_players
    rng = _r.Random(5)
    ns = [random_players(rng) for _ in range(400)]
    assert min(ns) == 2 and max(ns) == 10
    cfgs = [random_config(rng, n) for n in ns]
    assert len({c.start_stack for c in cfgs}) > 20 and len({c.blinds.hands_per_level for c in cfgs}) > 4
    assert all(len(c.payouts) < n or c.payouts == (1.0,) for c, n in zip(cfgs, ns))
    monkeypatch.setenv("POKERCOLLECTOR_DATA", str(tmp_path))
    from pokercollector.ai.nn_agent import build_net, rl_root, save_checkpoint
    from pokercollector.ai.optimize import LeaguePool
    from pokercollector.ai.rl import RLConfig, train_ppo
    run = rl_root() / "fmt"
    save_checkpoint(run / "ckpt_000000.pt", build_net(16), {"phase": "test"})
    pool = LeaguePool([("s", "station", 0.0), ("r", "random", 0.0), ("k", "rock", 0.0)], table=2)
    cfg = RLConfig(hidden=16, tournaments=4, minibatch=64, snapshot_every=5, eval_every=5, eval_schemes=1,
                   bench_every=0, random_formats=True)
    train_ppo(run, 1, pool, cfg, config=TINY, workers=2)
    assert json.loads((run / "log.jsonl").read_text("utf-8").splitlines()[0])["decisions"] > 0
