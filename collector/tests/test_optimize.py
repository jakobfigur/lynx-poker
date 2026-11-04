from pokercollector.ai.agents import make_agent
from pokercollector.ai.optimize import (SPACE, _denorm, _norm, gate, params_from_style, run_cem, scheme_payouts,
                                        spec_from_params)
from pokercollector.ai.tournament import BlindSchedule, TournamentConfig

TINY = TournamentConfig(start_stack=300, blinds=BlindSchedule(10, 20, 4))


def test_param_roundtrip_and_spec():
    p = params_from_style("tag")
    assert _denorm(_norm(p)) == {k: (int(round(v)) if SPACE[k][2] else round(v, 3)) for k, v in p.items()}
    spec = spec_from_params(p)
    a = make_agent(spec + ":x")
    assert a.style.vpip == p["vpip"] and a.style.push_bb == p["push_bb"]
    clipped = spec_from_params({**p, "bluff": 5.0})
    assert "bluff=0.5" in clipped


def test_scheme_payouts_zero_sum_against_itself():
    # Kandidat = tag gegen Pool aus tag-Kopien: alle identisch -> exakt 0 je Schema
    pays = scheme_payouts(spec_from_params(params_from_style("tag")), ["tag", "tag"], [1, 2], TINY)
    assert all(abs(x) < 1e-9 for x in pays)


def test_cem_and_gate_run(tmp_path):
    res = run_cem(generations=2, population=3, schemes_per_gen=1, pool=["station", "random"], config=TINY,
                  workers=2, out_dir=tmp_path)
    assert len(res["generations"]) == 2 and (tmp_path / "log.jsonl").exists()
    assert res["center"]["spec"].startswith("tag?")
    g = gate(res["center"]["spec"], "random", schemes=8, pool=["station", "rock"], config=TINY, workers=2)
    assert g["schemes"] == 8 and len(g["ci95"]) == 2
    assert g["diff_roi"] > 0                       # optimierter tag schlaegt einen Zufallsspieler


def test_resume_gives_same_result_as_uninterrupted(tmp_path):
    kw = dict(population=3, schemes_per_gen=1, pool=["station", "random"], config=TINY, workers=2, seed=4)
    full = run_cem(generations=2, out_dir=tmp_path / "a", **kw)
    run_cem(generations=1, out_dir=tmp_path / "b", **kw)                 # "Abbruch" nach Generation 1
    resumed = run_cem(generations=2, out_dir=tmp_path / "b", resume=True, **kw)
    assert [e["generation"] for e in resumed["generations"]] == [1, 2]
    assert resumed["center"] == full["center"]


def test_keep_awake_context():
    from pokercollector.system import keep_awake
    with keep_awake(False) as ok:
        assert ok is False
    with keep_awake(True):
        pass

def test_league_pool_sampling_weights_and_self_play():
    import random
    from pokercollector.ai.optimize import LeaguePool
    players = [("a", "rock", 50.0), ("b", "tag", 45.0), ("c", "lag", 30.0), ("d", "station", 14.0),
               ("e", "maniac", 15.0), ("f", "random", -7.0)]
    lp = LeaguePool(players, table=3, self_play=0.0)
    sh = lp.shares()
    assert abs(sum(sh.values()) - 1) < 1e-9 and sh["a"] > sh["b"] > sh["c"] > sh["f"] > 0
    rng = random.Random(3)
    counts = {}
    for _ in range(400):
        t = lp.sample(rng)
        assert len(t) == 3 and len(set(t)) == 3          # ohne Zuruecklegen
        for s in t:
            counts[s] = counts.get(s, 0) + 1
    assert counts["rock"] > counts["lag"] > counts["random"] > 0
    lp.self_play = 1.0
    assert "SELF" in lp.sample(random.Random(1), "SELF")


def test_cem_and_gate_with_league_pool(tmp_path):
    from pokercollector.ai.optimize import LeaguePool
    players = [("a", "station", 20.0), ("b", "random", 0.0), ("c", "rock", 30.0)]
    lp = LeaguePool(players, table=2)
    kw = dict(population=3, schemes_per_gen=2, pool=lp, config=TINY, workers=2, seed=5)
    full = run_cem(generations=2, out_dir=tmp_path / "a", **kw)
    assert all(len(t) == 2 for e in full["generations"] for t in e["tables"])
    assert "league" in full["pool"]
    run_cem(generations=1, out_dir=tmp_path / "b", **kw)
    resumed = run_cem(generations=2, out_dir=tmp_path / "b", resume=True, **kw)
    assert resumed["center"] == full["center"]          # Tische sind reproduzierbar
    g = gate(full["center"]["spec"], "random", schemes=8, pool=LeaguePool(players, table=2, self_play=0),
             config=TINY, workers=2)
    assert g["schemes"] == 8 and g["diff_roi"] > 0
