"""Import foreign hand histories in PHH format (Poker Hand History, Univ. Toronto).

Source: github.com/uoftcprg/phh-dataset (MIT). Most important part: the 10,000 hands by Pluribus
against pros (Brown & Sandholm 2019), 6-max, 100 BB, ALL cards known.

Each hand is replayed move-by-move in our engine. For each decision, the exact observation
available to the player at the time is recreated, from which features + action are derived as in
imitating a bot. Incidentally, this is an independent test of the engine: player order and final stacks must match the file.

PHH conventions: p1 = small blind, p2 = big blind, last player = button.
'd dh p1 AcKd' hole cards, 'd db 7d5h9d' board cards, 'p3 f' fold, 'p3 cc' check/call,
'p3 cbr 210' bet/raise TO 210 (street bet), 'p1 sm AcKd' show cards ('p1 sm' = muck).
"""

from __future__ import annotations

import random
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..poker import FULL_DECK
from .engine import Hand
from .features import FEATURES_VERSION, N_ACTIONS, N_FEATURES, action_mask, features, from_action
from .observation import Action, clamp_action

PHH_VERSION = "phh-1"


@dataclass
class ReplayResult:
    ok: bool
    problem: str | None
    samples: list[tuple]          # (player, x, mask, action, result_in_bb)


def load_phh(path: Path) -> dict:
    return tomllib.loads(path.read_text("utf-8"))


def _split(cards: str) -> list[str]:
    return [cards[i:i + 2] for i in range(0, len(cards), 2)]


def _build_deck(holes: list[list[str]], board: list[str], seed: int) -> list[str]:
    """Deck in engine order: seat i -> deck[2i:2i+2], board -> deck[20:25].
    Unknown cards are filled with unused cards."""
    used = {c for h in holes for c in h} | set(board)
    rest = [c for c in FULL_DECK if c not in used]
    random.Random(seed).shuffle(rest)
    deck = [None] * 52
    for i, h in enumerate(holes):
        deck[2 * i], deck[2 * i + 1] = h
    for k, c in enumerate(board[:5]):
        deck[20 + k] = c
    it = iter(rest)
    return [c if c is not None else next(it) for c in deck]


def replay(hand: dict, hand_no: int = 0) -> ReplayResult:
    """Replays a PHH hand in our engine and collects every decision."""
    if hand.get("variant") != "NT":
        return ReplayResult(False, f"Variant {hand.get('variant')} not supported", [])
    stacks = [int(round(s)) for s in hand["starting_stacks"]]
    n = len(stacks)
    blinds = hand["blinds_or_straddles"]
    if any(a for a in hand.get("antes", [])) or any(b for b in blinds[2:]):
        return ReplayResult(False, 'Antes/Straddles not supported', [])
    sb, bb = int(blinds[0]), int(blinds[1])
    holes: list[list[str] | None] = [None] * n
    board: list[str] = []
    for a in hand["actions"]:
        p = a.split()
        if p[0] == "d" and p[1] == "dh":
            holes[int(p[2][1:]) - 1] = _split(p[3]) if "?" not in p[3] else None
        elif p[0] == "d" and p[1] == "db":
            board += _split(p[2])
    if any(h is None for h in holes):
        return ReplayResult(False, 'not all hole cards known', [])
    names = hand.get("players") or [f"p{i + 1}" for i in range(n)]
    # Engine: SB to the left of Button -> button = last seat, then SB = seat 0, BB = seat 1
    h = Hand(stacks, n - 1, sb, bb, deck=_build_deck(holes, board, hand_no), hand_id=f"phh-{hand_no}",
             names=list(names))
    if n == 2:
        return ReplayResult(False, "Heads-up: Blindreihenfolge abweichend, ausgelassen", [])
    pending = []                      # (seat, x, mask, action)
    for a in hand["actions"]:
        p = a.split()
        if p[0] == "d" or p[1] == "sm":
            continue
        seat = int(p[0][1:]) - 1
        if h.done:
            return ReplayResult(False, f"Action after hand ended: {a}", [])
        if h.to_act != seat:
            return ReplayResult(False, f"Action order: file {a}, Engine expects p{h.to_act + 1}", [])
        obs = h.observation(seat)
        if p[1] == "f":
            act = Action.fold()
        elif p[1] == "cc":
            act = Action.check() if obs.can_check else Action.call()
        elif p[1] == "cbr":
            act = Action.raise_to(int(round(float(p[2]))))
        else:
            return ReplayResult(False, f"unknown action {a}", [])
        legal = clamp_action(obs, act)
        if legal != act and not (act.kind == "fold" and obs.can_check):
            return ReplayResult(False, f"not rule-compliant in our engine: {a} -> {legal}", [])
        pending.append((seat, features(obs), action_mask(obs), from_action(obs, legal)))
        h.apply(seat, legal)
    if not h.done:
        return ReplayResult(False, 'Hand incomplete in file', [])
    end = [r.end_stack for r in h.record.results]
    want = hand.get("finishing_stacks")
    # up to 1 chip difference: the file splits pots into half chips, we carry the odd chip forward
    if want is not None and any(abs(w - e) > 1 for w, e in zip(want, end)):
        return ReplayResult(False, f"Endstacks: Datei {want}, Engine {end}", [])
    net_bb = [(end[i] - stacks[i]) / bb for i in range(n)]
    samples = [(names[s], x, m, a, net_bb[s]) for s, x, m, a in pending]
    return ReplayResult(True, None, samples)


def build_dataset(files: list[Path], progress=None) -> tuple[dict, dict]:
    """Replay all files. Result: arrays like in imitation + validation report."""
    xs, ms, acts, rs, players = [], [], [], [], []
    report = {"hands": 0, "ok": 0, "problems": {}, "examples": []}
    for k, f in enumerate(sorted(files)):
        hand = load_phh(f)
        res = replay(hand, k)
        report["hands"] += 1
        if not res.ok:
            key = res.problem.split(":")[0]
            report["problems"][key] = report["problems"].get(key, 0) + 1
            if len(report["examples"]) < 10:
                report["examples"].append(f"{f.parent.name}/{f.name}: {res.problem}")
            continue
        report["ok"] += 1
        for name, x, m, a, r in res.samples:
            players.append(name)
            xs.append(x)
            ms.append(m)
            acts.append(a)
            rs.append(r)
        if progress and (k + 1) % 1000 == 0:
            progress(k + 1, len(files))
    data = {"x": np.stack(xs) if xs else np.zeros((0, N_FEATURES), np.float32),
            "mask": np.stack(ms) if ms else np.zeros((0, N_ACTIONS), bool),
            "a": np.array(acts, np.int64), "r": np.array(rs, np.float32), "player": np.array(players)}
    report["decisions"] = len(acts)
    report["by_player"] = {p: int((data["player"] == p).sum()) for p in sorted(set(players))}
    return data, report


# ---- storage and key figures -----------------------------------------------------------------

# Reward scale like in simulator: chip change / start stack (150 BB) * 10 = BB / 15
BB_TO_REWARD = 1 / 15


def datasets_dir() -> Path:
    from .nn_agent import rl_root
    return rl_root().parent / "datasets"


def dataset_file(name: str, version: str = FEATURES_VERSION) -> Path:
    """feat-1 named like before '<name>.npz', newer versions '<name>-<version>.npz'."""
    return datasets_dir() / (f"{name}.npz" if version == "feat-1" else f"{name}-{version}.npz")


def save_dataset(name: str, data: dict, report: dict, version: str = FEATURES_VERSION) -> Path:
    import json
    p = dataset_file(name, version)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(p, **data)
    p.with_suffix(".json").write_text(json.dumps({"phh_version": PHH_VERSION, "features": version, **report},
                                                 indent=2, ensure_ascii=False), "utf-8")
    return p


def load_dataset(name: str, players: list[str] | None = None, version: str = FEATURES_VERSION) -> dict:
    if version == "feat-3" and not dataset_file(name, version).exists():
        #Opponent features not in dataset: feat-2 + averages (like without observations)
        from .opponents import DEFAULT_FEATURES
        data = load_dataset(name, players, "feat-2")
        data["x"] = np.concatenate([data["x"], np.tile(DEFAULT_FEATURES, (len(data["x"]), 1))], 1)
        return data
    with np.load(dataset_file(name, version)) as z:
        data = {k: z[k] for k in z.files}
    if players:
        keep = np.isin(data["player"], players)
        data = {k: v[keep] for k, v in data.items()}
    data["r"] = (data["r"] * BB_TO_REWARD).astype(np.float32)
    return data


def forward_batch(w: dict, X: np.ndarray, M: np.ndarray) -> np.ndarray:
    na = w["bp"].shape[0]
    if M.shape[1] < na:                  # Dataset with 6 actions, network with 8: no new actions appeared there
        M = np.concatenate([M, np.zeros((len(M), na - M.shape[1]), bool)], 1)
    h = np.maximum(X @ w["w1"].T + w["b1"], 0)
    h = np.maximum(h @ w["w2"].T + w["b2"], 0)
    logits = np.where(M, h @ w["wp"].T + w["bp"], -1e9)
    logits -= logits.max(1, keepdims=True)
    p = np.exp(logits) * M
    return p / p.sum(1, keepdims=True)


def agreement(w: dict, data: dict) -> dict:
    """How well does a network predict the decisions in the dataset?
    top1 = most likely action matches; prob = average probability for the true action."""
    p = forward_batch(w, data["x"], data["mask"])
    a = data["a"]
    top = p.argmax(1)
    names = ("fold", "call", "raise_half", "raise_pot", "raise_2pot", "allin")
    return {"decisions": int(len(a)), "top1": round(float((top == a).mean()), 4),
            "prob": round(float(p[np.arange(len(a)), a].mean()), 4),
            "per_action": {nm: round(float((top[a == k] == k).mean()), 3) for k, nm in enumerate(names)
                           if (a == k).any()}}
