import numpy as np
import pytest

from pokercollector.ai import humandata, humanfold
from pokercollector.ai.engine import Hand
from pokercollector.ai.nn_agent import rl_root
from pokercollector.ai.observation import Action

DATA = rl_root().parent          # <Projekt>/data bzw. $POKERCOLLECTOR_DATA (3.11.: statt fester Stick-Pfade)


def _obs_flop():
    h = Hand([5000, 5000, 5000], 2, 50, 100, seed=4, hand_id="hf")   # 3-max, Button Platz 2
    h.apply(2, Action.raise_to(250))
    h.apply(0, Action.fold())
    h.apply(1, Action.call())
    return h, h.observation(h.to_act)                                 # Flop, BB (Platz 1) handelt zuerst


def test_public_vector_passt_zu_den_scherbenspalten():
    h, obs = _obs_flop()
    x = humanfold.public_vector(obs)
    assert x.shape == (humanfold.PUBLIC_DIM,) and x[1] == 1.0 and x[14] == 0.0      # Flop, kein Einsatz offen
    rows = humandata.public_rows({"variant": "NT", "antes": [0, 0, 0], "blinds_or_straddles": [0.5, 1.0, 0],
                                  "min_bet": 1.0, "starting_stacks": [50.0, 50.0, 50.0], "players": ["A", "B", "C"],
                                  "actions": ["d dh p1 ????", "d dh p2 ????", "d dh p3 ????", "p3 cbr 2.5", "p1 f",
                                              "p2 cc", "d db AhKd7c", "p2 cc", "p3 cc", "d db 2s", "p2 cc", "p3 cc",
                                              "d db 9h", "p2 cc", "p3 cc", "p2 sm AsTc"]}, 1)[2]
    r = rows[3]                                                       # p2 am Flop, erste Entscheidung
    y = humanfold.public_vector_arrays(*[[r[k]] for k in ("street", "position", "n_players", "n_live", "pot_bb",
                                                             "to_call_bb", "stack_bb", "raises_street", "raises_pre",
                                                             "facing", "aggressor", "board_paired", "board_suited",
                                                             "board_high")])[0]
    keep = [i for i in range(humanfold.PUBLIC_DIM) if i not in (16, 17, 18)]   # Board ist hier zufaellig anders
    assert np.allclose(x[keep], y[keep], atol=1e-6)                   # Training und Einsatz rechnen gleich


def test_fold_modell_training_und_faktor(tmp_path):
    rows_dir = DATA / "humans" / "actions"
    if not any(rows_dir.glob("public-*.npz")):
        pytest.skip("keine public-Scherben")
    res = humanfold.train(rows_dir, tmp_path / "hf.npz", max_rows=40000, epochs=1, hidden_f=16, hidden_g=32,
                          batch=2048, max_shards=1, log=lambda m: None)
    hf = humanfold.HumanFold.load(res["out"])
    h, obs = _obs_flop()
    x = humanfold.public_vector(obs)
    pf = hf.p_fold(x)
    assert pf.shape == (1,) and 0 < pf[0] < 1
    pc = hf.p_class(x)
    assert pc.shape == (1, 169) and abs(pc.sum() - 1) < 1e-5
    fac = hf.continue_factor(obs, np.ones(1326))
    assert fac.shape == (1326,) and np.all(fac >= 0) and np.all(fac <= 1) and 0 < fac.mean() < 1
    # preflop gegen einen Raise foldet ein Mensch meistens: Fold-Wahrscheinlichkeit hoch, ohne Einsatz niedrig
    h2 = Hand([5000, 5000, 5000], 2, 50, 100, seed=4, hand_id="hf2")
    h2.apply(2, Action.raise_to(250))
    pre = hf.p_fold(humanfold.public_vector(h2.observation(0)))[0]
    assert pre > hf.p_fold(x)[0]


def test_netzbot_mit_fold_modell_wirft_schwache_haende_weg():
    from pokercollector.ai.agents import make_agent
    from pokercollector.ai.evaluate import run_match
    fm = DATA / "humans" / "human-fold-1.npz"
    if not fm.exists() or not (DATA / "rl" / "human-1" / "ckpt_000001.pt").exists():
        pytest.skip("Fold-Modell oder human-1 fehlt")
    bot = make_agent("nn?run=human-1@1&fold=human-fold-1:m", 1)
    h = Hand([10000, 10000], 1, 50, 100, seed=7, hand_id="pf")                   # HU, Button raist 3 BB
    h.apply(1, Action.raise_to(300))
    obs = h.observation(0)
    obs.hole_cards = ["Ah", "Ad"]
    strong = bot.p_fold_hand(obs)
    obs.hole_cards = ["7d", "2c"]
    weak = bot.p_fold_hand(obs)
    assert strong < 0.1 < 0.8 < weak
    assert bot.p_fold_hand(h.observation(1)) == 0.0                              # ohne offenen Einsatz kein Fold
    import dataclasses
    folds = sum(bot.act(dataclasses.replace(obs, hand_id=f"pf{s}")).kind == "fold" for s in range(40))
    assert folds >= 25                                                            # ~97 % bei 72o
    plain = make_agent("nn?run=human-1@1:ohne", 1)
    res = run_match([plain, bot], 40, seed=3, small_blind=50, big_blind=100, stack_bb=100)
    assert res["results"][0]["hands"] == 80
