"""Night Oct 29/30: Why does the search hus-1 lose 29 points on hu480 against its own blueprint network?
Three consecutive measurements (CPU idle, 4 processes x 3 numba threads):
  A  only preflop solver (hupreflop), postflop network            -> isolates the preflop component
  B  search Turn+River WITHOUT preflop solver                     -> isolates the postflop component
  C  hus-1 directly against lynx-4@300, HU 200 BB Cash duplicate  -> does the search beat its blueprint in home format?
The __main__ guard is mandatory (Windows spawn starts this script anew in every worker)."""
import math
import time
from concurrent.futures import ProcessPoolExecutor

from pokercollector.ai.bench import compare, run_bench

BP = "lynx-4-300"
REF = ("lynx-4@300", "hus-lynx-4-300")


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
    run_bench(spec, name, sets=("hu480",), workers=4,
              progress=lambda s, r: print(' ', s, r.get("roi"), r.get("ci95"), flush=True))
    cmp(name, REF)
    print(f"=== {tag} complete ===", time.strftime("%H:%M"), flush=True)


def _h2h_task(k):
    from pokercollector.ai.agents import make_agent
    from pokercollector.ai.evaluate import run_match
    a = make_agent(f"hus?bp={BP}&iters=60&iters_river=150&threads=3:hus", k)
    b = make_agent(f"nn?run=lynx-4@300:bp", k)
    res = run_match([a, b], 25, seed=1000 + k, small_blind=50, big_blind=100, stack_bb=200)
    r = {x["agent"]: x for x in res["results"]}
    return k, r["hus"]["bb_per_100"], r["hus"]["hands"], res["elapsed_s"], r["hus"]["vpip"], r["hus"]["pfr"]


def phase_c(tasks=40):
    print(f"=== C: hus-1 vs lynx-4@300, HU 200 BB Cash duplicate, {tasks} x 25 blocks ===", time.strftime("%H:%M"),
          flush=True)
    vals = []
    with ProcessPoolExecutor(4) as ex:
        for k, bb100, hands, secs, vpip, pfr in ex.map(_h2h_task, range(tasks)):
            vals.append(bb100)
            m = sum(vals) / len(vals)
            print(f"  Task {k}: {bb100:+.1f} bb/100 ({hands} hands, {secs:.0f}s, VPIP {vpip} PFR {pfr}); "
                  f"running {m:+.1f} after {len(vals)}", flush=True)
    n = len(vals)
    m = sum(vals) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / (n - 1))
    ci = 1.96 * sd / math.sqrt(n)
    print(f"RESULT C: hus-1 vs lynx-4@300: {m:+.1f} bb/100 [{m - ci:+.1f}; {m + ci:+.1f}] over {n * 50} hands",
          flush=True)
    print('=== C complete ===', time.strftime("%H:%M"), flush=True)


def main():
    phase_bench("A", f"hus?bp={BP}&streets=preflop", f"hupre-{BP}")
    phase_bench("B", f"hus?bp={BP}&streets=turn,river&iters=60&iters_river=150&threads=3", f"hus1np-{BP}")
    phase_c()
    print('ALL DIAGNOSTICS COMPLETE', time.strftime("%H:%M"), flush=True)


if __name__ == "__main__":
    main()
