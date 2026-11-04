"""Self-improvement, step 1: optimization of style parameters of a bot.

Method: Cross-Entropy Method (CEM). Each generation draws candidates from a
normal distribution over (normalized to 0..1) parameters, evaluated via Duplicate Sit&Go
against a fixed opponent pool (all candidates of one generation with the same
cards = fair comparisons), the best 25% shift the distribution.

Then acceptance test (`gate`): candidate and reigning champion play on FRESH
card layouts (not seen during training) against the pool; matched pairwise
on each layout. Adopted only if difference is reliably positive (95% confidence interval > 0).

Opponents: either a fixed pool (all layouts against the same 5 bots) or the league
(`LeaguePool`): for each card layout a separate table of active league players is drawn,
stronger ones more often (prioritized self-play like AlphaStar), occasionally
include the current state of training. This counters overfitting on few
fixed opponents that was noticeable in the first run (opt-1).

Limit: Whether this transfers well against humans or real PokerTH bots will be shown only in real games.
"""

from __future__ import annotations

import json
import math
import random
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from .agents import STYLES, make_agent
from .evaluate import t95
from .tournament import BlindSchedule, TournamentConfig, play_tournament

OPT_VERSION = "cem-1"

# Parameters: (min, max, integer)
SPACE = {
    "vpip": (0.08, 0.60, False),
    "pfr": (0.03, 0.45, False),
    "value_margin": (0.0, 0.35, False),
    "raise_margin": (0.05, 0.50, False),
    "call_slack": (-0.10, 0.20, False),
    "bluff": (0.0, 0.50, False),
    "bet_size": (0.3, 1.2, False),
    "open_size": (2.0, 4.0, False),
    "push_bb": (0.0, 20.0, True),
    "nash_stack_factor": (0.5, 1.8, False),
}
DEFAULT_POOL = ["rock", "tag", "lag", "station", "maniac"]
DEFAULT_CONFIG = TournamentConfig(start_stack=3000, blinds=BlindSchedule(10, 20, 10))


def params_from_style(name: str) -> dict:
    st = STYLES[name]
    return {k: getattr(st, k) for k in SPACE}


def spec_from_params(params: dict, base: str = "tag") -> str:
    parts = []
    for k, (lo, hi, integer) in SPACE.items():
        v = min(hi, max(lo, params[k]))
        parts.append(f"{k}={int(round(v)) if integer else round(v, 3)}")
    return f"{base}?" + "&".join(parts)


def _norm(params: dict) -> np.ndarray:
    return np.array([(params[k] - lo) / (hi - lo) for k, (lo, hi, _) in SPACE.items()])


def _denorm(x: np.ndarray) -> dict:
    out = {}
    for v, (k, (lo, hi, integer)) in zip(np.clip(x, 0, 1), SPACE.items()):
        val = lo + v * (hi - lo)
        out[k] = int(round(val)) if integer else round(float(val), 3)
    return out


# Random opponents: deliberately wider than SPACE, from calling station to constant bluffer
RANDOM_SPACE = {
    "vpip": (0.05, 0.90), "pfr": (0.0, 0.60), "value_margin": (-0.05, 0.40), "raise_margin": (0.0, 0.60),
    "call_slack": (-0.15, 0.35), "bluff": (0.0, 0.70), "bet_size": (0.25, 2.0), "open_size": (2.0, 6.0),
    "push_bb": (0.0, 25.0), "nash_stack_factor": (0.4, 2.0),
}


def random_style_spec(rng: random.Random) -> str:
    """A style bot with rolled values. Same RNG state -> same bot (Duplicate-fair)."""
    p = {k: rng.uniform(lo, hi) for k, (lo, hi) in RANDOM_SPACE.items()}
    p["pfr"] = min(p["pfr"], p["vpip"])
    parts = [f"{k}={int(round(v)) if k == 'push_bb' else round(v, 3)}" for k, v in p.items()]
    return "tag?" + "&".join(parts)


class LeaguePool:
    """Opponent selection from the league. players: [(name, spec, mu)], bots only.
    Weight exp((mu - mu_max) / temperature), at least `floor`: stronger opponents appear more often,
    weak ones never disappear completely (else bot forgets how to exploit them).
    random_share: fraction of seats occupied by random style bots.
    add(): add more opponents, e.g. exploiters from training, weighted like the strongest league player."""

    def __init__(self, players: list[tuple[str, str, float]], table: int = 5, temperature: float = 15.0,
                 floor: float = 0.1, self_play: float = 0.2, random_share: float = 0.0):
        if len(players) < table:
            raise ValueError(f"League has only {len(players)} bots, a table needs {table} opponents")
        self.players = list(players)
        self.table = table
        self.self_play = self_play
        self.random_share = random_share
        self.human_share = 0.0
        self.human_bots: list[tuple[str, float]] = []     # (spec, share) from humanbots.load_bots
        top = max(mu for _, _, mu in players)
        self.weights = [max(floor, math.exp((mu - top) / temperature)) for _, _, mu in players]

    def add(self, name: str, spec: str, weight: float = 1.0):
        self.players.append((name, spec, float("nan")))
        self.weights.append(weight)

    def shares(self) -> dict[str, float]:
        tot = sum(self.weights)
        return {n: w / tot for (n, _, _), w in zip(self.players, self.weights)}

    def sample(self, rng: random.Random, self_spec: str | None = None, size: int | None = None) -> list[str]:
        """A table of `size` (default: table) opponents, weighted and without replacement as long as enough
        different available; then with replacement (e.g. 10-seat table in small league)."""
        idx, w = list(range(len(self.players))), list(self.weights)
        chosen = []
        for _ in range(size or self.table):
            if not idx:
                idx, w = list(range(len(self.players))), list(self.weights)
            k = rng.choices(range(len(idx)), weights=w)[0]
            chosen.append(self.players[idx.pop(k)][1])
            w.pop(k)
        if self.random_share:
            chosen = [random_style_spec(rng) if rng.random() < self.random_share else s for s in chosen]
        if self.human_share and self.human_bots:
            specs, w = zip(*self.human_bots)
            chosen = [rng.choices(specs, weights=w)[0] if rng.random() < self.human_share else s for s in chosen]
        if self_spec and rng.random() < self.self_play:
            chosen[rng.randrange(len(chosen))] = self_spec
        return chosen


def matchup_payouts(spec: str, matchups: list[tuple[int, list[str]]], config: TournamentConfig) -> list[float]:
    """Net payout (buy-ins, averaged over seat rotations) of the candidate per (layout, opponent table)."""
    out = []
    for sd, pool in matchups:
        n = len(pool) + 1
        total = 0.0
        for r in range(n):
            order = [(i + r) % n for i in range(n)]
            agents = [make_agent(f"{spec}:cand", 1) if a == 0 else make_agent(f"{pool[a - 1]}:pool-{a}", 99)
                      for a in order]
            res = play_tournament(agents, config, seed=sd)
            total += res.payouts[order.index(0)] - 1.0
        out.append(total / n)
    return out


def scheme_payouts(spec: str, pool: list[str], schemes: list[int], config: TournamentConfig) -> list[float]:
    """Like matchup_payouts, all layouts against the same fixed pool."""
    return matchup_payouts(spec, [(sd, pool) for sd in schemes], config)


def _eval_job(args):
    spec, matchups, config = args
    return matchup_payouts(spec, matchups, config)


def _matchups(schemes: list[int], pool, rng_seed: int, self_spec: str | None = None):
    if isinstance(pool, LeaguePool):
        rng = random.Random(rng_seed)
        return [(sd, pool.sample(rng, self_spec)) for sd in schemes]
    return [(sd, list(pool)) for sd in schemes]


def pool_desc(pool):
    if isinstance(pool, LeaguePool):
        return {"league": {k: round(v, 3) for k, v in pool.shares().items()}, "table": pool.table,
                "self_play": pool.self_play}
    return list(pool)


def run_cem(generations: int = 8, population: int = 12, schemes_per_gen: int = 12, start: str = "tag",
            pool: list[str] | LeaguePool | None = None, config: TournamentConfig = DEFAULT_CONFIG, seed: int = 1,
            workers: int | None = None, out_dir: Path | None = None, progress=None, resume: bool = False) -> dict:
    pool = pool or DEFAULT_POOL
    mean = _norm(params_from_style(start))
    std = np.full(len(SPACE), 0.2)
    elite_n = max(2, population // 4)
    best = {"roi": -math.inf, "params": params_from_style(start), "spec": None, "generation": 0}
    log = []
    first_gen = 1
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        if resume and (out_dir / "log.jsonl").exists():
            for line in (out_dir / "log.jsonl").read_text("utf-8").splitlines():
                if line.strip():
                    try:
                        log.append(json.loads(line))
                    except json.JSONDecodeError:
                        break          # incomplete last line after abort
            resumable = [e for e in log if "state_mean" in e]
            if resumable:
                last = resumable[-1]
                mean, std = np.array(last["state_mean"]), np.array(last["state_std"])
                best = last.get("state_best", best)
                first_gen = last["generation"] + 1
                log = log[:log.index(last) + 1]
    # random per generation from (seed, generation): continuing yields the same sequence
    t0 = time.perf_counter()

    def write_log(entry):
        if not out_dir:
            return
        for attempt in range(5):
            try:
                with open(out_dir / "log.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
                return
            except OSError:
                time.sleep(2 * (attempt + 1))   # e.g. USB stick briefly removed
        print('WARNING: log could not be written (generation', entry["generation"], ')')

    with ProcessPoolExecutor(workers) as ex:
        for g in range(first_gen, generations + 1):
            rng = np.random.default_rng([seed, g])
            schemes = [int(seed * 100_003 + g * 1009 + i) for i in range(schemes_per_gen)]
            xs = [mean] + [mean + std * rng.standard_normal(len(SPACE)) for _ in range(population - 1)]
            cands = [_denorm(x) for x in xs]
            specs = [spec_from_params(c) for c in cands]
            # all candidates of one generation: same cards AND same opponent tables
            mus = _matchups(schemes, pool, seed * 7919 + g, self_spec=specs[0])
            results = list(ex.map(_eval_job, [(s, mus, config) for s in specs]))
            rois = [100 * sum(r) / len(r) for r in results]
            order = np.argsort(rois)[::-1]
            elite = np.array([_norm(cands[i]) for i in order[:elite_n]])
            mean = 0.7 * elite.mean(axis=0) + 0.3 * mean
            std = np.maximum(0.7 * elite.std(axis=0) + 0.3 * std, 0.03)
            top = order[0]
            entry = {"generation": g, "best_roi": round(rois[top], 1), "mean_roi": round(float(np.mean(rois)), 1),
                     "center_roi": round(rois[0], 1), "best_params": cands[top], "best_spec": specs[top],
                     "std_mean": round(float(std.mean()), 3), "elapsed_s": round(time.perf_counter() - t0, 1)}
            if isinstance(pool, LeaguePool):
                entry["tables"] = [m[1] for m in mus]
            # "Best" = center of distribution of last generation is more robust than a single hit;
            # we remember both and decide later via acceptance test.
            if rois[top] > best["roi"]:
                best = {"roi": rois[top], "params": cands[top], "spec": specs[top], "generation": g}
            entry.update({"state_mean": [round(float(x), 6) for x in mean],
                          "state_std": [round(float(x), 6) for x in std], "state_best": best})
            log.append(entry)
            write_log(entry)
            if progress:
                progress(entry)
    center = _denorm(mean)
    return {"version": OPT_VERSION, "start": start, "pool": pool_desc(pool), "generations": log,
            "best_single": best, "center": {"params": center, "spec": spec_from_params(center)},
            "elapsed_s": round(time.perf_counter() - t0, 1)}


def gate(candidate_spec: str, champion_spec: str, schemes: int = 40, seed: int = 777,
         pool: list[str] | LeaguePool | None = None, config: TournamentConfig = DEFAULT_CONFIG,
         workers: int | None = None) -> dict:
    """Paired comparison on fresh card layouts (in LeaguePool also freshly drawn tables,
    no self-play). Gives ROI of both and difference with interval."""
    pool = pool or DEFAULT_POOL
    sch = [int(seed * 7_000_003 + i) for i in range(schemes)]
    mus = _matchups(sch, pool, seed)
    chunks = [mus[i::8] for i in range(8)]
    with ProcessPoolExecutor(workers) as ex:
        ca = list(ex.map(_eval_job, [(candidate_spec, c, config) for c in chunks]))
        cb = list(ex.map(_eval_job, [(champion_spec, c, config) for c in chunks]))
    a = [x for part in ca for x in part]
    b = [x for part in cb for x in part]
    d = [x - y for x, y in zip(a, b)]
    n = len(d)
    md = sum(d) / n
    sd = math.sqrt(sum((x - md) ** 2 for x in d) / (n - 1)) if n > 1 else float("nan")
    half = t95(n) * sd / math.sqrt(n) * 100
    return {"schemes": n, "pool": pool_desc(pool), "candidate_roi": round(100 * sum(a) / n, 1), "champion_roi": round(100 * sum(b) / n, 1),
            "diff_roi": round(100 * md, 1), "ci95": [round(100 * md - half, 1), round(100 * md + half, 1)],
            "passed": 100 * md - half > 0}
