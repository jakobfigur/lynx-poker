import shutil

import numpy as np

from pokercollector.ai import teacher
from pokercollector.ai.nn_agent import rl_root


def test_lehrer_sammelt_weiche_ziele_und_schueler_lernt(tmp_path):
    out = tmp_path / "t.npz"
    meta = teacher.collect("hus?bp=lynx-3-300&iters=10&iters_river=20", "nn?run=lynx-3@300", ["station"],
                           hands=3, stacks_bb=[100], out=out, seed=5)
    assert meta["rows"] >= 1 and out.exists()
    d = teacher.load([out])
    assert d["x"].shape[1] == 57 and d["mask"].shape[1] == 8 and d["target"].shape[1] == 8
    assert np.allclose(d["target"].sum(1), 1.0, atol=1e-5)
    assert np.all(d["target"][~d["mask"]] == 0)                      # targets only on allowed actions
    assert set(np.unique(d["street"])) <= {2, 3}                      # only turn/river are searched
    run = "test-teacher-tmp"
    try:
        res = teacher.fit("lynx-3", 300, [out], run, epochs=2, batch=16, lr=1e-3, kl_coef=0.5, holdout=0.34,
                          log=lambda m: None)
        assert (rl_root() / run / "ckpt_000001.pt").exists() and len(res["hist"]) == 3
        from pokercollector.ai.agents import make_agent
        from pokercollector.ai.engine import Hand
        a = make_agent(f"nn?run={run}@1", 1)
        h = Hand([5000, 5000], 0, 50, 100, seed=2, hand_id="t")
        assert a.act(h.observation(h.to_act)).kind in ("fold", "call", "check", "raise")
    finally:
        shutil.rmtree(rl_root() / run, ignore_errors=True)
