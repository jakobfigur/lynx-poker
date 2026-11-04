"""Real humans as benchmark: player types from HandHQ (PHH dataset, 21.6 million online hands 2009).

Cards are only known there if shown at showdown ('????' otherwise). Mimicking as with
Pluribus is therefore not possible - but measuring HOW humans play: per player (fixed, anonymized ID)
frequencies like a HUD, over thousands of hands. From that:
  1. Distribution of real player types (tight/loose, passive/aggressive, ...).
  2. 'Human bots': style bots whose frequencies match a type (fit_style).
  3. Training and test bench against this mixture instead of only own bots.

Only public data is counted. Hands with antes or straddles are skipped (our engine knows neither).
Statistics per player:
  hands, vpip, pfr, threebet (3-bet rate when exactly one raise came before), f3b (fold to 3-bet after
  own open), agg (bets/raises after flop / all bets, raises, calls after flop), ftb (fold to bet after flop), cbet (flop bet as preflop aggressor, when first to bet),
  wtsd (went to showdown if flop seen), wsd (won showdown), bb100 (win in big blinds per 100 hands)
"""

from __future__ import annotations

import json
import math
import tomllib
from collections import defaultdict
from pathlib import Path

import numpy as np

HUMANS_VERSION = "humans-1"
STAT_KEYS = ("vpip", "pfr", "threebet", "f3b", "agg", "ftb", "cbet", "wtsd", "wsd")


def handhq_dir() -> Path:
    from .nn_agent import rl_root
    return rl_root().parent / "external" / "phh-dataset" / "data" / "handhq"


def iter_hands(path: Path):
    """All hands of a .phhs file (TOML, sections [1], [2], ...)."""
    try:
        doc = tomllib.loads(path.read_text("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return
    for k in sorted(doc, key=lambda x: int(x) if x.isdigit() else 0):
        if isinstance(doc[k], dict):
            yield doc[k]


def _counter() -> dict:
    return defaultdict(int)


class HumanStats:
    def __init__(self):
        self.c: dict[str, dict] = defaultdict(_counter)
        self.skipped = 0
        self.used = 0

    @staticmethod
    def _winnings(live: list[int], put: list[float], shown: dict[int, list[str]], board: list[str],
                  mucked: set[int]) -> list[float]:
        """Gross winnings, if the file contains none: everyone else folded -> last player wins;
        otherwise among the revealed the best (ties split). Side pots simplified: each
        winner gets from each player at most as much as he invested."""
        n = len(put)
        win = [0.0] * n
        cands = [s for s in live if s not in mucked]
        if len(cands) > 1:
            if len(board) < 5 or any(s not in shown for s in cands):
                cands = [s for s in cands if s in shown] or cands[:1]
            if len(cands) > 1:
                from ..fastpoker import evaluate_fast
                val = {s: evaluate_fast(shown[s] + board[:5]) for s in cands}
                top = max(val.values())
                cands = [s for s in cands if val[s] == top]
        if not cands:
            return win
        cap = max(put[s] for s in cands)
        pot = sum(min(p, cap) for p in put)
        for s in cands:
            win[s] = pot / len(cands)
        for i in range(n):                                   # unclaimed remainder is returned
            if put[i] > cap:
                win[i] += put[i] - cap
        return win

    def add_hand(self, h: dict):
        if h.get("variant") != "NT" or any(h.get("antes") or []):
            self.skipped += 1
            return
        bl = h.get("blinds_or_straddles") or []
        if len(bl) < 2 or any(bl[2:]) or not bl[1]:
            self.skipped += 1
            return
        bb = float(bl[1])
        players = h.get("players") or []
        n = len(players)
        if n < 2:
            self.skipped += 1
            return
        self.used += 1
        names = list(players)
        for p in names:
            self.c[p]["hands"] += 1
        win = h.get("winnings") or [0] * n
        starts = h.get("starting_stacks") or [0] * n
        # Net: winnings - own bets (summed from actions)
        put = [0.0] * n
        street = 0                      #0 preflop, 1 flop, 2 turn, 3 river
        level = bb
        contrib = [0.0] * n
        contrib[0], contrib[1] = float(bl[0]), bb
        raises_pre = 0
        opener = None
        opener_answered = False
        pre_aggr = None
        vp, pr = set(), set()
        saw_flop = set()
        flop_first_bet_done = False
        folded = set()
        shown_cards: dict[int, list[str]] = {}
        mucked: set[int] = set()
        board: list[str] = []
        for a in h.get("actions") or []:
            parts = a.split()
            if parts[0] == "d":
                if parts[1] == "db" and len(parts) > 2:
                    board += [parts[2][i:i + 2] for i in range(0, len(parts[2]), 2)]
                if parts[1] == "db":
                    put = [put[i] + contrib[i] for i in range(n)]
                    contrib = [0.0] * n
                    street += 1
                    level = 0.0
                    if street == 1:
                        saw_flop = {i for i in range(n) if i not in folded}
                continue
            if not parts[0].startswith("p"):
                continue
            s = int(parts[0][1:]) - 1
            if not 0 <= s < n:
                continue
            c = self.c[names[s]]
            act = parts[1]
            facing = level > contrib[s] + 1e-9
            if act == "sm":
                if len(parts) > 2 and "?" not in parts[2]:
                    shown_cards[s] = [parts[2][i:i + 2] for i in range(0, len(parts[2]), 2)]
                    mucked.discard(s)
                elif s not in shown_cards:
                    #'????' = mucked (lost, but made it to showdown). If all-in before the river is indicated
                    #'????' also appears in the middle of the action, the actual cards follow later - then those count.
                    mucked.add(s)
                continue
            if street == 0:
                if raises_pre == 1 and s != opener and act in ("cbr", "cc", "f"):
                    c["threebet_n"] += 1                  #Opportunity: exactly one raise before him
                    c["threebet"] += act == "cbr"
                if raises_pre >= 2 and s == opener and not opener_answered and act in ("cbr", "cc", "f"):
                    opener_answered = True                #Opener responds to the 3-bet
                    c["f3b_n"] += 1
                    c["f3b"] += act == "f"
                if act == "cbr":
                    vp.add(s)
                    pr.add(s)
                    if raises_pre == 0:
                        opener = s
                    raises_pre += 1
                    pre_aggr = s
                elif act == "cc" and facing:
                    vp.add(s)
            else:
                if act == "cbr":
                    c["aggr"] += 1
                elif act == "cc" and facing:
                    c["pas"] += 1
                if facing and act in ("f", "cc", "cbr"):
                    c["ftb_n"] += 1
                    c["ftb"] += act == "f"
                if street == 1 and not flop_first_bet_done and s == pre_aggr and not facing:
                    c["cbet_n"] += 1
                    c["cbet"] += act == "cbr"
                if street == 1 and act == "cbr":
                    flop_first_bet_done = True
            if act == "f":
                folded.add(s)
            elif act == "cbr" and len(parts) > 2:
                amt = float(parts[2])
                contrib[s] = amt
                level = max(level, amt)
            elif act == "cc":
                contrib[s] = min(level, starts[s] - put[s]) if starts else level
        put = [put[i] + contrib[i] for i in range(n)]
        put_total = list(put)
        top = max(range(n), key=lambda i: put[i])
        second = max((put[i] for i in range(n) if i != top), default=0.0)
        if put[top] > second:
            put[top] = second                     #Uncalled bet returns
        live = [i for i in range(n) if i not in folded]
        if not any(float(x) for x in (h.get("winnings") or [])):   #missing or only zeros (e.g. uncontested)
            win = self._winnings(live, put, shown_cards, board, mucked)
        elif sum(float(x) for x in win) > sum(put) + 0.005:
            put = put_total                       #Winnings include the return flow (PartyPoker)
        for s in vp:
            self.c[names[s]]["vpip"] += 1
        for s in pr:
            self.c[names[s]]["pfr"] += 1
        for s in saw_flop:
            self.c[names[s]]["saw_flop"] += 1
        if len(live) >= 2:
            for s in live:
                if s in saw_flop:
                    self.c[names[s]]["wtsd"] += 1
                    self.c[names[s]]["wsd"] += win[s] > 0
        for i in range(n):
            self.c[names[i]]["net_bb_x100"] += int(round((float(win[i]) - put[i]) / bb * 100))

    def stats(self, min_hands: int = 0) -> dict[str, dict]:
        out = {}
        for p, c in self.c.items():
            n = c["hands"]
            if n < max(1, min_hands):
                continue

            def q(a, b):
                return c[a] / c[b] if c[b] else float("nan")

            out[p] = {"hands": n, "vpip": c["vpip"] / n, "pfr": c["pfr"] / n,
                      "threebet": q("threebet", "threebet_n"), "f3b": q("f3b", "f3b_n"),
                      "agg": c["aggr"] / (c["aggr"] + c["pas"]) if c["aggr"] + c["pas"] else float("nan"),
                      "ftb": q("ftb", "ftb_n"), "cbet": q("cbet", "cbet_n"),
                      "wtsd": q("wtsd", "saw_flop"), "wsd": q("wsd", "wtsd"),
                      "bb100": c["net_bb_x100"] / n}
        return out


def _collect_chunk(files: list[Path]) -> tuple[dict, int, int]:
    hs = HumanStats()
    for f in files:
        for h in iter_hands(f):
            hs.add_hand(h)
    return {p: dict(c) for p, c in hs.c.items()}, hs.used, hs.skipped


def collect(dirs: list[Path], max_files: int | None = None, progress=None, workers: int | None = None) -> HumanStats:
    """Evaluate all .phhs files, distributed across multiple processes (counters are then summed)."""
    from concurrent.futures import ProcessPoolExecutor, as_completed
    hs = HumanStats()
    files = [f for d in dirs for f in sorted(d.rglob("*.phhs"))]
    if max_files:
        files = files[:max_files]
    chunks = [files[i:i + 20] for i in range(0, len(files), 20)]
    done = 0
    with ProcessPoolExecutor(workers) as ex:
        for fut in as_completed([ex.submit(_collect_chunk, ch) for ch in chunks]):
            c, used, skipped = fut.result()
            for p, cnt in c.items():
                tgt = hs.c[p]
                for k, v in cnt.items():
                    tgt[k] += v
            hs.used += used
            hs.skipped += skipped
            done += 20
            if progress:
                progress(min(done, len(files)), len(files), hs)
    return hs


#---- Player Types ---------------------------------------------------------------

TYPE_FEATURES = ("vpip", "pfr", "agg", "ftb", "threebet", "cbet", "wtsd")


def player_types(stats: dict[str, dict], k: int = 6, min_hands: int = 300, seed: int = 0) -> list[dict]:
    """k-Means on the frequencies of players with enough hands -> types with proportion and means.
    Weighted by hands played (frequency of encountering the type at the table)."""
    names = [p for p, s in stats.items() if s["hands"] >= min_hands
             and all(not math.isnan(s[f]) for f in TYPE_FEATURES)]
    if len(names) < k:
        raise ValueError(f"only {len(names)} players with >= {min_hands} hands")
    X = np.array([[stats[p][f] for f in TYPE_FEATURES] for p in names])
    w = np.array([stats[p]["hands"] for p in names], float)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = (X - mu) / sd
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(8):                                    #multiple starts, best error wins
        C = Z[rng.choice(len(Z), k, replace=False, p=w / w.sum())]
        for _ in range(100):
            lab = ((Z[:, None, :] - C[None]) ** 2).sum(-1).argmin(1)
            newC = np.array([np.average(Z[lab == j], 0, w[lab == j]) if (lab == j).any() else C[j]
                             for j in range(k)])
            if np.allclose(newC, C):
                break
            C = newC
        err = float((w * ((Z - C[lab]) ** 2).sum(-1)).sum())
        if best is None or err < best[0]:
            best = (err, lab, C)
    _, lab, C = best
    types = []
    for j in range(k):
        m = lab == j
        if not m.any():
            continue
        mean = {f: float(np.average(X[m, i], weights=w[m])) for i, f in enumerate(TYPE_FEATURES)}
        bb100 = float(np.average([stats[p]["bb100"] for p in np.array(names)[m]], weights=w[m]))
        types.append({"share": float(w[m].sum() / w.sum()), "players": int(m.sum()), "mean": mean,
                      "bb100": round(bb100, 1)})
    return sorted(types, key=lambda t: -t["share"])


def type_name(m: dict) -> str:
    loose = m["vpip"] >= 0.32
    tight = m["vpip"] <= 0.20
    aggr = m["agg"] >= 0.5 and m["pfr"] >= 0.6 * m["vpip"]
    passive = m["agg"] < 0.38 or m["pfr"] < 0.4 * m["vpip"]
    if loose and passive:
        return 'Calling station (loose-passive)'
    if loose and aggr:
        return 'LAG/Maniac (loose-aggressive)'
    if tight and aggr:
        return 'TAG/Reg (tight-aggressive)'
    if tight:
        return 'Nit (very tight)'
    if passive:
        return 'passive recreational player'
    return "Durchschnitt"


def save(name: str, hs: HumanStats, types: list[dict]) -> Path:
    from .nn_agent import rl_root
    d = rl_root().parent / "humans"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.json"
    p.write_text(json.dumps({"version": HUMANS_VERSION, "hands_used": hs.used, "hands_skipped": hs.skipped,
                             "players": len(hs.c), "types": types,
                             "stats": hs.stats(min_hands=100)}, indent=1), "utf-8")
    return p
