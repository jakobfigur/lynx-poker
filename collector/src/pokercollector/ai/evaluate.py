"""Evaluation of agents over many hands.

Format: Cash game, each player starts every hand with `stack_bb` big blinds (hands
are independent, reducing variance). Button moves every hand.

Duplicate: Each deck is played N times; agents rotate through
all seats. Each agent thus gets the same cards as all others - luck largely cancels out.
Sample unit for error is a deck.

Result per agent: bb/100 with 95% confidence interval, plus playstyle statistics
(VPIP, PFR, Aggression, Showdown rate).
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .engine import ENGINE_VERSION, HandRecord, play_hand

EVAL_VERSION = "eval-1"

# 97.5% quantiles of the t-distribution (degrees of freedom 1..30); above that ~normal distribution
_T975 = [12.71, 4.30, 3.18, 2.78, 2.57, 2.45, 2.36, 2.31, 2.26, 2.23, 2.20, 2.18, 2.16, 2.14, 2.13,
         2.12, 2.11, 2.10, 2.09, 2.09, 2.08, 2.07, 2.07, 2.06, 2.06, 2.06, 2.05, 2.05, 2.05, 2.04]


def t95(n: int) -> float:
    """Factor for a 95% interval with n samples (small n: t-distribution)."""
    df = n - 1
    if df < 1:
        return float("nan")
    return _T975[df - 1] if df <= 30 else 1.96


@dataclass
class AgentStats:
    name: str
    hands: int = 0
    net_chips: int = 0
    per_unit: list[float] = field(default_factory=list)   # bb per sample unit
    vpip: int = 0
    pfr: int = 0
    saw_flop: int = 0
    showdowns: int = 0
    showdown_wins: int = 0
    aggr: int = 0          # Bets/Raises postflop
    calls: int = 0         # Calls postflop

    def result(self, big_blind: int, hands_per_unit: float) -> dict:
        n = len(self.per_unit)
        mean_unit = sum(self.per_unit) / n if n else 0.0
        var = sum((x - mean_unit) ** 2 for x in self.per_unit) / (n - 1) if n > 1 else float("nan")
        se_unit = math.sqrt(var / n) if n > 1 else float("nan")
        bb100 = mean_unit / hands_per_unit * 100 if hands_per_unit else 0.0
        se100 = se_unit / hands_per_unit * 100 if hands_per_unit else float("nan")
        pct = lambda a, b: round(100 * a / b, 1) if b else None
        return {
            "agent": self.name, "hands": self.hands, "net_bb": round(self.net_chips / big_blind, 1),
            "bb_per_100": round(bb100, 2), "ci95": [round(bb100 - t95(n) * se100, 2), round(bb100 + t95(n) * se100, 2)],
            "std_error_bb100": round(se100, 2),
            "vpip": pct(self.vpip, self.hands), "pfr": pct(self.pfr, self.hands),
            "aggression": round(self.aggr / self.calls, 2) if self.calls else None,
            "wtsd": pct(self.showdowns, self.saw_flop), "wsd": pct(self.showdown_wins, self.showdowns),
        }


def _tally(rec: HandRecord, seat_agent: list[int], stats: list[AgentStats], unit_net: list[float]):
    by_seat = defaultdict(list)
    for a in rec.actions:
        by_seat[a.seat].append(a)
    for res in rec.results:
        ai = seat_agent[res.seat]
        st = stats[ai]
        if not res.hole:
            continue
        st.hands += 1
        st.net_chips += res.net
        unit_net[ai] += res.net / rec.blinds[1]
        acts = by_seat[res.seat]
        pre = [a for a in acts if a.street == "preflop" and a.kind not in ("post_sb", "post_bb")]
        if any(a.kind in ("call", "bet", "raise") for a in pre):
            st.vpip += 1
        if any(a.kind in ("bet", "raise") for a in pre):
            st.pfr += 1
        post = [a for a in acts if a.street != "preflop"]
        folded_pre = any(a.kind == "fold" for a in pre)
        if not folded_pre and len(rec.board) >= 3:
            st.saw_flop += 1
        st.aggr += sum(1 for a in post if a.kind in ("bet", "raise"))
        st.calls += sum(1 for a in post if a.kind == "call")
        if res.showed:
            st.showdowns += 1
            if res.won > 0 and res.net > 0:
                st.showdown_wins += 1


def run_match(agents: list, hands: int, seed: int = 1, small_blind: int = 10, big_blind: int = 20,
              stack_bb: int = 100, duplicate: bool = True, progress=None, keep_records: int = 0) -> dict:
    """agents: list of agent objects (2-10). hands: number of decks.
    With duplicate=True, hands*len(agents) hands are played."""
    n = len(agents)
    names = [a.name for a in agents]
    if len(set(names)) != n:
        raise ValueError(f"agent names must be unique: {names} (e.g. 'tag:tag2')")
    stats = [AgentStats(nm) for nm in names]
    records: list[HandRecord] = []
    rotations = range(n) if duplicate else [None]
    t0 = time.perf_counter()
    played = 0
    for k in range(hands):
        deck_seed = seed * 1_000_003 + k
        button = k % n
        unit_net = [0.0] * n
        for r in rotations:
            rot = r if r is not None else 0
            seat_agent = [(i + rot) % n for i in range(n)]
            seated = [agents[a] for a in seat_agent]
            rec = play_hand(seated, [stack_bb * big_blind] * n, button, small_blind, big_blind,
                            seed=deck_seed, hand_id=f"{seed}-{k}-{rot}", names=[names[a] for a in seat_agent])
            played += 1
            _tally(rec, seat_agent, stats, unit_net)
            if len(records) < keep_records:
                records.append(rec)
        for i in range(n):
            stats[i].per_unit.append(unit_net[i])
        if progress:
            progress(k + 1, hands, played, time.perf_counter() - t0)
    hands_per_unit = n if duplicate else 1
    elapsed = time.perf_counter() - t0
    results = sorted((s.result(big_blind, hands_per_unit) for s in stats), key=lambda d: -d["bb_per_100"])
    return {
        "eval_version": EVAL_VERSION, "engine_version": ENGINE_VERSION,
        "config": {"agents": names, "deals": hands, "hands_played": played, "seed": seed,
                   "blinds": [small_blind, big_blind], "stack_bb": stack_bb, "duplicate": duplicate},
        "elapsed_s": round(elapsed, 1), "hands_per_s": round(played / elapsed, 1) if elapsed else None,
        "results": results,
        "records": records,
    }


def report_markdown(res: dict) -> str:
    c = res["config"]
    lines = [f"# Match: {', '.join(c['agents'])}", "",
             f"{c['hands_played']} hands ({c['deals']} boards{' x rotation (duplicate)' if c['duplicate'] else ''}), "
             f"seed {c['seed']}, blinds {c['blinds'][0]}/{c['blinds'][1]}, stack {c['stack_bb']} BB, "
             f"{res['hands_per_s']} hands/s", "",
             '| Agent | bb/100 | 95% Interval | VPIP | PFR | Aggr. | WTSD | W$SD |',
             "|---|---|---|---|---|---|---|---|"]
    for r in res["results"]:
        sig = "" if r["ci95"][0] <= 0 <= r["ci95"][1] else " *"
        lines.append(f"| {r['agent']} | {r['bb_per_100']:+.1f}{sig} | {r['ci95'][0]:+.1f} .. {r['ci95'][1]:+.1f} "
                     f"| {r['vpip']} | {r['pfr']} | {r['aggression']} | {r['wtsd']} | {r['wsd']} |")
    lines += ["", '`*` = interval excludes 0 (difference statistically significant).',
              'VPIP/PFR in % of hands, Aggr. = Bets+Raises / Calls after the flop, WTSD = showdown rate after seeing the flop, W$SD = won showdowns.']
    return "\n".join(lines)


def hand_text(rec: HandRecord) -> str:
    """Readable hand history (for debugging)."""
    nm = lambda s: rec.names[s] or f"Seat {s}"
    out = [f"Hand {rec.hand_id}  Button {nm(rec.button)}  Blinds {rec.blinds[0]}/{rec.blinds[1]}"]
    for r in rec.results:
        if r.hole:
            out.append(f"  {nm(r.seat)}: {' '.join(r.hole)}  Stack {r.start_stack}")
    street = None
    for a in rec.actions:
        if a.street != street:
            street = a.street
            n = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}[street]
            out.append(f"  -- {street} {' '.join(rec.board[:n])}")
        amt = f" to {a.amount_to}" if a.kind in ("bet", "raise", "call", "post_sb", "post_bb") else ""
        out.append(f"     {nm(a.seat)} {a.kind}{amt}{' (all-in)' if a.allin else ''}")
    for p in rec.pots:
        out.append(f"  Pot {p['amount']} -> {', '.join(nm(s) for s in p['winners'])}")
    for r in rec.results:
        if r.net:
            out.append(f"  {nm(r.seat)}: {r.net:+d}")
    return "\n".join(out)


def save_result(res: dict, path: Path):
    data = {k: v for k, v in res.items() if k != "records"}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
