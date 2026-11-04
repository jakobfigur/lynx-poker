"""Our targets (GOALS.md in the project folder) and the scoreboard: where does a bot rank per benchmark?

  1  Real PokerTH matches  - Jakob plays, Lynx advises; results per tournament entered manually
  2  Human tables           - human480 (PokerTH format, human-bots from HandHQ)
  3  Slumbot                - heads-up 200 BB vs. an almost flawless bot
  4  Exploitability         - exploiter learns against 5 copies; his ROI is the measure
  5  Endgame                - heads-up 20 BB: against push/fold Nash (nash240) and human bots (kurz240)

Measured with the testbench (bench.py, results.jsonl); the board always reads the latest entry.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

from .bench import bench_dir, load_results
from .tournament import TournamentConfig

ZIELE_VERSION = "ziele-1"
MEASURE_SETS = ("mensch480", "nash240", "kurz240")
PAYOUTS = TournamentConfig().payouts            #as in the simulator: 50/30/20 % of the prize money

#Stages per target: (designation, condition as text) - the check is in _stage()
GOALS = {
    1: ('Real PokerTH games', ['50 tournaments, ROI > 0', '200 tournaments, ROI > +20% and win rate > 1/6']),
    2: ('Human tables (human480)', ['ROI >= +100 %', 'ROI >= +120 %']),
    3: ('Slumbot (HU 200 BB)', ['> -15 bb/100', '> 0 bb/100', 'lower bound 95 % > 0']),
    4: ("Ausnutzbarkeit", ['exploiter <= +5 %']),
    5: ('Endgame HU 20 BB', ['nash240 >= 0 %', 'short240 > +20 %']),
}


def pokerth_log() -> Path:
    return bench_dir().parent / "ziele" / "pokerth.jsonl"


def add_tournament(place: int, players: int, bot: str, note: str = "", **extra) -> dict:
    """extra: further information (e.g. hands, session, source 'auto'), is recorded."""
    if not 1 <= place <= players <= 10:
        raise ValueError('Place between 1 and player count (2..10)')
    rec = {"t": time.strftime('%Y-%m-%d %H:%M:%S'), "platz": place, "spieler": players, "bot": bot, "notiz": note,
           **extra}
    p = pokerth_log()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def remove_last_tournament(bot: str) -> dict | None:
    """Remove last entry for this bot (correction of an incorrect automatic detection)."""
    p = pokerth_log()
    if not p.exists():
        return None
    rows = [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]
    idx = max((i for i, r in enumerate(rows) if r.get("bot") == bot), default=None)
    if idx is None:
        return None
    gone = rows.pop(idx)
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), "utf-8")
    return gone


def pokerth_summary(bot: str | None = None) -> dict | None:
    p = pokerth_log()
    if not p.exists():
        return None
    rows = [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]
    rows = [r for r in rows if bot is None or r["bot"] == bot]
    if not rows:
        return None
    vals = []
    for r in rows:
        pay = PAYOUTS[r["platz"] - 1] * r["spieler"] if r["platz"] - 1 < len(PAYOUTS) else 0.0
        vals.append(pay - 1.0)
    n = len(vals)
    m = sum(vals) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in vals) / (n - 1)) if n > 1 else float("nan")
    from .evaluate import t95
    half = t95(n) * sd / math.sqrt(n) * 100 if n > 1 else float("nan")
    wins = sum(1 for r in rows if r["platz"] == 1)
    return {"n": n, "roi": round(100 * m, 1), "ci95": [round(100 * m - half, 1), round(100 * m + half, 1)],
            "wins": wins, "win_rate": wins / n, "fair_win": sum(1 / r["spieler"] for r in rows) / n}


def latest(name: str) -> dict:
    """Latest values per test set for this name (later entries overwrite earlier ones)."""
    out: dict = {}
    for r in load_results():
        if r.get("name") == name:
            out.update({k: v for k, v in r.items() if k not in ("t", "name", "spec", "elapsed_s")})
    return out


def _stage(goal: int, v: dict) -> tuple[int, str]:
    """(achieved stages, measured value as text)."""
    if goal == 1:
        s = v.get("pokerth")
        if not s:
            return 0, 'No tournaments recorded yet'
        k = 0
        if s["n"] >= 50 and s["roi"] > 0:
            k = 1
        if s["n"] >= 200 and s["roi"] > 20 and s["win_rate"] > 1 / 6:
            k = 2
        return k, (f"{s['n']} tournaments, ROI {s['roi']:+.1f} % [{s['ci95'][0]:+.0f}; {s['ci95'][1]:+.0f}], "
                   f"wins {s['wins']} ({s['win_rate']:.0%}, fair {s['fair_win']:.0%})")
    if goal == 2:
        r = v.get("mensch480")
        if not r:
            return 0, 'not measured'
        return (r["roi"] >= 100) + (r["roi"] >= 120), f"ROI {r['roi']:+.1f} % [{r['ci95'][0]:+.1f}; {r['ci95'][1]:+.1f}]"
    if goal == 3:
        s = v.get("slumbot")
        if not s or not s.get("hands"):
            return 0, 'not measured'
        e = s.get("bereinigt") if s.get("bereinigt", {}).get("n", 0) >= 2 else s["allin_ev"]
        what = "bereinigt" if e is s.get("bereinigt") else "All-in-EV"
        k = (e["bb100"] > -15) + (e["bb100"] > 0) + (e["ci95"][0] > 0)
        return k, f"{s['hands']} hands, {what} {e['bb100']:+.1f} bb/100 [{e['ci95'][0]:+.0f}; {e['ci95'][1]:+.0f}]"
    if goal == 4:
        x = v.get("exploit")
        if not x:
            return 0, 'not measured'
        return int(x["exploiter_roi"] <= 5), f"Exploiter {x['exploiter_roi']:+.1f} % [{x['ci95'][0]:+.1f}; {x['ci95'][1]:+.1f}]"
    if goal == 5:
        a, b = v.get("nash240"), v.get("kurz240")
        if not a and not b:
            return 0, 'not measured'
        k = int(bool(a) and a["roi"] >= 0) + int(bool(b) and b["roi"] > 20)
        txt = []
        if a:
            txt.append(f"nash240 {a['roi']:+.1f} % [{a['ci95'][0]:+.1f}; {a['ci95'][1]:+.1f}]")
        if b:
            txt.append(f"short240 {b['roi']:+.1f} % [{b['ci95'][0]:+.1f}; {b['ci95'][1]:+.1f}]")
        return k, ", ".join(txt)
    raise ValueError(goal)


def scoreboard(name: str, slumbot_name: str | None = None, pokerth_bot: str | None = None) -> list[dict]:
    from . import slumbot
    v = latest(name)
    hands = slumbot.load_hands(slumbot_name or name)
    if hands:
        v["slumbot"] = slumbot.summarize(hands)
    v["pokerth"] = pokerth_summary(pokerth_bot or name)
    rows = []
    for g, (title, stages) in GOALS.items():
        k, txt = _stage(g, v)
        rows.append({"ziel": g, "titel": title, "stufen": stages, "erreicht": k, "wert": txt})
    return rows


def scoreboard_text(name: str, rows: list[dict]) -> str:
    lines = [f"Goals for {name}:"]
    for r in rows:
        n = len(r["stufen"])
        bar = "#" * r["erreicht"] + "." * (n - r["erreicht"])
        nxt = r["stufen"][r["erreicht"]] if r["erreicht"] < n else 'all levels reached'
        lines.append(f"  {r['ziel']}  {r['titel']:26s} [{bar}]  {r['wert']}")
        lines.append(f"     {'':26s}  next level: {nxt}")
    return "\n".join(lines)
