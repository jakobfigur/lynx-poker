"""Oct 31: Does the human model (human-1 + fold model human-fold-1) help the search AGAINST THE HUMAN BOT itself?
Heads-up cash duplicate, multiple stack depths, three variants of the search against nn?run=human-1@1:
  A  Standard ranges (auto=1, vnet)                      -> opponent "plays like our network"
  B  + opp=human-1@1                                     -> opponent actions evaluated with the human network (without folds)
  C  + opp=human-1@1 & oppfold=human-fold-1              -> plus continue-play factor per hand (Bayes remainder)
Also lynx-4@300 network alone as reference. Output bb/100 with 95% interval per variant and stack.
Start independently; ProcessPool over (variant, stack, seed-block)."""
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
BLOCKS = 4          # Seed blocks per (variant, stack)
HANDS = 60          # Blocks per seed (duplicate -> 120 hands)


def task(args):
    name, spec, stack, block = args
    from pokercollector.ai.agents import make_agent
    from pokercollector.ai.evaluate import run_match
    a = make_agent(f"{spec}:kand", 100 + block)
    b = make_agent("nn?run=human-1@1:mensch", 200 + block)
    res = run_match([a, b], HANDS, seed=5000 + 97 * block + stack, small_blind=50, big_blind=100, stack_bb=stack)
    r = {x["agent"]: x for x in res["results"]}["kand"]
    return name, stack, block, r["bb_per_100"], r["hands"], res["elapsed_s"]


if __name__ == "__main__":
    import math
    jobs = [(n, s, st, b) for n, s in VARIANTS.items() for st in STACKS for b in range(BLOCKS)]
    print(f"=== Search against human bot human-1: {len(jobs)} matches x {2 * HANDS} hands ===", time.strftime("%H:%M"), flush=True)
    acc = {}
    with ProcessPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as ex:
        for name, stack, block, bb100, hands, secs in ex.map(task, jobs):
            acc.setdefault((name, stack), []).append(bb100)
            print(f"  {name:13} {stack:3d} BB Block {block}: {bb100:+7.1f} bb/100 ({hands} hands, {secs:.0f}s)", flush=True)
    print('=== RESULT (mean of blocks, 95% interval over blocks) ===', time.strftime("%H:%M"), flush=True)
    for (name, stack), xs in sorted(acc.items()):
        m = sum(xs) / len(xs)
        sd = math.sqrt(sum((x - m) ** 2 for x in xs) / max(len(xs) - 1, 1))
        half = 2.78 * sd / math.sqrt(len(xs)) if len(xs) > 1 else float("nan")      # t(3) for 4 blocks
        print(f"  {name:13} {stack:3d} BB: {m:+7.1f} bb/100 [{m - half:+.1f}; {m + half:+.1f}] over {len(xs) * 2 * HANDS} hands", flush=True)
    print('ALL MEASUREMENTS COMPLETE', time.strftime("%H:%M"), flush=True)
