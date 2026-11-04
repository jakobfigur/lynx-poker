"""Server-Benchmark (1.11., Stufe 2): Suche mit Turn-Netz (leaf=4) und greedy Preflop gegen zwei Gegner,
Heads-up Cash duplicate, 40 und 100 BB, 16 Prozesse. Vorbild cloud/bench_humanopp_srv.py (31.10.).
Gegner: Menschen-Bot mit Folds (nn?run=human-1@1&fold=human-fold-1) und lynx-4@300 greedy (neue Referenz).
Varianten: siehe VARIANTS. Aufruf auf dem Server:
  uv run --quiet --project /opt/lynx/collector python /opt/lynx/cloud/bench_leaf4_srv.py 16 > /opt/lynx/data/bench/leaf4_srv.txt
Braucht auf dem Server: data/valuenet/vnet-river-1.pt und vnet-2.pt, data/rl/lynx-4/ckpt_000300.pt, lynx-5t/ckpt_000001.pt,
data/rl/human-1/ckpt_000001.pt, data/humans/human-fold-1.npz, data/league/players.json (cloud/upload-teacher-data.sh + vnet-2)."""
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

os.environ.setdefault("OMP_NUM_THREADS", "1")
C = "hus?bp=lynx-4-300&auto=1&iters=60&iters_river=150&threads=1&vnet=vnet-river-1&opp=human-1@1&oppfold=human-fold-1&bpgreedy=1"
VARIANTS = {
    "netz-g": "nn?run=lynx-4@300&greedy=1",
    "lynx5t-g": "nn?run=lynx-5t@1&greedy=1",
    "C-bpg": C,
    "C-bpg-g": C + "&greedy=1",
    "C-leaf4-8": C.replace("vnet=vnet-river-1", "vnet=vnet-2&leaf=4&k_turn=8"),
    "C-leaf4-all": C.replace("vnet=vnet-river-1", "vnet=vnet-2&leaf=4"),
    "C-5t-bpg": C.replace("bp=lynx-4-300", "bp=run:lynx-5t@1"),
}
OPPONENTS = {"mensch": "nn?run=human-1@1&fold=human-fold-1", "lynx4g": "nn?run=lynx-4@300&greedy=1"}
STACKS = (40, 100)
BLOCKS = 32         # Seed-Bloecke je (Variante, Gegner, Stack); 32 x 120 = 3840 Haende je Zelle
HANDS = 60          # Blaetter je Block (duplicate -> 120 Haende)


def task(args):
    name, spec, oname, ospec, stack, block = args
    from pokercollector.ai.agents import make_agent
    from pokercollector.ai.evaluate import run_match
    a = make_agent(f"{spec}:kand", 100 + block)
    b = make_agent(f"{ospec}:gegner", 200 + block)
    res = run_match([a, b], HANDS, seed=9000 + 97 * block + stack, small_blind=50, big_blind=100, stack_bb=stack)
    r = {x["agent"]: x for x in res["results"]}["kand"]
    return name, oname, stack, block, r["bb_per_100"], r["hands"], res["elapsed_s"]


def summary(acc, label):
    import math
    print(f"=== {label} ===", time.strftime("%H:%M"), flush=True)
    for (name, oname, stack), xs in sorted(acc.items()):
        m = sum(xs) / len(xs)
        sd = math.sqrt(sum((x - m) ** 2 for x in xs) / max(len(xs) - 1, 1))
        half = 2.04 * sd / math.sqrt(len(xs)) if len(xs) > 1 else float("nan")
        print(f"  {name:12} vs {oname:7} {stack:3d} BB: {m:+7.1f} bb/100 [{m - half:+.1f}; {m + half:+.1f}] ueber {len(xs) * 2 * HANDS} Haende", flush=True)


if __name__ == "__main__":
    jobs = [(n, s, on, os_, st, b) for b in range(BLOCKS) for on, os_ in OPPONENTS.items() for st in STACKS
            for n, s in VARIANTS.items()]
    print(f"=== leaf=4 / greedy-Suche: {len(jobs)} Matches x {2 * HANDS} Haende ===", time.strftime("%H:%M"), flush=True)
    acc = {}
    per_block = len(VARIANTS) * len(OPPONENTS) * len(STACKS)
    with ProcessPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as ex:
        for k, (name, oname, stack, block, bb100, hands, secs) in enumerate(ex.map(task, jobs)):
            acc.setdefault((name, oname, stack), []).append(bb100)
            print(f"  {name:12} vs {oname:7} {stack:3d} BB Block {block:2d}: {bb100:+7.1f} bb/100 ({hands} Haende, {secs:.0f}s)", flush=True)
            if (k + 1) % (per_block * 4) == 0:
                summary(acc, f"Zwischenstand nach Block {block}")
    summary(acc, "ERGEBNIS (Mittel der Bloecke, 95 %-Intervall ueber Bloecke)")
    print("ALLE MESSUNGEN FERTIG", time.strftime("%H:%M"), flush=True)
