"""Oct 31 evening: Greedy in search and turn-network - search against the HUMAN BOT WITH FOLDS (nn?run=human-1@1&fold=human-fold-1).
Server snapshot (7680 hands per cell, humanopp_srv.txt): C-human+fold 40 BB +30.4 / 100 BB +29.3; greedy lynx-5t +64/+66.
Variants (heads-up cash duplicate, 40 and 100 BB):
  netz-g     nn?run=lynx-4@300&greedy=1                                  reference network greedy
  lynx5t-g   nn?run=lynx-5t@1&greedy=1                                   reference teacher-student greedy
  C          search like server variant C (opp+oppfold)                  baseline
  C-bpg      + bpgreedy=1   (blueprint plays greedy where search not done: preflop)
  C-bpg-g    + greedy=1     (search itself takes top action)
  C-5t-bpg   blueprint lynx-5t instead of lynx-4 (ranges from student), bpgreedy
  C-leaf4    C-bpg with turn-network vnet-2, leaf=4, k_turn=8 (flop subtrees end at turn starts)
Output bb/100 with 95% interval per variant and stack. Start independently (bench_humanopp3.cmd)."""
import sys
import time
from concurrent.futures import ProcessPoolExecutor

C = "hus?bp=lynx-4-300&auto=1&iters=60&iters_river=150&threads=1&vnet=vnet-river-1&opp=human-1@1&oppfold=human-fold-1"
VARIANTS = {
    "netz-g": "nn?run=lynx-4@300&greedy=1",
    "lynx5t-g": "nn?run=lynx-5t@1&greedy=1",
    "C": C,
    "C-bpg": C + "&bpgreedy=1",
    "C-bpg-g": C + "&bpgreedy=1&greedy=1",
    "C-5t-bpg": C.replace("bp=lynx-4-300", "bp=run:lynx-5t@1") + "&bpgreedy=1",
    "C-leaf4": C.replace("vnet=vnet-river-1", "vnet=vnet-2&leaf=4&k_turn=8") + "&bpgreedy=1",
}
STACKS = (40, 100)
BLOCKS = 40         # Seed blocks per (variant, stack)
HANDS = 60          # Blocks per seed (duplicate -> 120 hands)


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
    # Order: block-wise across all variants to make intermediate results comparable
    jobs = [(n, s, st, b) for b in range(BLOCKS) for st in STACKS for n, s in VARIANTS.items()]
    print(f"=== Search greedy/turn-network against human bot human-1+Fold: {len(jobs)} matches x {2 * HANDS} hands ===",
          time.strftime("%H:%M"), flush=True)
    acc = {}
    with ProcessPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as ex:
        for k, (name, stack, block, bb100, hands, secs) in enumerate(ex.map(task, jobs)):
            acc.setdefault((name, stack), []).append(bb100)
            print(f"  {name:9} {stack:3d} BB Block {block:2d}: {bb100:+7.1f} bb/100 ({hands} hands, {secs:.0f}s)", flush=True)
            if (k + 1) % (len(VARIANTS) * len(STACKS) * 5) == 0:
                print(f"--- Intermediate result after block {block} ---", time.strftime("%H:%M"), flush=True)
                for (n2, s2), xs in sorted(acc.items()):
                    m = sum(xs) / len(xs)
                    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / max(len(xs) - 1, 1))
                    half = 2.0 * sd / math.sqrt(len(xs))
                    print(f"  {n2:9} {s2:3d} BB: {m:+7.1f} [{m - half:+.1f}; {m + half:+.1f}] ({len(xs) * 2 * HANDS} hands)", flush=True)
    print('=== RESULT (mean of blocks, 95% interval over blocks) ===', time.strftime("%H:%M"), flush=True)
    for (name, stack), xs in sorted(acc.items()):
        m = sum(xs) / len(xs)
        sd = math.sqrt(sum((x - m) ** 2 for x in xs) / max(len(xs) - 1, 1))
        half = 2.02 * sd / math.sqrt(len(xs)) if len(xs) > 1 else float("nan")
        print(f"  {name:9} {stack:3d} BB: {m:+7.1f} bb/100 [{m - half:+.1f}; {m + half:+.1f}] over {len(xs) * 2 * HANDS} hands", flush=True)
    print('ALL MEASUREMENTS COMPLETE', time.strftime("%H:%M"), flush=True)
