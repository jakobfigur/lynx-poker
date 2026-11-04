"""Oct 30: Search with blueprint ranges (bpranges.py) on hu480, paired against network and the heuristic search.
  D  hus1bp:  streets=turn,river, ranges=pre       (preflop actions evaluated with network)
  E  hus1bpf: streets=turn,river, ranges=pre,flop  (also flop actions)
References: lynx-4@300 (+46.5), hus1np-lynx-4-300 (heuristic ranges, +37.9), hus-lynx-4-300 (hus-1, +17.1).
Start independently (Start-Process), 4 workers x 3 threads. __main__ guard mandatory (Windows spawn)."""
import time

from pokercollector.ai.bench import compare, run_bench

BP = "lynx-4-300"
REF = ("lynx-4@300", "hus1np-lynx-4-300", "hus-lynx-4-300")


def cmp(name, others):
    for other in others:
        try:
            for s, ra, rb, d in compare(name, other):
                print(f"  {s}: {name} {ra['roi']:+.1f} vs {other} {rb['roi']:+.1f}  Difference {d['roi']:+.1f} "
                      f"[{d['ci95'][0]:+.1f}; {d['ci95'][1]:+.1f}]", flush=True)
        except Exception as e:
            print(f"  Comparison with {other} not possible: {e}", flush=True)


def phase_bench(tag, spec, name):
    print(f"=== {tag}: {spec} ===", time.strftime("%H:%M"), flush=True)
    # resume=True: completed blocks are in data/bench/partial-<name>-hu480.json; restarting this script
    # continues calculating (on the morning of 30.10 the parent process died after 85 minutes without a trace, everything lost)
    run_bench(spec, name, sets=("hu480",), workers=4, resume=True,
              on_chunk=lambda k, n, z: print(f"  Block {k}/{n}: running {z['roi']:+.1f} [{z['ci95'][0]:+.1f}; {z['ci95'][1]:+.1f}]",
                                             time.strftime("%H:%M"), flush=True),
              progress=lambda s, r: print(' ', s, r.get("roi"), r.get("ci95"), flush=True))
    cmp(name, REF)
    print(f"=== {tag} done ===", time.strftime("%H:%M"), flush=True)


if __name__ == "__main__":
    phase_bench("D", f"hus?bp={BP}&iters=60&iters_river=150&threads=3&ranges=pre", f"hus1bp-{BP}")
    phase_bench("E", f"hus?bp={BP}&iters=60&iters_river=150&threads=3&ranges=pre,flop", f"hus1bpf-{BP}")
    cmp(f"hus1bpf-{BP}", (f"hus1bp-{BP}",))
    print('ALL MEASUREMENTS COMPLETE', time.strftime("%H:%M"), flush=True)
