"""Pruefstand: jeder Kandidat durchlaeuft dieselben festen Testsets - vergleichbar ueber Wochen.

Testsets (feste Karten UND feste Tische, aendern sich nie innerhalb einer BENCH_VERSION):
  fest48   48 Sit&Go-Schemata gegen den festen Pool rock/tag/lag/station/maniac
  mix96    96 Sit&Go-Schemata, Tische gezogen aus einer festen, staerkeren Mischung
           (u. a. opt-1 und der Profi-Nachahmer pros-bc als menschenaehnlicher Gegner)
  cash     300 Duplicate-Cash-Haende je Platz gegen den festen Pool (bb/100)
  pluribus Uebereinstimmung mit Pluribus (nur Netze)
  Formate (je 48 Schemata, Tische aus der mix-Mischung, bei Bedarf mit Zuruecklegen):
  hu48 Heads-up | 3max48 3 Spieler | 10max48 10 Spieler | turbo48 6 Sp., 30 BB, Blinds alle 5 Haende |
  deep48 6 Sp., 200 BB | pokerth48 PokerTH-Standard (6 Sp., 1000 Chips = 50 BB, alle 9 Haende)
  exploit  Ausbeuter-Test (optional, teuer)
  Groessere Varianten fuer genauere Messungen: Zahl am Namen frei waehlbar, z. B. mix960, pokerth480,
  hu480, fest480. Die ersten Schemata sind identisch mit den kleinen Sets (mix960 beginnt mit mix96).
  "praezise" = mix960, pokerth480, hu480, 10max240 (Intervall etwa 3x enger als die 48er/96er-Sets).

Je Schema/Tisch spielt der Kandidat alle Sitzrotationen. ROI = mittlere Netto-Auszahlung in Buy-ins.
Wichtig: Die Testsets dienen dem VERGLEICHEN und Verfolgen. Fuer die Aufnahme in die Liga gilt
weiter die Aufnahmepruefung mit frischen Karten (optimize.gate) - ein fester Satz, der oft fuer
Entscheidungen benutzt wird, nutzt sich ab.
"""

from __future__ import annotations

import json
import math
import random
import re
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .evaluate import run_match, t95
from .optimize import DEFAULT_CONFIG, DEFAULT_POOL, matchup_payouts
from .tournament import POKERTH_DEFAULT, BlindSchedule, TournamentConfig

BENCH_VERSION = "bench-1"
MIX_PLAYERS = ["rock", "tag", "lag", "station", "maniac", "equity",
               "tag?vpip=0.082&pfr=0.157&value_margin=0.081&raise_margin=0.26&call_slack=-0.021&bluff=0.141"
               "&bet_size=0.808&open_size=3.289&push_bb=14&nash_stack_factor=1.429",
               "nn?run=pros-1@0"]
MIX_WEIGHTS = [3, 3, 2, 1, 1, 1, 3, 3]


FORMAT_SETS = {   # Name: (Gegner am Tisch, Turnierformat)
    "hu48": (1, TournamentConfig(start_stack=1000, blinds=BlindSchedule(10, 20, 10), payouts=(1.0,))),
    "3max48": (2, TournamentConfig(start_stack=1500, blinds=BlindSchedule(10, 20, 10), payouts=(0.65, 0.35))),
    "10max48": (9, TournamentConfig(start_stack=3000, blinds=BlindSchedule(10, 20, 10),
                                    payouts=(0.45, 0.27, 0.18, 0.1))),
    "turbo48": (5, TournamentConfig(start_stack=600, blinds=BlindSchedule(10, 20, 5))),
    "deep48": (5, TournamentConfig(start_stack=4000, blinds=BlindSchedule(10, 20, 15))),
    "pokerth48": (5, POKERTH_DEFAULT),
}


PRECISE_SETS = ("mix960", "pokerth480", "hu480", "10max240")
_SIZED = re.compile(r"^(fest|mix|hu|3max|10max|turbo|deep|pokerth|mensch|nash|kurz)(\d+)$")
HUMAN_BOTS = "mensch-25nl"          # data/humans/<name>.json (humanbots.fit_all)
# Endspiel (Ziel 5): heads-up mit 20 BB, Blinds steigen alle 10 Haende
ENDGAME_CONFIG = TournamentConfig(start_stack=400, blinds=BlindSchedule(10, 20, 10), payouts=(1.0,))
NASH_BOT = "tag?push_bb=40&nash_stack_factor=1"     # spielt bei <= 40 BB nur Push/Fold nach Nash


def parse_set(name: str) -> tuple[str, int]:
    """'mix960' -> ('mix96', 960): Basis-Set (bestimmt Karten und Tische) und Anzahl Schemata."""
    m = _SIZED.match(name)
    if not m:
        return name, 0
    base = {"fest": "fest48", "mix": "mix96", "mensch": "mensch", "nash": "nash", "kurz": "kurz"}.get(
        m.group(1), m.group(1) + "48")
    n = int(m.group(2))
    if not 1 <= n <= 1000:
        raise ValueError(f"Testset {name}: 1 bis 1000 Schemata")
    return base, n


def is_tournament_set(name: str) -> bool:
    return parse_set(name)[1] > 0


def set_config(name: str) -> TournamentConfig:
    base = parse_set(name)[0]
    if base == "mensch":
        return POKERTH_DEFAULT
    if base in ("nash", "kurz"):
        return ENDGAME_CONFIG
    return FORMAT_SETS[base][1] if base in FORMAT_SETS else DEFAULT_CONFIG


def bench_set(name: str) -> list[tuple[int, list[str]]]:
    name, count = parse_set(name)
    if name in FORMAT_SETS:
        k = FORMAT_SETS[name][0]
        rng = random.Random(f"bench|{name}")
        base = 990_000 + 1000 * list(FORMAT_SETS).index(name)
        out = []
        for i in range(count):
            idx, w, table = list(range(len(MIX_PLAYERS))), list(MIX_WEIGHTS), []
            for _ in range(k):
                if not idx:
                    idx, w = list(range(len(MIX_PLAYERS))), list(MIX_WEIGHTS)
                j = rng.choices(range(len(idx)), weights=w)[0]
                table.append(MIX_PLAYERS[idx.pop(j)])
                w.pop(j)
            out.append((base + i, table))
        return out
    if name == "mensch":
        from .humanbots import load_bots
        bots = load_bots(HUMAN_BOTS)
        if not bots:
            raise ValueError(f"keine Mensch-Bots ({HUMAN_BOTS}.json) - erst 'pc.cmd train humans-fit'")
        rng = random.Random("bench|mensch")
        return [(995_000 + i, [rng.choices([b["spec"] for b in bots], weights=[b["share"] for b in bots])[0]
                               for _ in range(5)]) for i in range(count)]
    if name == "nash":              # heads-up 20 BB gegen Push/Fold-Nash
        return [(996_000 + i, [NASH_BOT]) for i in range(count)]
    if name == "kurz":              # heads-up 20 BB gegen einen Mensch-Bot (nach Anteil)
        from .humanbots import load_bots
        bots = load_bots(HUMAN_BOTS)
        rng = random.Random("bench|kurz")
        return [(997_000 + i, [rng.choices([b["spec"] for b in bots], weights=[b["share"] for b in bots])[0]])
                for i in range(count)]
    if name == "fest48":
        return [(777_000 + i, list(DEFAULT_POOL)) for i in range(count)]
    if name == "mix96":
        rng = random.Random(888)
        out = []
        for i in range(count):
            idx, w, table = list(range(len(MIX_PLAYERS))), list(MIX_WEIGHTS), []
            for _ in range(5):
                k = rng.choices(range(len(idx)), weights=w)[0]
                table.append(MIX_PLAYERS[idx.pop(k)])
                w.pop(k)
            out.append((888_000 + i, table))
        return out
    raise ValueError(f"unbekanntes Testset {name}")


def _chunk(args):
    spec, mus, config = args
    return matchup_payouts(spec, mus, config)


def _summary(vals: list[float]) -> dict:
    n = len(vals)
    m = sum(vals) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in vals) / (n - 1)) if n > 1 else float("nan")
    half = t95(n) * sd / math.sqrt(n) * 100
    return {"roi": round(100 * m, 1), "ci95": [round(100 * m - half, 1), round(100 * m + half, 1)], "n": n}


def run_set(spec: str, name: str, ex, config=None, on_chunk=None, partial: Path | None = None) -> dict:
    """24 Blöcke parallel. on_chunk(fertig, gesamt, zwischenstand) nach jedem Block; partial = Datei, in der
    fertige Bloecke sofort gesichert werden (Wiederaufnahme nach Absturz des Elternprozesses - 30.10. gingen so
    85 Minuten Rechnung verloren). Die Datei wird am Ende geloescht."""
    mus = bench_set(name)
    config = config or set_config(name)
    jobs = {i: (spec, mus[i::24], config) for i in range(24) if mus[i::24]}
    done: dict[int, list[float]] = {}
    if partial is not None and partial.exists():
        try:
            saved = json.loads(partial.read_text("utf-8"))
            if saved.get("spec") == spec and saved.get("set") == name:
                done = {int(k): v for k, v in saved["chunks"].items() if int(k) in jobs}
        except (ValueError, KeyError):
            done = {}
    futs = {ex.submit(_chunk, jobs[i]): i for i in jobs if i not in done}
    for f in as_completed(futs):
        done[futs[f]] = list(f.result())
        if partial is not None:
            partial.parent.mkdir(parents=True, exist_ok=True)
            partial.write_text(json.dumps({"spec": spec, "set": name, "chunks": done}), "utf-8")
        if on_chunk:
            on_chunk(len(done), len(jobs), _summary([v for vs in done.values() for v in vs]))
    vals = [0.0] * len(mus)
    for i in range(24):                       # Reihenfolge wiederherstellen (fuer gepaarte Vergleiche)
        for j, v in enumerate(done.get(i, [])):
            vals[i + 24 * j] = v
    if partial is not None and partial.exists():
        partial.unlink()
    return {**_summary(vals), "per_scheme": [round(v, 4) for v in vals]}


def run_cash(spec: str, hands: int = 300) -> dict:
    from .agents import make_agent
    agents = [make_agent(f"{spec}:cand", 1)] + [make_agent(f"{g}:bench-{g}", 99) for g in DEFAULT_POOL]
    res = run_match(agents, hands=hands, seed=4242)
    r = next(x for x in res["results"] if x["agent"] == "cand")
    return {"bb_per_100": r["bb_per_100"], "ci95": r["ci95"], "vpip": r["vpip"], "pfr": r["pfr"]}


def bench_dir() -> Path:
    from .nn_agent import rl_root
    return rl_root().parent / "bench"


def run_bench(spec: str, name: str, sets=("fest48", "mix96", "cash", "pluribus"), exploit: bool = False,
              ex=None, workers: int | None = None, progress=None, on_chunk=None, resume: bool = False) -> dict:
    """progress(set, ergebnis) je fertigem Set; on_chunk(fertig, gesamt, zwischenstand) je Block;
    resume=True sichert fertige Bloecke unter bench/partial-<name>-<set>.json und nimmt dort wieder auf."""
    t0 = time.perf_counter()
    own = ex is None
    ex = ex or ProcessPoolExecutor(workers)
    out = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "bench_version": BENCH_VERSION, "name": name, "spec": spec}
    safe = re.sub(r"[^A-Za-z0-9_.@-]+", "_", name)
    try:
        for s in sets:
            if is_tournament_set(s):
                out[s] = run_set(spec, s, ex, on_chunk=on_chunk,
                                 partial=(bench_dir() / f"partial-{safe}-{s}.json") if resume else None)
            elif s == "cash":
                out[s] = ex.submit(run_cash, spec).result()
            elif s == "pluribus" and spec.startswith("nn?"):
                from .nn_agent import make_nn_agent
                from .phh import agreement, load_dataset
                try:
                    w = make_nn_agent(spec.partition("?")[2].partition(":")[0]).w
                    out[s] = agreement(w, load_dataset("pluribus", ["Pluribus"], version=w["features"]))
                except FileNotFoundError:
                    pass
            if progress and s in out:
                progress(s, out[s])
    finally:
        if own:
            ex.shutdown()
    if exploit:
        from .nn_agent import checkpoint_path
        from .rl import exploit_test
        out["exploit"] = exploit_test(spec, checkpoint_path("pros-1", 0), workers=workers)
        if progress:
            progress("exploit", out["exploit"])
    out["elapsed_s"] = round(time.perf_counter() - t0, 1)
    d = bench_dir()
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(out) + "\n")
    write_report()
    return out


def load_results() -> list[dict]:
    p = bench_dir() / "results.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text("utf-8").splitlines() if line.strip()]


def paired_diff(a: dict, b: dict, s: str) -> dict | None:
    """Gepaarter Vergleich zweier Ergebnisse auf demselben Testset (gleiche Schemata)."""
    if s not in a or s not in b or "per_scheme" not in a[s] or "per_scheme" not in b[s]:
        return None
    return _summary([x - y for x, y in zip(a[s]["per_scheme"], b[s]["per_scheme"])])


def write_report() -> str:
    rows = {}
    for r in load_results():
        if r.get("bench_version") == BENCH_VERSION:
            rows[r["name"]] = {**rows.get(r["name"], {}), **r}   # je Testset der neueste Wert
    ref = rows.get("rock")
    lines = ["# Pruefstand", "", f"Version {BENCH_VERSION}. Feste Testsets, vergleichbar ueber die Zeit. "
             "Δ rock = gepaarte Differenz zu rock auf denselben Karten (95-%-Intervall).", "",
             "| Bot | mix96 ROI | Δ rock | fest48 ROI | Δ rock | Cash bb/100 | Pluribus | Ausbeuter | Stand |",
             "|---|---|---|---|---|---|---|---|---|"]

    def roi(r, s):
        return f"{r[s]['roi']:+.1f} %" if s in r else "-"

    def delta(r, s):
        d = paired_diff(r, ref, s) if ref and r is not ref else None
        return f"{d['roi']:+.1f} [{d['ci95'][0]:+.0f}; {d['ci95'][1]:+.0f}]" if d else "-"

    for r in sorted(rows.values(), key=lambda r: -r.get("mix96", {}).get("roi", -1e9)):
        cash = f"{r['cash']['bb_per_100']:+.0f}" if "cash" in r else "-"
        plu = f"{r['pluribus']['top1']:.0%}" if "pluribus" in r else "-"
        exp = f"{r['exploit']['exploiter_roi']:+.1f} %" if "exploit" in r else "-"
        lines.append(f"| {r['name']} | {roi(r, 'mix96')} | {delta(r, 'mix96')} | {roi(r, 'fest48')} | "
                     f"{delta(r, 'fest48')} | {cash} | {plu} | {exp} | {r['t'][:16]} |")
    fmt = [f for f in FORMAT_SETS if any(f in r for r in rows.values())]
    if fmt:
        lines += ["", "## Formate (ROI, in Klammern Δ rock gepaart)", "", "| Bot | " + " | ".join(fmt) + " |",
                  "|---|" + "---|" * len(fmt)]
        for r in sorted(rows.values(), key=lambda r: -sum(r.get(f, {}).get("roi", 0) for f in fmt)):
            if any(f in r for f in fmt):
                cells = [f"{r[f]['roi']:+.0f} % ({delta(r, f)})" if f in r else "-" for f in fmt]
                lines.append(f"| {r['name']} | " + " | ".join(cells) + " |")
    big = sorted({k for r in rows.values() for k in r if is_tournament_set(k)
                  and k not in FORMAT_SETS and k not in ("fest48", "mix96")})
    if big:
        lines += ["", "## Grosse Testsets (ROI, Δ rock gepaart mit 95-%-Intervall)", "",
                  "| Bot | " + " | ".join(big) + " |", "|---|" + "---|" * len(big)]
        for r in sorted(rows.values(), key=lambda r: -sum(r.get(f, {}).get("roi", 0) for f in big)):
            if any(f in r for f in big):
                cells = [f"{r[f]['roi']:+.1f} % ({delta(r, f)})" if f in r else "-" for f in big]
                lines.append(f"| {r['name']} | " + " | ".join(cells) + " |")
    md = "\n".join(lines) + "\n"
    d = bench_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "report.md").write_text(md, "utf-8")
    return md


def compare(name_a: str, name_b: str) -> list[tuple[str, dict, dict, dict]]:
    """Gepaarter Vergleich zweier Pruefstand-Eintraege auf allen gemeinsamen Turnier-Testsets:
    (Set, Ergebnis A, Ergebnis B, Differenz A-B)."""
    rows = {}
    for r in load_results():
        if r.get("bench_version") == BENCH_VERSION:
            rows[r["name"]] = {**rows.get(r["name"], {}), **r}
    if name_a not in rows or name_b not in rows:
        missing = [n for n in (name_a, name_b) if n not in rows]
        raise KeyError(f"nicht auf dem Pruefstand: {', '.join(missing)}")
    a, b = rows[name_a], rows[name_b]
    out = []
    for s in a:
        if is_tournament_set(s) and s in b:
            d = paired_diff(a, b, s)
            if d:
                out.append((s, a[s], b[s], d))
    return out
