"""Training data for the value network of the search (Milestone 3, level 1b).

A situation = public state at the start of a street (board, pot, effective stack, to act first)
plus the ranges of both players (each 1326 weights). Target = counterfactual values per combo for both players
at the root, as exact CFR+ search (husearch.solve) delivers them, in pot units.

Order as in DeepStack: first the River (exact solution, cheap: ~100 nodes), so the river net can evaluate
turn tree leaves; then the Turn with river leaves, then the Flop. This file can solve each street exactly (Turn/Flop expensive then: all following cards).

Ranges: synthetic, but board-dependent - weight as soft threshold on hand strength (tight/loose, capped
without nuts, with gamma noise, evenly distributed portion), so the net also knows ranges far from equilibrium
(robustness against model errors, cf. ReBeL training with random beliefs).

Format: .npz per shard (board int8[n,5] (-1 = empty), pot_bb/stack_bb float32, oop int8, r0/r1 float16[n,1326],
v0/v1 float16[n,1326] in pot units, meta json). All without relation to real hands or persons.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from ..poker import FULL_DECK
from .husearch import N_COMBOS, State, solve
from .ranges import board_strength, dead_mask

VALUEDATA_VERSION = "vdata-1"
BB = 100
STREET_CARDS = {"flop": 3, "turn": 4, "river": 5}
ITERS_DEFAULT = {"flop": 60, "turn": 150, "river": 300, "river-leaf": 300, "turn-leaf": 150}
# 'river-leaf' (30.10.): River situations as they occur at the LEAVES of a genuine Turn search. A
# Turn situation (synthetic start ranges) is fully solved, at each river root of the tree the ranges
# are read out under the average strategy (thin, polarized, with blockers) and then solved exactly. Reason:
# Tranche 1 had only broad ranges (>= 9 bit entropy); at leaves with 50 combos network error was 0.23 pot.
LEAF_TURN_ITERS = 60
LEAF_PER_TURN = 24
LEAF_MIN_MASS = 1e-6
# 'turn-leaf' (31.10., level 2): Turn situations as they occur at the turn starts of a real flop search.
# Flop state + synthetic ranges, solve flop tree with drawn turn/river cards exactly, read ranges at the
# turn roots, then solve each turn subtree with the river value network as leaves (DeepStack recipe:
# the turn net learns from solutions whose leaves the river net provides).
TL_FLOP_ITERS = 40
TL_K_TURN = 8
TL_K_RIVER = 4
TL_PER_FLOP = 12
_VNET = {}


def sample_ranges(rng: np.random.Generator, board: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Two board-dependent ranges (sum 1). Mix of uniform, tight/loose (soft strength threshold),
    capped (without strongest hands) and noise."""
    s = board_strength(tuple(board))                    # Percentile of hand strength, 0 for blocked
    base = (~dead_mask(board)).astype(np.float64)
    out = []
    for _ in range(2):
        u = rng.random()
        if u < 0.2:
            r = np.ones(N_COMBOS)
        else:
            tau = rng.uniform(0.0, 0.85)                # Threshold: 0 = all, 0.85 = only top
            w = rng.uniform(0.04, 0.35)                 # Softness
            r = 1.0 / (1.0 + np.exp(-(s - tau) / w))
            if rng.random() < 0.3:                      # Capped range (does not include nuts, e.g. caller)
                cap = rng.uniform(0.7, 0.97)
                r = r * np.where(s > cap, rng.uniform(0.0, 0.4), 1.0)
            if rng.random() < 0.5:                      # Noise: individual hands more/less
                k = rng.uniform(1.5, 20.0)
                r = r * rng.gamma(k, 1.0 / k, N_COMBOS)
            r = r + rng.uniform(0.0, 0.02)              # Small floor: no hand entirely excluded
        r = r * base
        out.append(r / r.sum())
    return out[0], out[1]


def sample_state(rng: np.random.Generator, street: str) -> tuple[State, list[str], float, float]:
    """State at street start: pot 2..80 BB, stack/pot 0.25..8 (log-uniform), both stacks
    equal (heads-up counts effective stack only), to act first randomly."""
    n = STREET_CARDS[street]
    idx = sorted(int(x) for x in rng.choice(52, n, replace=False))
    board = [FULL_DECK[i] for i in idx]
    pot_bb = float(np.exp(rng.uniform(np.log(2.0), np.log(80.0))))
    spr = float(np.exp(rng.uniform(np.log(0.25), np.log(8.0))))
    pot = max(2 * BB, int(round(pot_bb * BB / 2)) * 2)
    stack = max(BB, int(round(spr * pot)))
    oop = int(rng.integers(0, 2))
    st = State(board=tuple(idx), committed=(pot // 2, pot - pot // 2), bets=(0, 0), stacks=(stack, stack),
               to_act=oop, last_inc=BB, raises=0, acted=(False, False), oop=oop, bb=BB)
    return st, board, pot / BB, stack / BB


def get_vnet(name: str | None):
    """Load River value network once per process (None = no net, exact)."""
    if not name:
        return None
    if name not in _VNET:
        from .husearch import load_valuenet
        _VNET[name] = load_valuenet(name)
    return _VNET[name]


def solve_sample(seed: int, street: str, iters: int, vnet: str | None = None) -> dict:
    rng = np.random.default_rng(seed)
    st, board, pot_bb, stack_bb = sample_state(rng, street)
    r0, r1 = sample_ranges(rng, board)
    t = time.time()
    net = get_vnet(vnet) if street != "river" else None
    tree, _, v = solve(st, r0, r1, iters, valuenet=net, leaf_street=5 if net is not None else None)
    pot = sum(st.committed)
    b = np.full(5, -1, np.int8)
    b[:len(st.board)] = st.board
    return {"seed": seed, "board": b, "pot_bb": np.float32(pot_bb), "stack_bb": np.float32(stack_bb),
            "oop": np.int8(st.oop), "r0": r0.astype(np.float16), "r1": r1.astype(np.float16),
            "v0": (v[0] / pot).astype(np.float16), "v1": (v[1] / pot).astype(np.float16),
            "nodes": len(tree.kind), "secs": time.time() - t}


def _river_row(seed: int, sub: int, board: tuple[int, ...], pot: int, stack: int, oop: int,
               r0: np.ndarray, r1: np.ndarray, iters: int, net=None) -> dict:
    """One line: situation at street start (River exact; Turn with net = River value net as leaf)."""
    st = State(board=board, committed=(pot // 2, pot - pot // 2), bets=(0, 0), stacks=(stack, stack),
               to_act=oop, last_inc=BB, raises=0, acted=(False, False), oop=oop, bb=BB)
    t = time.time()
    tree, _, v = solve(st, r0, r1, iters, valuenet=net, leaf_street=5 if net is not None else None)
    b = np.full(5, -1, np.int8)
    b[:len(board)] = board
    return {"seed": seed, "sub": sub, "board": b, "pot_bb": np.float32(pot / BB), "stack_bb": np.float32(stack / BB),
            "oop": np.int8(oop), "r0": r0.astype(np.float16), "r1": r1.astype(np.float16),
            "v0": (v[0] / pot).astype(np.float16), "v1": (v[1] / pot).astype(np.float16),
            "nodes": len(tree.kind), "secs": time.time() - t}


def solve_leaf_samples(seed: int, iters: int = 300, iters_turn: int = LEAF_TURN_ITERS,
                       max_per_turn: int = LEAF_PER_TURN) -> list[dict]:
    """River situations from a real Turn search: Turn state + synthetic start ranges, full turn tree
    (all river cards) solved, ranges at river roots under the average strategy read out, up to
    max_per_turn of those (weighted by reach probability) solved exactly."""
    rng = np.random.default_rng(seed)
    st, board, _, _ = sample_state(rng, "turn")
    r0, r1 = sample_ranges(rng, board)
    tree, _, _, avg = solve(st, r0, r1, iters_turn, return_avg=True)
    roots = tree.river_roots or []
    if not roots:
        return []
    return _roots_rows(seed, tree, avg, r0, r1, roots, iters, max_per_turn, rng)


def _roots_rows(seed: int, tree, avg, r0, r1, roots, iters: int, max_rows: int, rng, net=None) -> list[dict]:
    """Ranges at street starts roots read under the average strategy and up to max_rows of these
    (weighted by reach prob) solved."""
    from .husearch import average_reaches
    R0, R1 = average_reaches(tree, avg, r0, r1)
    mass = np.array([R0[n].sum() * R1[n].sum() for n, _ in roots])
    ok = np.nonzero(mass > LEAF_MIN_MASS)[0]
    if len(ok) == 0:
        return []
    k = min(max_rows, len(ok))
    pick = rng.choice(ok, size=k, replace=False, p=mass[ok] / mass[ok].sum())
    rows = []
    for sub, i in enumerate(sorted(int(x) for x in pick)):
        node, rs = roots[i]
        live = ~dead_mask([FULL_DECK[c] for c in rs.board])
        a, b = R0[node] * live, R1[node] * live
        if a.sum() <= 0 or b.sum() <= 0 or min(rs.stacks) <= 0:
            continue
        rows.append(_river_row(seed, sub, tuple(rs.board), int(sum(rs.committed)), int(min(rs.stacks)), rs.oop,
                               a / a.sum(), b / b.sum(), iters, net))
    return rows


def solve_turn_leaf_samples(seed: int, iters: int = 150, vnet: str | None = "vnet-river-1",
                            iters_flop: int = TL_FLOP_ITERS, max_per_flop: int = TL_PER_FLOP) -> list[dict]:
    """Turn situations from a real flop search: Flop state + synthetic start ranges, flop tree with
    TL_K_TURN turn and TL_K_RIVER river cards solved exactly, ranges at turn roots read, up to
    max_per_flop solved with the river value net as leaf (values at turn start = learning target for turn net)."""
    rng = np.random.default_rng(seed)
    st, board, _, _ = sample_state(rng, "flop")
    r0, r1 = sample_ranges(rng, board)
    tree, _, _, avg = solve(st, r0, r1, iters_flop, k_turn=TL_K_TURN, k_river=TL_K_RIVER, seed=seed,
                            return_avg=True)
    roots = tree.turn_roots or []
    if not roots:
        return []
    return _roots_rows(seed, tree, avg, r0, r1, roots, iters, max_per_flop, rng, get_vnet(vnet))


def _worker(args):
    seed, street, iters, threads, vnet = args
    if threads:
        from .husearch import set_threads
        set_threads(threads)
    try:
        if street == "river-leaf":
            return solve_leaf_samples(seed, iters)
        if street == "turn-leaf":
            return solve_turn_leaf_samples(seed, iters, vnet)
        return solve_sample(seed, street, iters, vnet)
    except Exception as e:          #a broken situation must not stop the run
        return {"seed": seed, "error": repr(e)[:200]}


def data_dir() -> Path:
    from .nn_agent import rl_root
    return rl_root().parent / "valuenet"


def generate(street: str, n: int, out: Path | str, seed: int = 0, iters: int | None = None, workers: int = 1,
             threads: int | None = None, progress=None, vnet: str | None = None) -> dict:
    """Solve n situations and write as one .npz shard. Seeds seed..seed+n-1 (reproducible).
    vnet: River value net as leaves for turn/flop/turn-leaf (mandatory for turn-leaf, default vnet-river-1)."""
    iters = iters or ITERS_DEFAULT[street]
    if street == "turn-leaf" and not vnet:
        vnet = "vnet-river-1"
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    jobs = [(seed + i, street, iters, threads, vnet) for i in range(n)]
    rows, errors = [], []
    t0 = time.time()

    def take(r):
        if isinstance(r, list):                 # river-leaf/turn-leaf: multiple lines per seed
            rows.extend(r)
        else:
            (errors if "error" in r else rows).append(r)

    if workers > 1:
        with ProcessPoolExecutor(workers) as ex:
            it = ex.map(_worker, jobs, chunksize=1 if street.endswith("-leaf") else 4)
            for k, r in enumerate(it, 1):
                take(r)
                if progress and k % 50 == 0:
                    progress(k, n, time.time() - t0)
    else:
        for k, j in enumerate(jobs, 1):
            take(_worker(j))
            if progress and k % 50 == 0:
                progress(k, n, time.time() - t0)
    if not rows:
        raise RuntimeError(f"No situation solved: {errors[:3]}")
    stack = lambda key, dt: np.stack([r[key] for r in rows]).astype(dt)
    meta = {"version": VALUEDATA_VERSION, "street": street, "iters": iters, "n": len(rows), "errors": len(errors),
            "vnet": vnet,
            "seed": seed, "bb": BB, "secs_per_sample": float(np.mean([r["secs"] for r in rows])),
            "nodes_mean": float(np.mean([r["nodes"] for r in rows])), "t": time.strftime('%Y-%m-%d %H:%M:%S')}
    np.savez_compressed(out, board=stack("board", np.int8), pot_bb=stack("pot_bb", np.float32),
                        stack_bb=stack("stack_bb", np.float32), oop=stack("oop", np.int8),
                        r0=stack("r0", np.float16), r1=stack("r1", np.float16),
                        v0=stack("v0", np.float16), v1=stack("v1", np.float16),
                        seed=np.array([r["seed"] for r in rows], np.int64), meta=json.dumps(meta))
    meta["elapsed_s"] = time.time() - t0
    meta["path"] = str(out)
    return meta


def load(path: Path | str) -> dict:
    z = np.load(path, allow_pickle=False)
    d = {k: z[k] for k in z.files if k != "meta"}
    d["meta"] = json.loads(str(z["meta"]))
    return d
