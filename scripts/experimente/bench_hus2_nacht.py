"""hus-2 (search also at the flop, dealt cards 6/6, preset narrow) against network lynx-4-300 and against hus-1 on hu480,
paired. 4 workers x 3 numba threads = 12 threads. Night run 29./30.10.
The __main__ guard is mandatory (Windows spawn restarts this script in each worker)."""
from pokercollector.ai.bench import run_bench, compare

SPEC = "hus?bp=lynx-4-300&iters=60&iters_river=150&iters_flop=30&streets=preflop,flop,turn,river&threads=3"
NAME = "hus2-lynx-4-300"


def main():
    run_bench(SPEC, NAME, sets=("hu480",), workers=4,
              progress=lambda s, r: print(s, r.get("roi"), r.get("ci95"), flush=True))
    for other in ("lynx-4@300", "hus-lynx-4-300"):
        try:
            for s, ra, rb, d in compare(NAME, other):
                print(f"{s}: {NAME} {ra['roi']:+.1f} vs {other} {rb['roi']:+.1f}  Difference {d['roi']:+.1f} "
                      f"[{d['ci95'][0]:+.1f}; {d['ci95'][1]:+.1f}]", flush=True)
        except Exception as e:      # Comparison partner missing or similar: measurement itself remains valid
            print(f"Comparison with {other} not possible: {e}", flush=True)


if __name__ == "__main__":
    main()
