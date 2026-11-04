"""30.10 evening: Search with value network leaves (hus1v) on hu480. Template bench_hus1bp.py.
"""
'Oct 30: Search with Blueprint-Ranges (bpranges.py) on hu480, paired against network and against heuristic search.\n  D  hus1bp:  streets=turn,river, ranges=pre       (Preflop actions evaluated with the network)\n  E  hus1bpf: streets=turn,river, ranges=pre,flop  (also flop actions)\nReferences: lynx-4@300 (+46.5), hus1np-lynx-4-300 (heuristic ranges, +37.9), hus-lynx-4-300 (hus-1, +17.1).\nRun detached (Start-Process), 4 workers x 3 threads. __main__ protection mandatory (Windows spawn).'
import time

from pokercollector.ai.bench import compare, run_bench

BP = "lynx-4-300"
REF = ("lynx-4@300", "hus1v-lynx-4-300", "hus1bpf-lynx-4-300")


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
    # resume=True: completed blocks are in data/bench/partial-<name>-hu480.json; a restart of this script
    # continues calculating (on the morning of 30.10 the parent process died after 85 minutes without a trace, everything lost)
    run_bench(spec, name, sets=("hu480", "mensch480"), workers=2, resume=True,
              on_chunk=lambda k, n, z: print(f"  Block {k}/{n}: running {z['roi']:+.1f} [{z['ci95'][0]:+.1f}; {z['ci95'][1]:+.1f}]",
                                             time.strftime("%H:%M"), flush=True),
              progress=lambda s, r: print(' ', s, r.get("roi"), r.get("ci95"), flush=True))
    cmp(name, REF)
    print(f"=== {tag} done ===", time.strftime("%H:%M"), flush=True)


if __name__ == "__main__":
    # H: Search (auto-format, network leaves) with HUMAN MODEL human-1 as opponent range (H11 step 5) on hu480 + mensch480
    # V: Search like E (streets=turn,river, ranges=pre,flop), but river subtrees in turn tree replaced by the value network
    # kaggle-t2-big (2048x3, 752k mixed) replaced -> faster; question: does it play as strongly as E (+44.0)?
    phase_bench("H", f"hus?bp={BP}&auto=1&opp=human-1@1&iters=60&iters_river=150&threads=3&vnet=kaggle-t2-big/vnet-river", f"hus1h-{BP}")
    print('ALL MEASUREMENTS COMPLETE', time.strftime("%H:%M"), flush=True)
