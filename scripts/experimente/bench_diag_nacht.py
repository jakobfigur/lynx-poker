"""Nacht 29./30.10.: Warum verliert die Suche hus-1 auf hu480 29 Punkte gegen ihr eigenes Blueprint-Netz?
Drei Messungen nacheinander (CPU frei, 4 Prozesse x 3 numba-Faeden):
  A  nur Preflop-Loeser (hupreflop), postflop Netz            -> trennt den Preflop-Anteil ab
  B  Suche Turn+River OHNE Preflop-Loeser                     -> trennt den Postflop-Anteil ab
  C  hus-1 gegen lynx-4@300 direkt, HU 200 BB Cash duplicate  -> schlaegt die Suche ihr Blueprint im Heimformat?
Der __main__-Schutz ist Pflicht (Windows spawn startet dieses Skript in jedem Worker neu)."""
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
                print(f"  {s}: {name} {ra['roi']:+.1f} vs {other} {rb['roi']:+.1f}  Differenz {d['roi']:+.1f} "
                      f"[{d['ci95'][0]:+.1f}; {d['ci95'][1]:+.1f}]", flush=True)
        except Exception as e:
            print(f"  Vergleich mit {other} nicht moeglich: {e}", flush=True)


def phase_bench(tag, spec, name):
    print(f"=== {tag}: {spec} ===", time.strftime("%H:%M"), flush=True)
    run_bench(spec, name, sets=("hu480",), workers=4,
              progress=lambda s, r: print(" ", s, r.get("roi"), r.get("ci95"), flush=True))
    cmp(name, REF)
    print(f"=== {tag} fertig ===", time.strftime("%H:%M"), flush=True)


def _h2h_task(k):
    from pokercollector.ai.agents import make_agent
    from pokercollector.ai.evaluate import run_match
    a = make_agent(f"hus?bp={BP}&iters=60&iters_river=150&threads=3:hus", k)
    b = make_agent(f"nn?run=lynx-4@300:bp", k)
    res = run_match([a, b], 25, seed=1000 + k, small_blind=50, big_blind=100, stack_bb=200)
    r = {x["agent"]: x for x in res["results"]}
    return k, r["hus"]["bb_per_100"], r["hus"]["hands"], res["elapsed_s"], r["hus"]["vpip"], r["hus"]["pfr"]


def phase_c(tasks=40):
    print(f"=== C: hus-1 vs lynx-4@300, HU 200 BB Cash duplicate, {tasks} x 25 Blaetter ===", time.strftime("%H:%M"),
          flush=True)
    vals = []
    with ProcessPoolExecutor(4) as ex:
        for k, bb100, hands, secs, vpip, pfr in ex.map(_h2h_task, range(tasks)):
            vals.append(bb100)
            m = sum(vals) / len(vals)
            print(f"  Aufgabe {k}: {bb100:+.1f} bb/100 ({hands} Haende, {secs:.0f}s, VPIP {vpip} PFR {pfr}); "
                  f"laufend {m:+.1f} nach {len(vals)}", flush=True)
    n = len(vals)
    m = sum(vals) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / (n - 1))
    ci = 1.96 * sd / math.sqrt(n)
    print(f"ERGEBNIS C: hus-1 vs lynx-4@300: {m:+.1f} bb/100 [{m - ci:+.1f}; {m + ci:+.1f}] ueber {n * 50} Haende",
          flush=True)
    print("=== C fertig ===", time.strftime("%H:%M"), flush=True)


def main():
    phase_bench("A", f"hus?bp={BP}&streets=preflop", f"hupre-{BP}")
    phase_bench("B", f"hus?bp={BP}&streets=turn,river&iters=60&iters_river=150&threads=3", f"hus1np-{BP}")
    phase_c()
    print("ALLE DIAGNOSEN FERTIG", time.strftime("%H:%M"), flush=True)


if __name__ == "__main__":
    main()
