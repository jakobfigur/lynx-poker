"""Wertnetz-Daten (Meilenstein 3): Format, Reproduzierbarkeit, Nullsumme."""
import numpy as np

from pokercollector.ai.valuedata import generate, load, sample_ranges, sample_state, solve_sample


def test_sample_state_und_ranges_sind_gueltig():
    rng = np.random.default_rng(3)
    for street, n in (("river", 5), ("turn", 4), ("flop", 3)):
        st, board, pot_bb, stack_bb = sample_state(rng, street)
        assert len(st.board) == n and len(board) == n and sum(st.committed) == round(pot_bb * 100)
        assert st.stacks[0] == st.stacks[1] >= 100 and st.to_act == st.oop
        r0, r1 = sample_ranges(rng, board)
        assert abs(r0.sum() - 1) < 1e-9 and abs(r1.sum() - 1) < 1e-9
        from pokercollector.ai.ranges import dead_mask
        assert r0[dead_mask(board)].sum() == 0 and r1[dead_mask(board)].sum() == 0


def test_solve_sample_reproduzierbar_und_nullsumme():
    a = solve_sample(11, "river", 40)
    b = solve_sample(11, "river", 40)
    assert np.array_equal(a["v0"], b["v0"]) and np.array_equal(a["board"], b["board"])
    r0, r1 = a["r0"].astype(float), a["r1"].astype(float)
    assert abs(float(r0 @ a["v0"].astype(float) + r1 @ a["v1"].astype(float))) < 0.02      # Pot-Einheiten


def test_generate_schreibt_scherbe(tmp_path):
    m = generate("river", 3, tmp_path / "r.npz", seed=5, iters=20)
    assert m["n"] == 3 and m["errors"] == 0
    d = load(tmp_path / "r.npz")
    assert d["r0"].shape == (3, 1326) and d["v1"].dtype == np.float16 and d["board"].shape == (3, 5)
    assert d["meta"]["street"] == "river" and list(d["seed"]) == [5, 6, 7]


def test_river_leaf_zeilen_aus_turnsuche():
    """river-leaf: Turn-Baum loesen, Ranges an River-Anfaengen auslesen, exakt loesen. Zeilen haben das normale
    Format, Ranges sind normiert und frei von Boardkarten, die Werte sind (bis auf Konvergenz) nullsummig."""
    import numpy as np
    from pokercollector.ai.husearch import average_reaches, build_tree
    from pokercollector.ai.valuedata import sample_ranges, sample_state, solve_leaf_samples
    from pokercollector.ai.valuenet import combo_mask
    rows = solve_leaf_samples(seed=7, iters=60, iters_turn=8, max_per_turn=3)
    assert 1 <= len(rows) <= 3
    for r in rows:
        assert r["board"].shape == (5,) and (r["board"] >= 0).all() and r["r0"].shape == (1326,)
        m = combo_mask(r["board"][None])[0]
        for key in ("r0", "r1"):
            x = r[key].astype(np.float64)
            assert abs(x.sum() - 1) < 1e-2 and np.all(x[~m] == 0)
        zs = float((r["r0"].astype(float) * r["v0"].astype(float)).sum() + (r["r1"].astype(float) * r["v1"].astype(float)).sum())
        assert abs(zs) < 0.05
        assert r["pot_bb"] > 0 and r["stack_bb"] > 0 and r["seed"] == 7
    # average_reaches: an der Wurzel die Start-Ranges, an Zufallskindern ohne die gefallene Karte
    rng = np.random.default_rng(1)
    st, board, _, _ = sample_state(rng, "turn")
    r0, r1 = sample_ranges(rng, board)
    tree = build_tree(st)
    avg = np.ones((len(tree.kind), 1326))
    R0, R1 = average_reaches(tree, avg, r0, r1)
    assert np.allclose(R0[0], r0) and np.allclose(R1[0], r1)
    assert tree.river_roots and all(len(s.board) == 5 for _, s in tree.river_roots)
    n, s = tree.river_roots[0]
    from pokercollector.ai.ranges import dead_mask
    from pokercollector.poker import FULL_DECK
    assert np.all(R0[n][dead_mask([FULL_DECK[s.board[4]]])] == 0)


def test_turn_leaf_zeilen_aus_flopsuche():
    """turn-leaf (Stufe 2): Flop-Baum mit gezogenen Karten loesen, Ranges an Turn-Anfaengen auslesen, Turn-Teilbaum
    mit dem River-Wertnetz als Blatt loesen. Zeilen haben 4 Boardkarten, normierte Ranges, Werte ~nullsummig."""
    import numpy as np
    import pytest
    from pokercollector.ai.valuedata import data_dir, solve_turn_leaf_samples
    from pokercollector.ai.valuenet import combo_mask
    if not (data_dir() / "vnet-river-1.pt").exists():
        pytest.skip("kein River-Wertnetz vnet-river-1")
    rows = solve_turn_leaf_samples(seed=11, iters=20, vnet="vnet-river-1", iters_flop=6, max_per_flop=3)
    assert 1 <= len(rows) <= 3
    for r in rows:
        assert r["board"].shape == (5,) and (r["board"] >= 0).sum() == 4 and r["board"][4] == -1
        m = combo_mask(r["board"][None])[0]
        for key in ("r0", "r1"):
            x = r[key].astype(np.float64)
            assert abs(x.sum() - 1) < 1e-2 and np.all(x[~m] == 0)
        zs = float((r["r0"].astype(float) * r["v0"].astype(float)).sum() + (r["r1"].astype(float) * r["v1"].astype(float)).sum())
        assert abs(zs) < 0.08
        assert r["pot_bb"] > 0 and r["stack_bb"] > 0 and r["seed"] == 11
