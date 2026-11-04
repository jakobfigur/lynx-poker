"""31.10.: Hilft das Menschenmodell (human-1 + Fold-Modell human-fold-1) der Suche gegen den MENSCHEN-BOT MIT FOLDS (nn?run=human-1@1&fold=human-fold-1)?
Zweite Messreihe (31.10. vormittags): der erste Gegner (human-1 ohne Folds) war ein Calling-Station-Zerrbild mit Riesenvarianz.
Heads-up Cash duplicate, mehrere Stacktiefen, drei Varianten der Suche gegen nn?run=human-1@1:
  A  Standard-Ranges (auto=1, vnet)                      -> Gegner "spielt wie unser Netz"
  B  + opp=human-1@1                                     -> Gegneraktionen mit dem Menschen-Netz bewertet (ohne Folds)
  C  + opp=human-1@1 & oppfold=human-fold-1              -> dazu Weiterspiel-Faktor je Hand (Bayes-Rest)
Dazu das Netz lynx-4@300 allein als Referenz. Ausgabe bb/100 mit 95 %-Intervall je Variante und Stack.
Losgeloest starten; ProcessPool ueber (Variante, Stack, Seed-Block)."""
import sys
import time
from concurrent.futures import ProcessPoolExecutor

VARIANTS = {
    "netz": "nn?run=lynx-4@300",
    "A-standard": "hus?bp=lynx-4-300&auto=1&iters=60&iters_river=150&threads=2&vnet=vnet-river-1",
    "B-human": "hus?bp=lynx-4-300&auto=1&iters=60&iters_river=150&threads=2&vnet=vnet-river-1&opp=human-1@1",
    "C-human+fold": "hus?bp=lynx-4-300&auto=1&iters=60&iters_river=150&threads=2&vnet=vnet-river-1&opp=human-1@1&oppfold=human-fold-1",
}
STACKS = (40, 100)
BLOCKS = 6          # Seed-Bloecke je (Variante, Stack)
HANDS = 60          # Blaetter je Block (duplicate -> 120 Haende)


def task(args):
    name, spec, stack, block = args
    from pokercollector.ai.agents import make_agent
    from pokercollector.ai.evaluate import run_match
    a = make_agent(f"{spec}:kand", 100 + block)
    b = make_agent("nn?run=human-1@1&fold=human-fold-1:mensch", 200 + block)
    res = run_match([a, b], HANDS, seed=9000 + 97 * block + stack, small_blind=50, big_blind=100, stack_bb=stack)
    r = {x["agent"]: x for x in res["results"]}["kand"]
    return name, stack, block, r["bb_per_100"], r["hands"], res["elapsed_s"]


if __name__ == "__main__":
    import math
    jobs = [(n, s, st, b) for n, s in VARIANTS.items() for st in STACKS for b in range(BLOCKS)]
    print(f"=== Suche gegen Menschen-Bot human-1+Fold: {len(jobs)} Matches x {2 * HANDS} Haende ===", time.strftime("%H:%M"), flush=True)
    acc = {}
    with ProcessPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as ex:
        for name, stack, block, bb100, hands, secs in ex.map(task, jobs):
            acc.setdefault((name, stack), []).append(bb100)
            print(f"  {name:13} {stack:3d} BB Block {block}: {bb100:+7.1f} bb/100 ({hands} Haende, {secs:.0f}s)", flush=True)
    print("=== ERGEBNIS (Mittel der Bloecke, 95 %-Intervall ueber Bloecke) ===", time.strftime("%H:%M"), flush=True)
    for (name, stack), xs in sorted(acc.items()):
        m = sum(xs) / len(xs)
        sd = math.sqrt(sum((x - m) ** 2 for x in xs) / max(len(xs) - 1, 1))
        half = 2.57 * sd / math.sqrt(len(xs)) if len(xs) > 1 else float("nan")      # t(5) fuer 6 Bloecke
        print(f"  {name:13} {stack:3d} BB: {m:+7.1f} bb/100 [{m - half:+.1f}; {m + half:+.1f}] ueber {len(xs) * 2 * HANDS} Haende", flush=True)
    print("ALLE MESSUNGEN FERTIG", time.strftime("%H:%M"), flush=True)
