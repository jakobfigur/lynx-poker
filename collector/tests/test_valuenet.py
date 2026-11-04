"""Value network (milestone 3): Features, mask, zero-sum correction, mini-training learns."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from pokercollector.ai.valuedata import generate                     # noqa: E402
from pokercollector.ai.valuenet import N_IN, ValueMLP, ValueNet, combo_mask, features, train, zero_sum_fix  # noqa: E402
from pokercollector.ai.ranges import COMBOS, dead_mask                # noqa: E402
from pokercollector.poker import FULL_DECK                            # noqa: E402


def test_combos_und_maske_passen_zu_ranges():
    from pokercollector.ai.valuenet import _COMBOS
    assert np.array_equal(_COMBOS, COMBOS)
    board = np.array([[0, 5, 10, -1, -1]], np.int8)
    m = combo_mask(board)[0]
    cards = [FULL_DECK[0], FULL_DECK[5], FULL_DECK[10]]
    assert np.array_equal(m, ~dead_mask(cards))


def test_features_form_und_nullsumme():
    board = np.array([[0, 5, 10, 20, -1], [1, 2, 3, -1, -1]], np.int8)
    r0 = np.full((2, 1326), 1 / 1326.0)
    r1 = r0.copy()
    x = features(board, np.array([10.0, 3.0]), np.array([40.0, 6.0]), np.array([1, 0]), r0, r1)
    assert x.shape == (2, N_IN) and x[0, 52 + 1] == 1.0 and x[1, 52 + 0] == 1.0 and x[0, 58] == 1.0
    v0 = np.random.default_rng(0).normal(size=(2, 1326))
    v1 = np.random.default_rng(1).normal(size=(2, 1326))
    a, b = zero_sum_fix(v0, v1, r0, r1)
    assert np.allclose((r0 * a).sum(1) + (r1 * b).sum(1), 0, atol=1e-9)


def test_mini_training_lernt_und_predict_hat_nullsumme(tmp_path):
    p = tmp_path / "r.npz"
    generate("river", 24, p, seed=100, iters=30)
    out = tmp_path / "vnet.pt"
    res = train([str(p)], out, epochs=12, batch=8, lr=2e-3, width=64, depth=2, holdout=0.1, device="cpu",
                log=lambda *_: None)
    h = res["hist"]
    assert h[-1]["train_loss"] < h[0]["train_loss"]
    net = ValueNet.load(out)
    board = np.array([[0, 5, 10, 20, 30]], np.int8)
    r = np.full((1, 1326), 1 / 1326.0)
    v0, v1 = net.predict(board, np.array([10.0]), np.array([20.0]), np.array([0]), r, r)
    assert v0.shape == (1, 1326) and abs(float((r * v0).sum() + (r * v1).sum())) < 1e-9
    assert np.all(v0[0][~combo_mask(board)[0]] == 0)                 # blocked combinations 0
