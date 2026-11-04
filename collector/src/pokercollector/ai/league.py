""" League with rating, benchmark against fixed opponents and development progression.

Rating: Weng-Lin (2011), Plackett-Luce model (like OpenSkill) - for placements with
any number of players, with uncertainty sigma per player. Display on Elo-like
scale: 1500 + 48 * (mu - 25). 48 points per unit because a beta difference (25/6)
corresponds to about 200 Elo points (~76% win probability).
"Safe rating" = display - 3 sigma (increases only if a player is demonstrated good).

A league match = one duplicate Sit&Go card schema: all seat rotations are played,
placement is from sum of payouts. This removes much card luck.

Files (data/league/): players.json, games.jsonl, benchmarks.jsonl, report.md, report.html
"""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .agents import make_agent
from .evaluate import run_match
from .recording import DecisionLog, RecordingAgent
from .tournament import TournamentConfig, play_tournament

LEAGUE_VERSION = "league-1"
MU0, SIGMA0 = 25.0, 25.0 / 3
BETA = SIGMA0 / 2
KAPPA = 1e-4
GAUNTLET = ["rock", "tag", "station", "maniac", "lag"]


def display(mu: float) -> float:
    return 1500 + 48 * (mu - MU0)


@dataclass
class Player:
    name: str
    spec: str | None             # None = human
    kind: str = "bot"            # 'bot' | 'human'
    note: str = ""
    created: str = ""
    mu: float = MU0
    sigma: float = SIGMA0
    games: int = 0
    active: bool = True

    @property
    def rating(self) -> float:
        return display(self.mu)

    @property
    def rating_sd(self) -> float:
        return 48 * self.sigma

    @property
    def conservative(self) -> float:
        return display(self.mu - 3 * self.sigma)


def rate_plackett_luce(ratings: list[tuple[float, float]], ranks: list[float]) -> list[tuple[float, float]]:
    """ Weng-Lin Plackett-Luce update. ratings: (mu, sigma) per player; ranks: smaller = better,
    ties allowed. Returns new (mu, sigma)."""
    n = len(ratings)
    c = math.sqrt(sum(s * s + BETA * BETA for _, s in ratings))
    e = [math.exp(m / c) for m, _ in ratings]
    sum_q = [sum(e[s] for s in range(n) if ranks[s] >= ranks[q]) for q in range(n)]
    a_q = [sum(1 for s in range(n) if ranks[s] == ranks[q]) for q in range(n)]
    out = []
    for i, (mu, sigma) in enumerate(ratings):
        omega = delta = 0.0
        for q in range(n):
            if ranks[q] > ranks[i]:
                continue
            p = e[i] / sum_q[q]
            omega += ((1.0 if q == i else 0.0) - p) / a_q[q]
            gamma = sigma / c
            delta += gamma * (sigma * sigma / (c * c)) * p * (1 - p) / a_q[q]
        new_mu = mu + sigma * sigma / c * omega
        new_sigma = sigma * math.sqrt(max(1 - delta, KAPPA))
        out.append((new_mu, new_sigma))
    return out


class League:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.players: dict[str, Player] = {}
        p = root / "players.json"
        if p.exists():
            for d in json.loads(p.read_text("utf-8")):
                self.players[d["name"]] = Player(**d)

    def save(self):
        tmp = self.root / "players.json.tmp"
        tmp.write_text(json.dumps([asdict(p) for p in self.players.values()], indent=2, ensure_ascii=False),
                       "utf-8")
        tmp.replace(self.root / "players.json")

    def add(self, name: str, spec: str | None, kind: str = "bot", note: str = "") -> Player:
        if name in self.players:
            raise ValueError(f"'{name}' already exists")
        if spec is not None:
            make_agent(spec)    # checks the specification
        p = Player(name, spec, kind, note, time.strftime('%Y-%m-%d %H:%M'))
        self.players[name] = p
        self.save()
        return p

    def ensure_defaults(self):
        for k in ("rock", "tag", "lag", "station", "maniac", "equity", "random"):
            if k not in self.players:
                self.add(k, k, note="Standard-Pool")

    def agent(self, name: str, seed: int):
        p = self.players[name]
        return make_agent(f"{p.spec}:{name}", seed)

    # ---- Games ------------------------------------------------------------------

    def record_game(self, participants: list[str], ranks: list[float], payouts: list[float], kind: str,
                    extra: dict | None = None):
        before = [(self.players[n].mu, self.players[n].sigma) for n in participants]
        after = rate_plackett_luce(before, ranks)
        for n, (mu, sg) in zip(participants, after):
            self.players[n].mu, self.players[n].sigma = mu, sg
            self.players[n].games += 1
        self.save()
        rec = {"t": time.strftime('%Y-%m-%d %H:%M:%S'), "type": kind, "participants": participants,
               "ranks": ranks, "payouts": [round(x, 3) for x in payouts],
               "before": [[round(m, 3), round(s, 3)] for m, s in before],
               "after": [[round(m, 3), round(s, 3)] for m, s in after], **(extra or {})}
        with open(self.root / "games.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def play_round(self, names: list[str], config: TournamentConfig, seed: int) -> dict:
        """ A duplicate Sit&Go scheme: all rotations, rank by sum of payouts."""
        n = len(names)
        logs = {nm: DecisionLog() for nm in names}
        total = {nm: 0.0 for nm in names}
        for r in range(n):
            order = [names[(i + r) % n] for i in range(n)]
            agents = [RecordingAgent(self.agent(nm, seed), logs[nm]) for nm in order]
            res = play_tournament(agents, config, seed=seed)
            for seat, nm in enumerate(order):
                total[nm] += res.payouts[seat]
        # Rank: higher sum = better; ties share the rank
        ranks = []
        for nm in names:
            better = sum(1 for v in total.values() if v > total[nm])
            ranks.append(better + 1)
        pf = {nm: logs[nm].summary() for nm in names}
        return self.record_game(names, ranks, [total[nm] / n for nm in names], "duplicate_sng",
                                {"seed": seed, "pushfold": pf})

    def run(self, rounds: int, table: int = 6, config: TournamentConfig | None = None, seed: int | None = None,
            progress=None) -> list[dict]:
        """ Bots (no humans) in random seatings; those who played less get preference."""
        config = config or TournamentConfig()
        rng = random.Random(seed if seed is not None else int(time.time()))
        bots = [p for p in self.players.values() if p.kind == "bot" and p.active]
        if len(bots) < 2:
            raise ValueError('at least two active bots required')
        out = []
        for k in range(rounds):
            size = min(table, len(bots))
            pool = sorted(bots, key=lambda p: (p.games + rng.random() * 3))
            names = [p.name for p in pool[:size]]
            rng.shuffle(names)
            out.append(self.play_round(names, config, seed=rng.randrange(1 << 30)))
            if progress:
                progress(k + 1, rounds, out[-1])
        return out

    # ---- Benchmark ---------------------------------------------------------------

    def benchmark(self, name: str, hands: int = 300, tournaments: int = 10, seed: int = 4242,
                  config: TournamentConfig | None = None) -> dict:
        """ Fixed opponent group, fixed seed: comparable across versions."""
        from .tournament import run_tournaments
        config = config or TournamentConfig()
        gauntlet = [make_agent(f"{g}:bench-{g}", 99) for g in GAUNTLET]
        me = self.agent(name, 1)
        cash = run_match([me] + gauntlet, hands=hands, seed=seed)
        me = self.agent(name, 1)
        log = DecisionLog()
        sng = run_tournaments([RecordingAgent(me, log)] + [make_agent(f"{g}:bench-{g}", 99) for g in GAUNTLET],
                              tournaments, config, seed=seed)
        c = next(r for r in cash["results"] if r["agent"] == name)
        s = next(r for r in sng["results"] if r["agent"] == name)
        rec = {"t": time.strftime('%Y-%m-%d %H:%M:%S'), "player": name, "spec": self.players[name].spec,
               "gauntlet": GAUNTLET, "seed": seed,
               "cash": {"hands": cash["config"]["hands_played"], "bb_per_100": c["bb_per_100"], "ci95": c["ci95"],
                        "vpip": c["vpip"], "pfr": c["pfr"], "aggression": c["aggression"]},
               "sng": {"tournaments": s["tournaments"], "roi_pct": s["roi_pct"], "ci95": s["ci95"],
                       "avg_place": s["avg_place"], "itm_pct": s["itm_pct"]},
               "pushfold": log.summary()}
        with open(self.root / "benchmarks.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    # ---- Evaluation --------------------------------------------------------------

    def games(self) -> list[dict]:
        p = self.root / "games.jsonl"
        return [json.loads(l) for l in p.read_text("utf-8").splitlines() if l.strip()] if p.exists() else []

    def benchmarks(self) -> list[dict]:
        p = self.root / "benchmarks.jsonl"
        return [json.loads(l) for l in p.read_text("utf-8").splitlines() if l.strip()] if p.exists() else []

    def history(self) -> dict[str, list[tuple[int, float, float]]]:
        """ Rating progression per player: (league game no., rating, sigma in display points)."""
        h: dict[str, list] = {}
        for i, g in enumerate(self.games(), 1):
            for n, (mu, sg) in zip(g["participants"], g["after"]):
                h.setdefault(n, []).append((i, display(mu), 48 * sg))
        return h

    def pushfold_quality(self) -> dict[str, dict]:
        agg: dict[str, list] = {}
        for g in self.games():
            for n, s in (g.get("pushfold") or {}).items():
                a = agg.setdefault(n, [0, 0.0, 0])
                a[0] += s["pf_spots"]
                a[1] += s["pf_ev_loss_total_bb"]
                a[2] += s["pf_mistakes"]
        return {n: {"spots": a[0], "ev_loss_per_spot": round(a[1] / a[0], 3) if a[0] else None,
                    "mistake_pct": round(100 * a[2] / a[0], 1) if a[0] else None} for n, a in agg.items()}

    def leaderboard_markdown(self) -> str:
        pf = self.pushfold_quality()
        last_bench = {}
        for b in self.benchmarks():
            last_bench[b["player"]] = b
        rows = sorted(self.players.values(), key=lambda p: -p.conservative)
        lines = [f"# League ({len(self.games())} league games)", "",
                 '| # | Player | Rating | ± | Secure | Games | Benchmark Cash bb/100 | Benchmark SNG ROI | Push/Fold Loss BB/Spot | Specification |',
                 "|---|---|---|---|---|---|---|---|---|---|"]
        for i, p in enumerate(rows, 1):
            b = last_bench.get(p.name)
            cash = f"{b['cash']['bb_per_100']:+.0f} ({b['cash']['ci95'][0]:+.0f}..{b['cash']['ci95'][1]:+.0f})" if b else "-"
            sng = f"{b['sng']['roi_pct']:+.0f} % ({b['sng']['ci95'][0]:+.0f}..{b['sng']['ci95'][1]:+.0f})" if b else "-"
            q = pf.get(p.name, {})
            pfq = f"{q['ev_loss_per_spot']:.3f} ({q['spots']})" if q.get("spots") else "-"
            lines.append(f"| {i} | {p.name}{' (human)' if p.kind == 'human' else ''} | {p.rating:.0f} "
                         f"| {p.rating_sd:.0f} | {p.conservative:.0f} | {p.games} | {cash} | {sng} | {pfq} "
                         f"| `{p.spec or '-'}` |")
        lines += ["", "Rating: Elo-like (start 1500 ± 400). 'secure' = rating minus 3 sigma; sorted accordingly.",
                  'Benchmark: fixed opponents (' + ", ".join(GAUNTLET) + '), fixed seed - comparable across versions.',
                  'Push/Fold loss: average BB lost per short-stack decision versus Nash (0 = perfect), number of situations in parentheses.']
        return "\n".join(lines)

    def report_html(self) -> str:
        hist = self.history()
        w, h, pad = 900, 420, 50
        all_pts = [pt for v in hist.values() for pt in v]
        if not all_pts:
            return '<html><body><p>No league games yet.</p></body></html>'
        xmax = max(p[0] for p in all_pts)
        ys = [p[1] for p in all_pts]
        ymin, ymax = min(ys) - 50, max(ys) + 50
        sx = lambda x: pad + (w - 2 * pad) * (x - 1) / max(1, xmax - 1)
        sy = lambda y: h - pad - (h - 2 * pad) * (y - ymin) / max(1e-9, ymax - ymin)
        colors = ["#2a6fdb", "#d9480f", "#2b8a3e", "#ae3ec9", "#e67700", "#0b7285", "#c92a2a", "#5c940d",
                  "#364fc7", "#862e9c"]
        paths, legend = [], []
        for i, (name, pts) in enumerate(sorted(hist.items(), key=lambda kv: -kv[1][-1][1])):
            col = colors[i % len(colors)]
            d = " ".join(f"{'M' if j == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for j, (x, y, _) in enumerate(pts))
            paths.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2"/>')
            legend.append(f'<span style="color:{col}">&#9632;</span> {name} {pts[-1][1]:.0f} ± {pts[-1][2]:.0f}')
        grid = []
        step = 100
        y = math.ceil(ymin / step) * step
        while y <= ymax:
            grid.append(f'<line x1="{pad}" x2="{w - pad}" y1="{sy(y):.1f}" y2="{sy(y):.1f}" stroke="#8884"/>'
                        f'<text x="{pad - 6}" y="{sy(y) + 4:.1f}" font-size="11" text-anchor="end" fill="currentColor">{y:.0f}</text>')
            y += step
        board = self.leaderboard_markdown().replace("<", "&lt;")
        return f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Poker League</title>
<style>body{{font-family:system-ui,sans-serif;margin:24px;background:#fff;color:#222}}
@media (prefers-color-scheme:dark){{body{{background:#1b1b1f;color:#ddd}}}}
pre{{white-space:pre-wrap;font-size:13px}} .legend span{{font-size:16px}}</style></head><body>
<h1>Poker League: Rating History</h1>
<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px">{''.join(grid)}{''.join(paths)}
<text x="{w / 2}" y="{h - 12}" font-size="12" text-anchor="middle" fill="currentColor">League Game</text></svg>
<p class="legend">{'<br>'.join(legend)}</p>
<pre>{board}</pre></body></html>"""
