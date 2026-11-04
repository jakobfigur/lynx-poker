import pytest

from pokercollector.ai.icm import icm_equities, icm_equity, prizes_from


def test_preisgeld_wird_vollstaendig_verteilt():
    prizes = prizes_from((0.5, 0.3, 0.2), 6)
    assert prizes == pytest.approx([3.0, 1.8, 1.2])
    eq = icm_equities([3000, 1500, 900, 600, 0, 0], prizes)
    assert sum(eq) == pytest.approx(6.0)
    assert eq[4] == 0 and eq[5] == 0
    assert eq[0] > eq[1] > eq[2] > eq[3] > 0


def test_gleiche_stacks_gleiches_kapital():
    eq = icm_equities([1000, 1000, 1000], prizes_from((0.5, 0.3, 0.2), 3))
    assert all(e == pytest.approx(1.0) for e in eq)


def test_sieger_nimmt_alles_entspricht_chipanteil():
    eq = icm_equities([3000, 1000], [2.0])
    assert eq == pytest.approx([1.5, 0.5])


def test_icm_bestraft_chipfuehrer_bei_flacher_auszahlung():
    # 4 Spieler, 3 bezahlt: der Big Stack ist weniger wert als sein Chipanteil, der Kurzstack mehr
    prizes = prizes_from((0.5, 0.3, 0.2), 4)
    stacks = [2500, 500, 500, 500]
    eq = icm_equities(stacks, prizes)
    chip_share = [s / 4000 * 4 for s in stacks]
    assert eq[0] < chip_share[0] and eq[1] > chip_share[1]


def test_zwei_uebrig_und_einer_weg():
    assert icm_equity([5000, 1000], [3.0, 1.8], 0) == pytest.approx(3.0 * 5 / 6 + 1.8 * 1 / 6)
    assert icm_equity([6000, 0], [3.0, 1.8], 0) == 3.0


def test_icm_belohnung_im_rollout():
    """Ein kurzes Training-Rollout mit ICM-Belohnung laeuft durch, und die Belohnungssumme je Turnier ist
    die Aenderung des Eigenkapitals (Start 1 Buy-in -> Auszahlung)."""
    import random
    from pokercollector.ai.rl import _rollout_job
    from pokercollector.ai.nn_agent import build_net, numpy_weights
    from pokercollector.ai.tournament import TournamentConfig, BlindSchedule
    w = numpy_weights(build_net(16))
    cfg = TournamentConfig(start_stack=400, blinds=BlindSchedule(10, 20, 5), payouts=(0.5, 0.3, 0.2))
    tables = [["rock", "tag", "station", "lag", "maniac"]]
    data, stats = _rollout_job((w, tables, [7], cfg, 10.0, 1, 1.0))
    assert stats["tournaments"] == 1 and stats["hands"] > 0
    # Summe der Belohnungen (/scale) = Auszahlung - 1 Buy-in, wenn der Lerner bis zum Ende oder Ausscheiden spielt
    total = float(data["r"].sum()) / 10.0
    assert -1.0 - 1e-6 <= total <= 2.0 + 1e-6
