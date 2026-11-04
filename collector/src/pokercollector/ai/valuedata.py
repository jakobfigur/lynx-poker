"""Trainingsdaten fuer das Wertnetz der Suche (Meilenstein 3, Stufe 1b).

Eine Situation = oeffentlicher Zustand zu Beginn einer Strasse (Board, Pot, effektiver Stack, wer zuerst handelt)
plus die Ranges beider Spieler (je 1326 Gewichte). Ziel = kontrafaktische Werte je Kombination fuer beide Spieler
an der Wurzel, wie sie die exakte CFR+-Suche (husearch.solve) liefert, in Pot-Einheiten.

Reihenfolge wie bei DeepStack: zuerst der River (exakte Loesung, billig: ~100 Knoten), damit das River-Netz die
Blaetter des Turn-Baums bewerten kann; dann der Turn mit River-Netz-Blaettern, dann der Flop. Diese Datei kann
jede Strasse exakt loesen (Turn/Flop dann teuer: alle Folgekarten).

Ranges: synthetisch, aber boardbezogen - Gewicht als weiche Schwelle auf der Handstaerke (dicht/locker, gekappt
ohne Nuts, mit Gamma-Rauschen, Anteil gleichverteilt), damit das Netz auch Ranges weit ab vom Gleichgewicht
kennt (Robustheit gegen Modellfehler, vgl. ReBeL-Training mit zufaelligen Beliefs).

Format: .npz je Scherbe (board int8[n,5] (-1 = leer), pot_bb/stack_bb float32, oop int8, r0/r1 float16[n,1326],
v0/v1 float16[n,1326] in Pot-Einheiten, meta json). Alles ohne Bezug zu echten Haenden oder Personen.
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
# 'river-leaf' (30.10.): River-Situationen, wie sie an den BLAETTERN einer echten Turn-Suche entstehen. Eine
# Turn-Situation (synthetische Start-Ranges) wird voll geloest, an jedem River-Anfang des Baums werden die Ranges
# unter der Durchschnittsstrategie ausgelesen (duenn, polarisiert, mit Blockern) und dann exakt geloest. Grund:
# Tranche 1 hatte nur breite Ranges (>= 9 Bit Entropie); an Blaettern mit 50 Kombis lag der Netzfehler bei 0,23 Pot.
LEAF_TURN_ITERS = 60
LEAF_PER_TURN = 24
LEAF_MIN_MASS = 1e-6
# 'turn-leaf' (31.10., Stufe 2): Turn-Situationen, wie sie an den Turn-Anfaengen einer echten Flop-Suche entstehen.
# Flop-Zustand + synthetische Ranges, Flop-Baum mit gezogenen Turn-/Rivercards exakt loesen, Ranges an den
# Turn-Anfaengen auslesen, dann jeden Turn-Teilbaum mit dem River-Wertnetz als Blatt loesen (DeepStack-Rezept:
# das Turn-Netz lernt aus Loesungen, deren Blaetter das River-Netz liefert).
TL_FLOP_ITERS = 40
TL_K_TURN = 8
TL_K_RIVER = 4
TL_PER_FLOP = 12
_VNET = {}


def sample_ranges(rng: np.random.Generator, board: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Zwei boardbezogene Ranges (Summe 1). Mischung aus gleichverteilt, dicht/locker (weiche Staerkeschwelle),
    gekappt (ohne die staerksten Haende) und Rauschen."""
    s = board_strength(tuple(board))                    # Perzentil der Handstaerke, 0 fuer blockierte
    base = (~dead_mask(board)).astype(np.float64)
    out = []
    for _ in range(2):
        u = rng.random()
        if u < 0.2:
            r = np.ones(N_COMBOS)
        else:
            tau = rng.uniform(0.0, 0.85)                # Schwelle: 0 = alles, 0.85 = nur Spitze
            w = rng.uniform(0.04, 0.35)                 # Weichheit
            r = 1.0 / (1.0 + np.exp(-(s - tau) / w))
            if rng.random() < 0.3:                      # gekappte Range (hat die Nuts nicht, z. B. Caller)
                cap = rng.uniform(0.7, 0.97)
                r = r * np.where(s > cap, rng.uniform(0.0, 0.4), 1.0)
            if rng.random() < 0.5:                      # Rauschen: einzelne Haende mehr/weniger
                k = rng.uniform(1.5, 20.0)
                r = r * rng.gamma(k, 1.0 / k, N_COMBOS)
            r = r + rng.uniform(0.0, 0.02)              # kleiner Boden: keine Hand ganz ausgeschlossen
        r = r * base
        out.append(r / r.sum())
    return out[0], out[1]


def sample_state(rng: np.random.Generator, street: str) -> tuple[State, list[str], float, float]:
    """Zustand zu Strassenbeginn: Pot 2..80 BB, Stack/Pot 0.25..8 (logarithmisch gleichverteilt), beide Stacks
    gleich (heads-up zaehlt nur der effektive Stack), wer zuerst handelt zufaellig."""
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
    """River-Wertnetz je Prozess einmal laden (None = ohne Netz, exakt)."""
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
    """Eine Zeile: Situation zu Strassenbeginn (River exakt; Turn mit net = River-Wertnetz als Blatt)."""
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
    """River-Situationen aus einer echten Turn-Suche: Turn-Zustand + synthetische Start-Ranges, voller Turn-Baum
    (alle Rivercards) loesen, Ranges an den River-Anfaengen unter der Durchschnittsstrategie auslesen, bis zu
    max_per_turn davon (gewichtet mit der Erreichwahrscheinlichkeit) exakt loesen."""
    rng = np.random.default_rng(seed)
    st, board, _, _ = sample_state(rng, "turn")
    r0, r1 = sample_ranges(rng, board)
    tree, _, _, avg = solve(st, r0, r1, iters_turn, return_avg=True)
    roots = tree.river_roots or []
    if not roots:
        return []
    return _roots_rows(seed, tree, avg, r0, r1, roots, iters, max_per_turn, rng)


def _roots_rows(seed: int, tree, avg, r0, r1, roots, iters: int, max_rows: int, rng, net=None) -> list[dict]:
    """Ranges an den Strassenanfaengen roots unter der Durchschnittsstrategie auslesen und bis zu max_rows davon
    (gewichtet mit der Erreichwahrscheinlichkeit) loesen."""
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
    """Turn-Situationen aus einer echten Flop-Suche: Flop-Zustand + synthetische Start-Ranges, Flop-Baum mit
    TL_K_TURN Turn- und TL_K_RIVER Rivercards exakt loesen, Ranges an den Turn-Anfaengen auslesen, bis zu
    max_per_flop davon mit dem River-Wertnetz als Blatt loesen (Werte zu Turn-Beginn = Lernziel des Turn-Netzes)."""
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
    except Exception as e:          # eine kaputte Situation darf den Lauf nicht stoppen
        return {"seed": seed, "error": repr(e)[:200]}


def data_dir() -> Path:
    from .nn_agent import rl_root
    return rl_root().parent / "valuenet"


def generate(street: str, n: int, out: Path | str, seed: int = 0, iters: int | None = None, workers: int = 1,
             threads: int | None = None, progress=None, vnet: str | None = None) -> dict:
    """n Situationen loesen und als eine .npz-Scherbe schreiben. Seeds seed..seed+n-1 (reproduzierbar).
    vnet: River-Wertnetz als Blatt fuer turn/flop/turn-leaf (Pflicht bei turn-leaf, Standard vnet-river-1)."""
    iters = iters or ITERS_DEFAULT[street]
    if street == "turn-leaf" and not vnet:
        vnet = "vnet-river-1"
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    jobs = [(seed + i, street, iters, threads, vnet) for i in range(n)]
    rows, errors = [], []
    t0 = time.time()

    def take(r):
        if isinstance(r, list):                 # river-leaf/turn-leaf: mehrere Zeilen je Seed
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
        raise RuntimeError(f"keine Situation geloest: {errors[:3]}")
    stack = lambda key, dt: np.stack([r[key] for r in rows]).astype(dt)
    meta = {"version": VALUEDATA_VERSION, "street": street, "iters": iters, "n": len(rows), "errors": len(errors),
            "vnet": vnet,
            "seed": seed, "bb": BB, "secs_per_sample": float(np.mean([r["secs"] for r in rows])),
            "nodes_mean": float(np.mean([r["nodes"] for r in rows])), "t": time.strftime("%Y-%m-%d %H:%M:%S")}
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
