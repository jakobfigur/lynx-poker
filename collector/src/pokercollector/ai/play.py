"""Game sessions human versus bots and their evaluation.

Each session is saved as JSONL (data/play/<Time>_<Mode>.jsonl):
  1st line {"type": "meta", ...}
  per hand {"type": "hand", "record": {...}}     (complete history including all cards)
  end      {"type": "end", "pf": [...], "summary": {...}}
"""

from __future__ import annotations

import dataclasses
import json
import math
import time
from pathlib import Path

from .engine import HandRecord, play_hand
from .evaluate import AgentStats, _tally, t95
from .human import HumanAgent, QuitGame
from .observation import PublicAction
from .recording import RecordingAgent
from .tournament import TournamentConfig, play_tournament

PLAY_VERSION = "play-1"


def _rec_to_dict(rec: HandRecord) -> dict:
    return dataclasses.asdict(rec)


def rec_from_dict(d: dict) -> HandRecord:
    from .engine import SeatResult
    d = dict(d)
    d["actions"] = [PublicAction(**a) for a in d["actions"]]
    d["results"] = [SeatResult(**r) for r in d["results"]]
    d["blinds"] = tuple(d["blinds"])
    return HandRecord(**d)


class SessionWriter:
    def __init__(self, path: Path, meta: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.f = open(path, "w", encoding="utf-8")
        self.write({"type": "meta", **meta})

    def write(self, obj: dict):
        self.f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.f.flush()

    def close(self, end: dict):
        self.write({"type": "end", **end})
        self.f.close()


def play_cash(human: HumanAgent, bots: list, out_dir: Path, hands: int = 1000, stack_bb: int = 100,
              blinds: tuple[int, int] = (10, 20), seed: int | None = None) -> Path:
    """Cash game: stacks remain; anyone falling below 1 BB automatically rebuys."""
    seed = seed if seed is not None else int(time.time())
    rec_human = RecordingAgent(human)
    agents = [rec_human] + bots
    n = len(agents)
    names = [a.name for a in agents]
    sb, bb = blinds
    start = stack_bb * bb
    stacks = [start] * n
    path = out_dir / f"{time.strftime('%Y%m%d-%H%M%S')}_cash.jsonl"
    w = SessionWriter(path, {"mode": "cash", "version": PLAY_VERSION, "seed": seed, "names": names,
                             "human_seat": 0, "human": human.name, "blinds": [sb, bb], "stack_bb": stack_bb})
    played, rebuys = 0, {nm: 0 for nm in names}
    human.out(f"Cash game against {', '.join(names[1:])}. Blinds {sb}/{bb}, Start {start} ({stack_bb} BB). "
              f"'q' quits.")
    try:
        for k in range(hands):
            for s in range(n):
                if stacks[s] < bb:
                    stacks[s] = start
                    rebuys[names[s]] += 1
                    if s == 0:
                        human.out(f"  (You rebuy at: {start})")
            rec = play_hand(agents, stacks, k % n, sb, bb, seed=seed * 1_000_003 + k, hand_id=str(k + 1),
                            names=names)
            stacks = [r.end_stack for r in rec.results]
            w.write({"type": "hand", "record": _rec_to_dict(rec)})
            played += 1
    except (QuitGame, KeyboardInterrupt, EOFError):
        human.out('\nSession ended (current hand not counted).')
    w.close({"hands": played, "rebuys": rebuys, "pf": rec_human.log.pf_spots,
             "summary": rec_human.log.summary()})
    return path


def play_tournament_session(human: HumanAgent, bots: list, out_dir: Path, config: TournamentConfig,
                            seed: int | None = None) -> tuple[Path, object]:
    seed = seed if seed is not None else int(time.time())
    rec_human = RecordingAgent(human)
    agents = [rec_human] + bots
    names = [a.name for a in agents]
    path = out_dir / f"{time.strftime('%Y%m%d-%H%M%S')}_turnier.jsonl"
    w = SessionWriter(path, {"mode": "tournament", "version": PLAY_VERSION, "seed": seed, "names": names,
                             "human_seat": 0, "human": human.name, "start_stack": config.start_stack,
                             "blinds": [config.blinds.small_blind, config.blinds.big_blind],
                             "hands_per_level": config.blinds.hands_per_level, "payouts": list(config.payouts)})
    real_out = human.out
    human.out(f"Tournament against {', '.join(names[1:])}: {config.start_stack} chips, blinds "
              f"{config.blinds.small_blind}/{config.blinds.big_blind}, doubling every "
              f"{config.blinds.hands_per_level} hands. 'q' to quit.")

    def on_hand(rec, hand_no, before):
        w.write({"type": "hand", "record": _rec_to_dict(rec)})
        if before[0] > 0 and rec.results[0].end_stack == 0:
            real_out('\n*** You are out. The rest of the tournament is simulated to the end without output. ***')
            human.out = lambda *a, **k: None

    try:
        res = play_tournament(agents, config, seed=seed, on_hand=on_hand)
    except (QuitGame, KeyboardInterrupt, EOFError):
        human.out = real_out
        human.out('\nTournament aborted — not counted.')
        w.close({"aborted": True, "pf": rec_human.log.pf_spots, "summary": rec_human.log.summary()})
        return path, None
    human.out = real_out
    human.out(f"\nTournament ended after {res.hands} hands. Your place: {res.places[0]:g} out of {len(names)}, "
              f"payout {res.payouts[0]:.2f} buy-ins.")
    for e in res.eliminations:
        human.out(f"  Hand {e['hand']:4d}: {e['name']} -> Place {e['place']:g}")
    w.close({"places": res.places, "payouts": res.payouts, "hands": res.hands, "finished": res.finished,
             "pf": rec_human.log.pf_spots, "summary": rec_human.log.summary()})
    return path, res


# ---- Evaluation ------------------------------------------------------------------

def load_sessions(play_dir: Path) -> list[dict]:
    out = []
    for p in sorted(play_dir.glob("*.jsonl")):
        meta, hands, end = None, [], None
        for line in p.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if d["type"] == "meta":
                meta = d
            elif d["type"] == "hand":
                hands.append(rec_from_dict(d["record"]))
            elif d["type"] == "end":
                end = d
        if meta:
            out.append({"path": p, "meta": meta, "hands": hands, "end": end})
    return out


def player_stats(sessions: list[dict]) -> dict:
    """Key figures per player name over all sessions (human and bots)."""
    stats: dict[str, AgentStats] = {}
    per_hand: dict[str, list[float]] = {}
    for s in sessions:
        names = s["meta"]["names"]
        for rec in s["hands"]:
            local = [stats.setdefault(nm, AgentStats(nm)) for nm in names]
            unit = [0.0] * len(names)
            _tally(rec, list(range(len(names))), local, unit)
            for i, nm in enumerate(names):
                if rec.results[i].hole:
                    per_hand.setdefault(nm, []).append(unit[i])
    out = {}
    for nm, st in stats.items():
        xs = per_hand.get(nm, [])
        n = len(xs)
        mean = sum(xs) / n if n else 0.0
        sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / (n - 1)) if n > 1 else float("nan")
        se100 = sd / math.sqrt(n) * 100 if n > 1 else float("nan")
        r = st.result(1, 1)
        r.update({"hands": n, "bb_per_100": round(mean * 100, 1),
                  "ci95": [round(mean * 100 - t95(n) * se100, 1), round(mean * 100 + t95(n) * se100, 1)]})
        out[nm] = r
    return out


def stats_markdown(sessions: list[dict], human: str = "du") -> str:
    if not sessions:
        return 'No game sessions yet.'
    st = player_stats(sessions)
    lines = [f"# Your matches against the bots", "",
             f"{len(sessions)} session(s), {sum(len(s['hands']) for s in sessions)} hands", "",
             '| Player | Hands | bb/100 | 95% interval | VPIP | PFR | Agg. | WTSD | W$SD |',
             "|---|---|---|---|---|---|---|---|---|"]
    for nm, r in sorted(st.items(), key=lambda kv: (kv[0] != human, -kv[1]["bb_per_100"])):
        who = f"**{nm}**" if nm == human else nm
        lines.append(f"| {who} | {r['hands']} | {r['bb_per_100']:+.1f} | {r['ci95'][0]:+.1f} .. {r['ci95'][1]:+.1f} "
                     f"| {r['vpip']} | {r['pfr']} | {r['aggression']} | {r['wtsd']} | {r['wsd']} |")
    tours = [s for s in sessions if s["meta"]["mode"] == "tournament" and s["end"] and s["end"].get("places")]
    if tours:
        places = [s["end"]["places"][0] for s in tours]
        pay = [s["end"]["payouts"][0] - 1 for s in tours]
        lines += ["", f"Tournaments: {len(tours)}, avg. place {sum(places) / len(places):.2f}, "
                      f"ROI {100 * sum(pay) / len(pay):+.0f} %, wins {sum(1 for p in places if p == 1)}"]
    pf = [x for s in sessions if s["end"] for x in s["end"].get("pf", [])]
    if pf:
        loss = sum(x["ev_loss"] for x in pf)
        wrong = [x for x in pf if x["ev_loss"] > 0.01]
        lines += ["", f"Push/Fold situations: {len(pf)}, of which {len(wrong)} differ from Nash, "
                      f"total EV loss {loss:.2f} BB ({loss / len(pf):.3f} BB per situation)"]
        for x in sorted(wrong, key=lambda x: -x["ev_loss"])[:10]:
            lines.append(f"- {x['hand']} at {x['stack_bb']:g} BB, {x['behind']} behind: you {x['chose']}, "
                         f"better {x['best']} (-{x['ev_loss']:.2f} BB)")
    lines += ["", 'Note: A few hundred hands is statistically small – the interval shows how uncertain the figure still is.']
    return "\n".join(lines)
