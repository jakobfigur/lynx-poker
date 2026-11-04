"""Measurement against Slumbot (slumbot.com) - a strong public heads-up bot as absolute benchmark.

Format in Slumbot: Heads-up No-Limit, Cash, Blinds 50/100, both stacks at start of each hand 20000 (200 BB).
API: POST /api/new_hand {token?} and /api/act {token, incr}. History as text, streets separated by '/':
k = check, c = call, f = fold, b<N> = bet TO N (street total, like Action.raise_to in engine).
client_pos 0 = Big Blind (acts postflop first), 1 = Small Blind/Button (acts preflop first).

At hand end, Slumbot provides 'winnings' plus 'baseline_winnings': how much Slumbot itself
would have won from our seat with the same cards (card luck; expectation 0, Slumbot vs itself).
winnings - baseline fluctuates almost as much as raw winnings (correlation only ~0.4-0.6, Slumbot plays cards differently)
and is heavily skewed by luck. Better: 'adjusted' = All-in EV - beta * baseline with
estimated optimal beta (control variable) - unbiased and with smallest error bars; this is the
main measure. All-in EV: if all-in before the river, equity counts instead of dealt cards.

Each hand is immediately written to data/bench/slumbot/<name>.jsonl (appendable, nothing lost).
Note: Hands here are played only against Slumbot - none of this involves PokerTH.
"""

from __future__ import annotations

import itertools
import json
import math
import random
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..poker import FULL_DECK
from .agents import make_agent
from .engine import Hand
from .observation import Action, clamp_action

API = "https://slumbot.com/api"
STACK, SB, BB = 20000, 50, 100
SLUMBOT_VERSION = "slumbot-1"
CLIENT, BOT = 0, 1                  # our seat numbers in the engine


class SlumbotError(RuntimeError):
    pass


def _post(endpoint: str, data: dict, retries: int = 5) -> dict:
    body = json.dumps(data).encode()
    for k in range(retries):
        try:
            req = urllib.request.Request(f"{API}/{endpoint}", body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                out = json.loads(r.read())
            if "error_msg" in out:
                raise SlumbotError(out["error_msg"])
            return out
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
            if k == retries - 1:
                raise
            time.sleep(2 ** k)
    raise AssertionError


def parse_action(action: str) -> list[list[tuple[str, int | None]]]:
    """'b200c/kb300' -> [[('b',200),('c',None)], [('k',None),('b',300)]]"""
    streets = []
    for part in action.split("/"):
        toks, i = [], 0
        while i < len(part):
            c = part[i]
            if c == "b":
                j = i + 1
                while j < len(part) and part[j].isdigit():
                    j += 1
                toks.append(("b", int(part[i + 1:j])))
                i = j
            elif c in "kcf":
                toks.append((c, None))
                i += 1
            else:
                raise ValueError(f"unknown character {c!r} in {action!r}")
        streets.append(toks)
    return streets


def replay(action: str, client_pos: int, hole: list[str], board: list[str],
           bot_hole: list[str] | None = None, seed: int = 0) -> Hand:
    """Reconstructs game state in engine. Unknown cards (opponents, upcoming board cards) random."""
    known = set(hole) | set(board) | set(bot_hole or [])
    rest = [c for c in FULL_DECK if c not in known]
    random.Random(seed).shuffle(rest)
    it = iter(rest)
    deck: list[str | None] = [None] * 52
    deck[2 * CLIENT], deck[2 * CLIENT + 1] = hole
    deck[2 * BOT], deck[2 * BOT + 1] = bot_hole or (next(it), next(it))
    for k, c in enumerate(board):
        deck[20 + k] = c
    deck = [c if c is not None else next(it) for c in deck]
    button = CLIENT if client_pos == 1 else BOT          # heads-up: button = small blind
    h = Hand([STACK, STACK], button, SB, BB, deck=deck, hand_id=f"slumbot|{seed}")
    for toks in parse_action(action):
        for kind, amt in toks:
            s = h.to_act
            if kind == "k":
                h.apply(s, Action.check())
            elif kind == "c":
                h.apply(s, Action.call())
            elif kind == "f":
                h.apply(s, Action.fold())
            else:
                h.apply(s, Action.raise_to(amt))
    return h


def to_incr(obs, action: Action) -> str:
    a = clamp_action(obs, action)
    if a.kind == "fold":
        return "f"
    if a.kind == "check" or (a.kind == "call" and obs.to_call == 0):
        return "k"
    if a.kind == "call":
        return "c"
    return f"b{a.amount}"


def _equity(h1: list[str], h2: list[str], board: list[str], samples: int = 4000, seed: int = 0) -> float:
    """Equity of h1 against h2 (split counts half). Exact to 2 missing cards, otherwise Monte Carlo."""
    from ..fastpoker import evaluate_fast
    rest = [c for c in FULL_DECK if c not in set(h1) | set(h2) | set(board)]
    need = 5 - len(board)
    if need <= 2:
        runs = itertools.combinations(rest, need)
    else:
        rng = random.Random(seed)
        runs = (rng.sample(rest, need) for _ in range(samples))
    tot = n = 0
    for r in runs:
        b = board + list(r)
        a, c = evaluate_fast(h1 + b), evaluate_fast(h2 + b)
        tot += 1.0 if a > c else 0.5 if a == c else 0.0
        n += 1
    return tot / n


def allin_ev(h: Hand, hole: list[str], bot_hole: list[str]) -> float | None:
    """Net (chips) for us after all-in EV, if all-in occurred before the river and cards were shown."""
    rec = h.record
    if rec is None or not rec.went_to_showdown or not any(h.allin):
        return None
    last = rec.actions[-1].street
    nb = {"preflop": 0, "flop": 3, "turn": 4}.get(last)
    if nb is None:
        return None
    eff = min(h.committed)
    import zlib
    eq = _equity(hole, bot_hole, rec.board[:nb], seed=zlib.crc32("".join(hole + bot_hole).encode()) & 0xFFFF)
    return (2 * eq - 1) * eff


def play_hand(agent, token: str | None, seed: int) -> dict:
    r = _post("new_hand", {"token": token} if token else {})
    token = r.get("token", token)
    decisions = 0
    while "winnings" not in r:
        h = replay(r["action"], r["client_pos"], r["hole_cards"], r["board"], seed=seed)
        if h.done or h.to_act != CLIENT:
            raise SlumbotError(f"Game state does not match: {r}")
        obs = h.observation(CLIENT)
        incr = to_incr(obs, agent.act(obs))
        decisions += 1
        r = _post("act", {"token": token, "incr": incr})
        token = r.get("token", token)
    out = {"token": token, "client_pos": r["client_pos"], "hole": r["hole_cards"], "board": r["board"],
           "bot_hole": r.get("bot_hole_cards"), "action": r["action"], "winnings": r["winnings"],
           "baseline": r.get("baseline_winnings"), "decisions": decisions}
    #Cross-check: engine calculates the same result (checks translation)
    h = replay(r["action"], r["client_pos"], r["hole_cards"], r["board"], r.get("bot_hole_cards"), seed=seed)
    if h.done and h.record is not None:
        net = h.record.results[CLIENT].net
        out["engine_net"] = net
        if out["bot_hole"]:
            ev = allin_ev(h, r["hole_cards"], out["bot_hole"])
            out["allin_ev"] = round(ev, 1) if ev is not None else None
    return out


def results_dir() -> Path:
    from .nn_agent import rl_root
    return rl_root().parent / "bench" / "slumbot"


def load_hands(name: str) -> list[dict]:
    p = results_dir() / f"{name}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]


def _stat(vals: list[float]) -> dict:
    n = len(vals)
    if n < 2:
        return {"bb100": float("nan"), "ci95": [float("nan")] * 2, "n": n}
    m = sum(vals) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in vals) / (n - 1))
    half = 1.96 * sd / math.sqrt(n)
    f = 100 / BB
    return {"bb100": round(m * f, 1), "ci95": [round((m - half) * f, 1), round((m + half) * f, 1)], "n": n}


def summarize(hands: list[dict]) -> dict:
    raw = [h["winnings"] for h in hands]
    ev = [h["allin_ev"] if h.get("allin_ev") is not None else h["winnings"] for h in hands]
    base = [h["winnings"] - h["baseline"] for h in hands if h.get("baseline") is not None]
    mism = sum(1 for h in hands if "engine_net" in h and h["engine_net"] != h["winnings"])
    return {"roh": _stat(raw), "allin_ev": _stat(ev), "vs_baseline": _stat(base), "bereinigt": adjusted(hands),
            "hands": len(hands), "engine_mismatch": mism}


def adjusted(hands: list[dict]) -> dict:
    """All-in EV adjusted with card luck (baseline, expectation 0) as control variable."""
    pairs = [(h["allin_ev"] if h.get("allin_ev") is not None else h["winnings"], h["baseline"])
             for h in hands if h.get("baseline") is not None]
    if len(pairs) < 3:
        return _stat([])
    n = len(pairs)
    mw = sum(w for w, _ in pairs) / n
    mb = sum(b for _, b in pairs) / n
    vb = sum((b - mb) ** 2 for _, b in pairs) / (n - 1)
    beta = sum((w - mw) * (b - mb) for w, b in pairs) / (n - 1) / vb if vb > 0 else 0.0
    out = _stat([w - beta * b for w, b in pairs])
    out["beta"] = round(beta, 2)
    out["glueck_bb100"] = round(mb * 100 / BB, 1)
    return out


def run(spec: str, name: str, hands: int, workers: int = 4, progress=None) -> dict:
    """Play up to `hands` more hands with `workers` parallel Slumbot sessions."""
    d = results_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.jsonl"
    done0 = len(load_hands(name))
    per = [hands // workers + (1 if i < hands % workers else 0) for i in range(workers)]
    import threading
    lock = threading.Lock()
    count = [0]

    def worker(i: int):
        agent = make_agent(f"{spec}:cand", 1000 + i)
        token = None
        errors = 0
        for k in range(per[i]):
            try:
                res = play_hand(agent, token, seed=(done0 + i * 100_003 + k) & 0x7FFFFFFF)
            except (SlumbotError, ValueError) as e:
                errors += 1
                token = None                     # new session
                if errors > 20:
                    raise
                print(f"  Session {i}: {e} - new session", flush=True)
                continue
            token = res.pop("token")
            res["spec"], res["t"] = spec, time.strftime('%Y-%m-%d %H:%M:%S')
            with lock:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(res) + "\n")
                count[0] += 1
                if progress and count[0] % 100 == 0:
                    progress(count[0], summarize(load_hands(name)))

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(worker, range(workers)))
    return summarize(load_hands(name))
