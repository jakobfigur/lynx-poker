"""One-time confirmation of two bots against human bots on FRESH tables and cards.

The test bench mensch480 is fixed and watched often - whoever ranks first there might be lucky with exactly
these cards. Therefore, before making decisions, compare once paired with new tables (own seed).
Rule: don’t repeat until it fits.
"""

from __future__ import annotations

import random
from concurrent.futures import ProcessPoolExecutor

from .bench import _chunk, _summary
from .humanbots import load_bots
from .tournament import POKERTH_DEFAULT


def human_tables(schemes: int, seed: str, bots_name: str = "mensch-25nl") -> list[tuple[int, list[str]]]:
    bots = load_bots(bots_name)
    rng = random.Random(f"confirm|{seed}")
    specs, w = [b["spec"] for b in bots], [b["share"] for b in bots]
    return [(rng.randrange(1 << 30), rng.choices(specs, weights=w, k=5)) for _ in range(schemes)]


def confirm_vs_humans(spec_a: str, spec_b: str, schemes: int = 600, seed: str = "1", workers: int | None = None) -> dict:
    mus = human_tables(schemes, seed)
    n_jobs = 24
    out = {}
    with ProcessPoolExecutor(workers) as ex:
        for key, spec in (("a", spec_a), ("b", spec_b)):
            parts = list(ex.map(_chunk, [(spec, mus[i::n_jobs], POKERTH_DEFAULT) for i in range(n_jobs)]))
            vals = [0.0] * len(mus)
            for i in range(n_jobs):
                for j, v in enumerate(parts[i]):
                    vals[i + n_jobs * j] = v
            out[key] = vals
    diff = _summary([x - y for x, y in zip(out["a"], out["b"])])
    return {"a": _summary(out["a"]), "b": _summary(out["b"]), "diff": diff, "schemes": schemes, "seed": seed,
            "passed": diff["ci95"][0] > 0}
