"""Search (hus) against network alone on the PokerTH test rig hu480, paired. Decides live standard.
Base since 29.10.: lynx-4-300 (comparison against the test run 'lynx-4@300' from night training).
The __main__ guard is mandatory: on Windows each worker process restarts this script (spawn); without the
protection each worker called run_bench again -> BrokenProcessPool (night 29.10.)."""
from pokercollector.ai.bench import run_bench, compare


def main():
    run_bench("hus?bp=lynx-4-300&iters=60&iters_river=150", "hus-lynx-4-300", sets=("hu480",), workers=4,
              progress=lambda s, r: print(s, r.get("roi"), r.get("ci95"), flush=True))
    for s, ra, rb, d in compare("hus-lynx-4-300", "lynx-4@300"):
        print(f"{s}: {ra['roi']:+.1f} vs {rb['roi']:+.1f}  Difference {d['roi']:+.1f} [{d['ci95'][0]:+.1f}; {d['ci95'][1]:+.1f}]")


if __name__ == "__main__":
    main()
