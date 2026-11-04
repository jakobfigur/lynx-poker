import json

from pokercollector.ai.bench import bench_set, paired_diff, write_report


def test_testsets_fixed_and_valid():
    a, b = bench_set("mix96"), bench_set("mix96")
    assert a == b and len(a) == 96                          # never randomly different
    assert all(len(t) == 5 and len(set(t)) == 5 for _, t in a)
    assert len({sd for sd, _ in a} | {sd for sd, _ in bench_set("fest48")}) == 96 + 48


def test_paired_diff_and_report(tmp_path, monkeypatch):
    monkeypatch.setenv("POKERCOLLECTOR_DATA", str(tmp_path))
    from pokercollector.ai.bench import bench_dir
    rock = {"name": "rock", "spec": "rock", "t": '2026-10-26 12:00:00', "bench_version": "bench-1",
            "mix96": {"roi": 10.0, "ci95": [0, 20], "n": 3, "per_scheme": [0.1, 0.2, 0.0]}}
    cand = {"name": "kand", "spec": "x", "t": '2026-10-26 13:00:00', "bench_version": "bench-1",
            "mix96": {"roi": 20.0, "ci95": [10, 30], "n": 3, "per_scheme": [0.2, 0.3, 0.1]}}
    d = paired_diff(cand, rock, "mix96")
    assert d["roi"] == 10.0 and d["ci95"][0] == d["ci95"][1] == 10.0   # constant difference
    bench_dir().mkdir(parents=True)
    (bench_dir() / "results.jsonl").write_text(json.dumps(rock) + "\n" + json.dumps(cand) + "\n", "utf-8")
    md = write_report()
    assert md.index('| kand') < md.index('| rock') and '+10.0 [+10; +10]' in md


def test_format_sets():
    from pokercollector.ai.bench import FORMAT_SETS, set_config
    for name, (k, cfg) in FORMAT_SETS.items():
        sets = bench_set(name)
        assert len(sets) == 48 and all(len(t) == k for _, t in sets)
        assert bench_set(name) == sets and set_config(name) is cfg
    assert len({sd for n in FORMAT_SETS for sd, _ in bench_set(n)}) == 48 * len(FORMAT_SETS)


def test_run_set_fortschritt_und_wiederaufnahme(tmp_path, monkeypatch):
    """ Completed blocks are immediately saved in the partial file; a restart only processes missing blocks,
    the result is identical to a run in one go; on_chunk reports each block."""
    import json
    from concurrent.futures import ThreadPoolExecutor
    from pokercollector.ai import bench

    mus = [(i, ["a"]) for i in range(50)]
    monkeypatch.setattr(bench, "bench_set", lambda name: mus)
    monkeypatch.setattr(bench, "set_config", lambda name: None)
    calls = []

    def fake_chunk(args):
        spec, sub, cfg = args
        calls.append(len(sub))
        return [0.01 * m[0] for m in sub]
    monkeypatch.setattr(bench, "_chunk", fake_chunk)
    with ThreadPoolExecutor(2) as ex:
        full = bench.run_set("x", "s", ex)
    assert full["n"] == 50 and len(calls) == 24
    # "Crash" after 10 blocks: partial file with the first 10 blocks exists
    saved = {str(i): [0.01 * m[0] for m in mus[i::24]] for i in range(10)}
    partial = tmp_path / "partial.json"
    partial.write_text(json.dumps({"spec": "x", "set": "s", "chunks": saved}), "utf-8")
    calls.clear()
    seen = []
    with ThreadPoolExecutor(2) as ex:
        again = bench.run_set("x", "s", ex, on_chunk=lambda k, n, z: seen.append((k, n, z["n"])), partial=partial)
    assert len(calls) == 14                                   # only the missing blocks
    assert again["per_scheme"] == full["per_scheme"] and again["roi"] == full["roi"]
    assert [k for k, _, _ in seen] == list(range(11, 25)) and all(n == 24 for _, n, _ in seen)
    assert not partial.exists()                               # cleaned up
    # partial file from another specification is ignored
    partial.write_text(json.dumps({"spec": "anders", "set": "s", "chunks": saved}), "utf-8")
    calls.clear()
    with ThreadPoolExecutor(2) as ex:
        bench.run_set("x", "s", ex, partial=partial)
    assert len(calls) == 24
