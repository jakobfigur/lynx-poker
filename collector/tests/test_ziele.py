from pokercollector.ai import ziele
from pokercollector.ai.bench import ENDGAME_CONFIG, NASH_BOT, bench_set, set_config


def test_endspiel_sets():
    assert bench_set("nash3") == [(996_000 + i, [NASH_BOT]) for i in range(3)]
    k = bench_set("kurz5")
    assert len(k) == 5 and all(len(t) == 1 for _, t in k)
    assert set_config("nash240") is ENDGAME_CONFIG and set_config("kurz10").start_stack == 400


def test_turniere_und_tafel(tmp_path, monkeypatch):
    monkeypatch.setenv("POKERCOLLECTOR_DATA", str(tmp_path))
    ziele.add_tournament(1, 6, "lynx-x")
    ziele.add_tournament(4, 6, "lynx-x")
    s = ziele.pokerth_summary("lynx-x")
    assert s["n"] == 2 and s["wins"] == 1
    assert abs(s["roi"] - 100 * ((0.5 * 6 - 1) + (0 - 1)) / 2) < 0.1
    rows = ziele.scoreboard("lynx-x")
    assert [r["ziel"] for r in rows] == [1, 2, 3, 4, 5]
    assert rows[0]["erreicht"] == 0 and "2 tournaments" in rows[0]["wert"]
    assert "not measured" in rows[1]["wert"]
    assert "Goals for lynx-x" in ziele.scoreboard_text("lynx-x", rows)


def test_stufen():
    assert ziele._stage(2, {"mensch480": {"roi": 110.0, "ci95": [100.0, 120.0]}})[0] == 1
    sl = {"hands": 20000, "allin_ev": {"bb100": 3.0, "ci95": [-5.0, 11.0]}}
    assert ziele._stage(3, {"slumbot": sl})[0] == 2
    assert ziele._stage(5, {"nash240": {"roi": 1.0, "ci95": [-5, 7]}, "kurz240": {"roi": 25.0, "ci95": [10, 40]}})[0] == 2
