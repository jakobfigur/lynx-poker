"""Unsere Ziele (ZIELE.md im Projektordner) und die Anzeigetafel: wo steht ein Bot je Benchmark?

  1  Echte PokerTH-Partien  - Jakob spielt, Lynx beraet; Ergebnis je Turnier von Hand eingetragen
  2  Mensch-Tische          - mensch480 (PokerTH-Format, Mensch-Bots aus HandHQ)
  3  Slumbot                - heads-up 200 BB gegen einen fast fehlerfreien Bot
  4  Ausnutzbarkeit         - Ausbeuter lernt gegen 5 Kopien; sein ROI ist das Mass
  5  Endspiel               - heads-up 20 BB: gegen Push/Fold-Nash (nash240) und Mensch-Bots (kurz240)

Gemessen wird mit dem Pruefstand (bench.py, results.jsonl); die Tafel liest immer den neuesten Eintrag.
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
PAYOUTS = TournamentConfig().payouts            # wie im Simulator: 50/30/20 % des Preisgelds

# Stufen je Ziel: (Bezeichnung, Bedingung als Text) - die Pruefung steht in _stage()
GOALS = {
    1: ("Echte PokerTH-Partien", ["50 Turniere, ROI > 0", "200 Turniere, ROI > +20 % und Siegquote > 1/6"]),
    2: ("Mensch-Tische (mensch480)", ["ROI >= +100 %", "ROI >= +120 %"]),
    3: ("Slumbot (HU 200 BB)", ["> -15 bb/100", "> 0 bb/100", "untere Grenze 95 % > 0"]),
    4: ("Ausnutzbarkeit", ["Ausbeuter <= +5 %"]),
    5: ("Endspiel HU 20 BB", ["nash240 >= 0 %", "kurz240 > +20 %"]),
}


def pokerth_log() -> Path:
    return bench_dir().parent / "ziele" / "pokerth.jsonl"


def add_tournament(place: int, players: int, bot: str, note: str = "", **extra) -> dict:
    """extra: weitere Angaben (z. B. Haende, Sitzung, Quelle 'auto'), werden mitgeschrieben."""
    if not 1 <= place <= players <= 10:
        raise ValueError("Platz zwischen 1 und Spielerzahl (2..10)")
    rec = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "platz": place, "spieler": players, "bot": bot, "notiz": note,
           **extra}
    p = pokerth_log()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def remove_last_tournament(bot: str) -> dict | None:
    """Letzten Eintrag dieses Bots entfernen (Korrektur einer falschen automatischen Erkennung)."""
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
    """Neueste Werte je Testset fuer diesen Namen (spaetere Eintraege ueberschreiben fruehere)."""
    out: dict = {}
    for r in load_results():
        if r.get("name") == name:
            out.update({k: v for k, v in r.items() if k not in ("t", "name", "spec", "elapsed_s")})
    return out


def _stage(goal: int, v: dict) -> tuple[int, str]:
    """(erreichte Stufen, Messwert als Text)."""
    if goal == 1:
        s = v.get("pokerth")
        if not s:
            return 0, "noch keine Turniere eingetragen"
        k = 0
        if s["n"] >= 50 and s["roi"] > 0:
            k = 1
        if s["n"] >= 200 and s["roi"] > 20 and s["win_rate"] > 1 / 6:
            k = 2
        return k, (f"{s['n']} Turniere, ROI {s['roi']:+.1f} % [{s['ci95'][0]:+.0f}; {s['ci95'][1]:+.0f}], "
                   f"Siege {s['wins']} ({s['win_rate']:.0%}, fair {s['fair_win']:.0%})")
    if goal == 2:
        r = v.get("mensch480")
        if not r:
            return 0, "nicht gemessen"
        return (r["roi"] >= 100) + (r["roi"] >= 120), f"ROI {r['roi']:+.1f} % [{r['ci95'][0]:+.1f}; {r['ci95'][1]:+.1f}]"
    if goal == 3:
        s = v.get("slumbot")
        if not s or not s.get("hands"):
            return 0, "nicht gemessen"
        e = s.get("bereinigt") if s.get("bereinigt", {}).get("n", 0) >= 2 else s["allin_ev"]
        what = "bereinigt" if e is s.get("bereinigt") else "All-in-EV"
        k = (e["bb100"] > -15) + (e["bb100"] > 0) + (e["ci95"][0] > 0)
        return k, f"{s['hands']} Haende, {what} {e['bb100']:+.1f} bb/100 [{e['ci95'][0]:+.0f}; {e['ci95'][1]:+.0f}]"
    if goal == 4:
        x = v.get("exploit")
        if not x:
            return 0, "nicht gemessen"
        return int(x["exploiter_roi"] <= 5), f"Ausbeuter {x['exploiter_roi']:+.1f} % [{x['ci95'][0]:+.1f}; {x['ci95'][1]:+.1f}]"
    if goal == 5:
        a, b = v.get("nash240"), v.get("kurz240")
        if not a and not b:
            return 0, "nicht gemessen"
        k = int(bool(a) and a["roi"] >= 0) + int(bool(b) and b["roi"] > 20)
        txt = []
        if a:
            txt.append(f"nash240 {a['roi']:+.1f} % [{a['ci95'][0]:+.1f}; {a['ci95'][1]:+.1f}]")
        if b:
            txt.append(f"kurz240 {b['roi']:+.1f} % [{b['ci95'][0]:+.1f}; {b['ci95'][1]:+.1f}]")
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
    lines = [f"Ziele fuer {name}:"]
    for r in rows:
        n = len(r["stufen"])
        bar = "#" * r["erreicht"] + "." * (n - r["erreicht"])
        nxt = r["stufen"][r["erreicht"]] if r["erreicht"] < n else "alle Stufen erreicht"
        lines.append(f"  {r['ziel']}  {r['titel']:26s} [{bar}]  {r['wert']}")
        lines.append(f"     {'':26s}  naechste Stufe: {nxt}")
    return "\n".join(lines)
