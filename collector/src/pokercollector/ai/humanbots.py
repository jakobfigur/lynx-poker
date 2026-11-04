"""Mensch-Bots: Stilbots, deren Haeufigkeiten zu echten Spielertypen (humans.py, HandHQ) passen.

Messen: der Bot spielt 6er-Cash-Haende mit 100 BB (wie 25NL online) gegen eine feste Mischung; seine
Haende laufen durch DIESELBE Statistik wie die echten Haende (HumanStats, ueber das PHH-Format) - so sind
Bot- und Menschenwerte direkt vergleichbar.
Anpassen: Cross-Entropy-Methode ueber die 10 Stilparameter, Ziel = moeglichst kleiner gewichteter Abstand
der Haeufigkeiten zum Typ (VPIP, PFR, 3-Bet, Aggression, Fold auf Einsatz, C-Bet, Showdown-Quote).
"""

from __future__ import annotations

import json
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from .agents import make_agent
from .engine import play_hand
from .humans import HumanStats, type_name
from .optimize import RANDOM_SPACE

FIT_SPACE = {**RANDOM_SPACE, "bet_size": (0.3, 1.1), "respect": (0.0, 1.0), "sticky": (0.0, 1.0)}

HUMANBOTS_VERSION = "humanbots-1"
FIT_KEYS = {"vpip": 3.0, "pfr": 3.0, "threebet": 2.0, "agg": 1.0, "ftb": 1.5, "cbet": 2.0, "wtsd": 3.0}
MEASURE_TABLE = ["tag", "rock", "lag", "station", "tag"]          # feste Mitspieler beim Messen
STACK_BB = 100


def record_to_phh(rec) -> dict:
    """HandRecord der Engine -> PHH-artiges dict (p1 = Small Blind, wie in HandHQ)."""
    seats = [r.seat for r in rec.results if r.start_stack > 0]
    n_all = len(rec.results)
    order = sorted(seats, key=lambda s: (s - rec.sb_seat) % n_all) if rec.sb_seat is not None else seats
    pi = {s: i + 1 for i, s in enumerate(order)}
    acts = [f"d dh p{pi[s]} ????" for s in order]
    street = "preflop"
    board_shown = 0
    for a in rec.actions:
        if a.kind in ("post_sb", "post_bb"):
            continue
        if a.street != street:
            street = a.street
            k = {"flop": 3, "turn": 4, "river": 5}[street]
            acts.append("d db " + "".join(rec.board[board_shown:k]))
            board_shown = k
        p = f"p{pi[a.seat]}"
        if a.kind == "fold":
            acts.append(f"{p} f")
        elif a.kind in ("check", "call"):
            acts.append(f"{p} cc")
        else:
            acts.append(f"{p} cbr {a.amount_to}")
    if rec.went_to_showdown:
        while board_shown < min(5, len(rec.board)):             # All-in: Rest des Boards
            k = {0: 3, 3: 4, 4: 5}[board_shown]
            acts.append("d db " + "".join(rec.board[board_shown:k]))
            board_shown = k
        for s in order:
            r = rec.results[s]
            if r.showed:
                acts.append(f"p{pi[s]} sm {''.join(r.hole)}")
    res = {r.seat: r for r in rec.results}
    # Gewinne wie in HandHQ: ohne den zurueckgegebenen, nicht gecallten Einsatz
    put = {s: res[s].start_stack - res[s].end_stack + res[s].won for s in order}
    top = max(order, key=lambda s: put[s])
    second = max((put[s] for s in order if s != top), default=0)
    put[top] = min(put[top], second)
    winnings = [res[s].end_stack - res[s].start_stack + put[s] for s in order]
    return {"variant": "NT", "antes": [0] * len(order), "blinds_or_straddles": [rec.blinds[0], rec.blinds[1]]
            + [0] * (len(order) - 2), "starting_stacks": [res[s].start_stack for s in order], "actions": acts,
            "players": [rec.names[s] if rec.names and rec.names[s] else f"s{s}" for s in order],
            "winnings": winnings}


def measure(spec: str, hands: int = 600, seed: int = 0, table: list[str] | None = None) -> dict:
    """Haeufigkeiten des Bots `spec` ueber `hands` 6er-Cash-Haende (100 BB, Stacks jede Hand neu)."""
    table = table or MEASURE_TABLE
    agents = [make_agent(f"{spec}:target", 1)] + [make_agent(f"{s}:m{i}", 99) for i, s in enumerate(table)]
    n = len(agents)
    hs = HumanStats()
    rng = random.Random(seed)
    for k in range(hands):
        rot = k % n                                               # Bot sitzt reihum auf jedem Platz
        order = agents[rot:] + agents[:rot]
        rec = play_hand(order, [STACK_BB * 20] * n, rng.randrange(n), 10, 20, seed=seed * 100_003 + k,
                        hand_id=f"m{seed}-{k}", names=[a.name for a in order])
        hs.add_hand(record_to_phh(rec))
    return hs.stats().get("target", {})


def distance(st: dict, target: dict) -> float:
    d = 0.0
    for k, w in FIT_KEYS.items():
        a, b = st.get(k, float("nan")), target.get(k, float("nan"))
        if a == a and b == b:
            d += w * (a - b) ** 2
    return d


def spec_from(x: dict) -> str:
    x = dict(x)
    x["pfr"] = min(x["pfr"], x["vpip"])
    return "tag?" + "&".join(f"{k}={int(round(v)) if k == 'push_bb' else round(v, 3)}" for k, v in x.items())


def _eval(args):
    spec, target, hands, seed, table = args
    st = measure(spec, hands, seed, table)
    return distance(st, target), st


def fit_type(target: dict, generations: int = 10, population: int = 16, hands: int = 600, seed: int = 0,
             ex=None, progress=None, table: list[str] | None = None, start: dict | None = None) -> dict:
    """CEM ueber die Stilparameter (Grenzen FIT_SPACE), Start nahe der Zielwerte fuer vpip/pfr."""
    keys = list(FIT_SPACE)
    lo = np.array([FIT_SPACE[k][0] for k in keys])
    hi = np.array([FIT_SPACE[k][1] for k in keys])
    mu = (lo + hi) / 2
    mu[keys.index("vpip")] = target["vpip"]
    mu[keys.index("pfr")] = target["pfr"]
    mu[keys.index("push_bb")] = 0.0                     # Cash mit 100 BB: kein Push/Fold
    sd = (hi - lo) / 4
    if start:                                           # Runde 2: beim Ergebnis von Runde 1 weitermachen
        mu = np.array([start.get(k, m) for k, m in zip(keys, mu)])
        sd = (hi - lo) / 8
    rng = np.random.default_rng(seed)
    best = None
    for g in range(generations):
        xs = np.clip(rng.normal(mu, sd, (population, len(keys))), lo, hi)
        xs[:, keys.index("push_bb")] = 0.0
        specs = [spec_from(dict(zip(keys, x))) for x in xs]
        jobs = [(s, target, hands, seed * 1000 + g, table) for s in specs]   # gleiche Karten je Generation
        res = list(ex.map(_eval, jobs)) if ex else [_eval(j) for j in jobs]
        order = np.argsort([r[0] for r in res])
        elite = xs[order[: max(2, population // 4)]]
        mu, sd = elite.mean(0), elite.std(0) + (hi - lo) * 0.02
        d0, st0 = res[order[0]]
        if best is None or d0 < best["distance"]:
            best = {"spec": specs[order[0]], "distance": round(float(d0), 5), "stats": st0}
        if progress:
            progress(g + 1, generations, best)
    # Bestaetigung mit frischen Karten und mehr Haenden
    st = measure(best["spec"], hands * 3, seed + 777, table)
    best["stats_check"] = st
    best["distance_check"] = round(distance(st, target), 5)
    return best


def _params(spec: str) -> dict:
    return {k: float(v) for k, v in (p.split("=") for p in spec.partition("?")[2].split("&"))}


def fit_all(humans_file: Path, out_name: str, generations: int = 10, population: int = 16, hands: int = 600,
            workers: int | None = None, progress=None, rounds: int = 2) -> Path:
    """Runde 1 misst gegen die alten Stilbots; ab Runde 2 sitzen die Mensch-Bots der Vorrunde am Tisch
    (gezogen nach Anteil) - die Mitspieler beeinflussen z. B. die Showdown-Quote stark."""
    data = json.loads(humans_file.read_text("utf-8"))
    path = humans_file.parent / f"{out_name}.json"
    table, prev = None, {}
    with ProcessPoolExecutor(workers) as ex:
        for rnd in range(1, rounds + 1):
            out = {"version": HUMANBOTS_VERSION, "source": humans_file.name, "round": rnd, "table": table, "bots": []}
            for i, t in enumerate(data["types"]):
                name = f"mensch-{i + 1}"
                if progress:
                    progress(f"Runde {rnd}, {name}: {type_name(t['mean'])}, Anteil {t['share']:.1%}")
                best = fit_type(t["mean"], generations, population, hands, seed=i + 100 * rnd, ex=ex, table=table,
                                start=_params(prev[name]) if name in prev else None,
                                progress=(lambda g, n, b: progress(f"  Generation {g}/{n}: Abstand {b['distance']:.4f}"))
                                if progress else None)
                out["bots"].append({"name": name, "type": type_name(t["mean"]), "share": t["share"],
                                    "target": t["mean"], **best})
                path.write_text(json.dumps(out, indent=1), "utf-8")   # nach jedem Typ sichern
            prev = {b["name"]: b["spec"] for b in out["bots"]}
            rng = random.Random(rnd)
            table = [rng.choices([b["spec"] for b in out["bots"]], weights=[b["share"] for b in out["bots"]])[0]
                     for _ in range(5)]
    return path


def load_bots(name: str = "mensch-25nl") -> list[dict]:
    from .nn_agent import rl_root
    p = rl_root().parent / "humans" / f"{name}.json"
    return json.loads(p.read_text("utf-8"))["bots"] if p.exists() else []
