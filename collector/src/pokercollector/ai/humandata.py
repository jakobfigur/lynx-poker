"""HandHQ showdown decisions with known cards -> training data for a human policy network (lever H11).

HandHQ (PHH format, .phhs = many hands per file, 25NL PokerStars/Party 2009, obfuscated names) knows the
hole cards only if they were shown at showdown ('p3 sm AhKd'). From these players every decision
in the hand is collected: the hand is replayed with our engine (like phh.replay for Pluribus), at every
decision of a shown player the same observation arises as at the Blueprint, from which features
(features.py, feat-2) and the action grid (from_action, 8 actions) are derived. A net trained on this has
the same interface as the Blueprint and fits without modification as an opponent model in bpranges (ranges=human).

Bias: showdown hands are not all hands (folding early shows no cards). Preflop ranges therefore
come from the unbiased statistics of all hands (humans.py), the CONDITIONAL postflop ranges
(from which hands a normal player bets/calls/raises in this situation) come from the showdowns.
Each line provides metadata (street, position, pot, to_call, stack, action, hand class, player) to later
measure and weight the bias.

Pilot study 30.10. (40 of 5,989 files): 21.7% of hands with shown cards, extrapolated 1.24 million
showdown hands and 7.5 million decisions with cards (pre 2.2 / flop 2.1 / turn 1.8 / river 1.5 million).
No persons, no own recordings; source approved according to PROJECT HANDOVER (PHH/HandHQ).
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from ..poker import FULL_DECK
from .engine import Hand, IllegalAction
from .features import FEATURE_SIZES, action_mask, features, from_action
from .observation import Action, clamp_action
from .tables import all_classes, hand_class

HUMANDATA_VERSION = "humandata-1"
FEATURES = "feat-2"
N_ACTIONS = 8
SCALE = 100                     # Dollars -> cents: the engine calculates in whole chips
STREETS = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}
CLASS_ID = {c: i for i, c in enumerate(all_classes())}
META_FIELDS = ("street", "position", "n_players", "n_live", "pot_bb", "to_call_bb", "stack_bb", "kind",
               "amount_bb", "hole_class", "player", "hand")
KIND_ID = {"fold": 0, "check": 1, "call": 2, "raise": 3}


def _split(cards: str) -> list[str]:
    return [cards[i:i + 2] for i in range(0, len(cards), 2)]


def _deck(holes: list[list[str] | None], board: list[str], seed: int) -> list[str]:
    import random
    used = {c for h in holes if h for c in h} | set(board)
    rest = [c for c in FULL_DECK if c not in used]
    random.Random(seed).shuffle(rest)
    deck: list[str | None] = [None] * 52
    for i, h in enumerate(holes):
        if h:
            deck[2 * i], deck[2 * i + 1] = h
    for k, c in enumerate(board[:5]):
        deck[20 + k] = c
    it = iter(rest)
    return [c if c is not None else next(it) for c in deck]


def replay_handhq(hand: dict, hand_no: int = 0, version: str = FEATURES, n_actions: int = N_ACTIONS):
    """Replay one HandHQ hand. Return (ok, problem, samples); samples = list
    (x float32, mask bool, action int, meta dict) only for players with shown cards."""
    if hand.get("variant") != "NT":
        return False, "Variante", []
    blinds = hand.get("blinds_or_straddles") or []
    if len(blinds) < 2 or any(float(b) for b in blinds[2:]) or any(float(a) for a in (hand.get("antes") or [])):
        return False, "Antes/Straddles", []
    starts = hand.get("starting_stacks") or []
    players = hand.get("players") or []
    n = len(players)
    if n < 2 or len(starts) != n:
        return False, "Spieler", []
    holes: list[list[str] | None] = [None] * n
    board: list[str] = []
    for a in hand.get("actions") or []:
        p = a.split()
        if p[0] == "d" and p[1] == "db" and len(p) > 2:
            board += _split(p[2])
        elif p[0].startswith("p") and len(p) > 2 and p[1] == "sm" and "?" not in p[2]:
            s = int(p[0][1:]) - 1
            if 0 <= s < n:
                holes[s] = _split(p[2])
    if not any(holes):
        return False, 'no cards', []
    if len(set(c for h in holes if h for c in h) | set(board)) != sum(2 for h in holes if h) + len(board):
        return False, "Kartenkonflikt", []
    stacks = [int(round(float(s) * SCALE)) for s in starts]
    sb, bb = int(round(float(blinds[0]) * SCALE)), int(round(float(blinds[1]) * SCALE))
    if bb <= 0 or min(stacks) <= 0:
        return False, "Stacks/Blinds", []
    button = 0 if n == 2 else n - 1            # PHH: p1 = SB, p2 = BB, last = Button; heads-up SB is the Button
    try:
        h = Hand(stacks, button, sb, bb, deck=_deck(holes, board, hand_no), hand_id=f"hq-{hand_no}")
    except (ValueError, IllegalAction) as e:
        return False, f"Engine: {e}", []
    known = {i for i, x in enumerate(holes) if x}
    samples = []
    for a in hand.get("actions") or []:
        p = a.split()
        if p[0] == "d" or len(p) < 2 or p[1] == "sm" or not p[0].startswith("p"):
            continue
        seat = int(p[0][1:]) - 1
        if h.done:
            return False, 'Action after hand ended', []
        if h.to_act != seat:
            return False, "Reihenfolge", []
        obs = h.observation(seat)
        if p[1] == "f":
            act = Action.fold()
        elif p[1] == "cc":
            act = Action.check() if obs.can_check else Action.call()
        elif p[1] == "cbr" and len(p) > 2:
            act = Action.raise_to(int(round(float(p[2]) * SCALE)))
        else:
            return False, "Aktion", []
        legal = clamp_action(obs, act)
        if legal != act and not (act.kind == "fold" and obs.can_check):
            return False, 'not compliant with rules', []
        if seat in known:
            pot = max(obs.pot, 1)
            live = [s for s in range(n) if obs.in_hand[s] and not obs.folded[s]]
            meta = {"street": STREETS[obs.street], "position": obs.position(), "n_players": n, "n_live": len(live),
                    "pot_bb": obs.pot / bb, "to_call_bb": obs.to_call / bb, "stack_bb": obs.my_stack / bb,
                    "kind": KIND_ID[legal.kind], "amount_bb": (legal.amount or 0) / bb if legal.kind == "raise" else 0.0,
                    "hole_class": CLASS_ID[hand_class(holes[seat])], "player": str(players[seat]), "hand": hand_no}
            samples.append((features(obs, version=version), action_mask(obs, n_actions),
                            from_action(obs, legal, n_actions), meta))
        try:
            h.apply(seat, legal)
        except IllegalAction as e:
            return False, f"Engine: {e}", []
    return True, None, samples


def iter_file(path: Path):
    import tomllib
    try:
        doc = tomllib.loads(path.read_text("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return
    for k in sorted(doc, key=lambda x: int(x) if x.isdigit() else 0):
        if isinstance(doc[k], dict):
            yield doc[k]


def _process_files(args):
    files, shard_no, version, n_actions = args
    xs, ms, acts, metas = [], [], [], []
    report = {"hands": 0, "with_cards": 0, "ok": 0, "problems": {}}
    hand_no = shard_no * 10_000_000
    for f in files:
        for hand in iter_file(f):
            hand_no += 1
            report["hands"] += 1
            ok, problem, samples = replay_handhq(hand, hand_no, version, n_actions)
            if problem == 'no cards':
                continue
            report["with_cards"] += 1
            if not ok:
                key = (problem or "?").split(":")[0]
                report["problems"][key] = report["problems"].get(key, 0) + 1
                continue
            report["ok"] += 1
            for x, m, a, meta in samples:
                xs.append(x), ms.append(m), acts.append(a), metas.append(meta)
    players = sorted({m["player"] for m in metas})
    pid = {p: i for i, p in enumerate(players)}
    out = {"x": np.stack(xs).astype(np.float16) if xs else np.zeros((0, FEATURE_SIZES[version]), np.float16),
           "mask": np.stack(ms) if ms else np.zeros((0, n_actions), bool),
           "a": np.array(acts, np.int8)}
    for k in META_FIELDS:
        if k == "player":
            out["player"] = np.array([pid[m["player"]] for m in metas], np.int32)
        elif k in ("pot_bb", "to_call_bb", "stack_bb", "amount_bb"):
            out[k] = np.array([m[k] for m in metas], np.float32)
        else:
            out[k] = np.array([m[k] for m in metas], np.int32)
    out["players"] = json.dumps(players)
    report["decisions"] = len(acts)
    return shard_no, out, report


def extract(files: list[Path], out_dir: Path | str, workers: int = 2, files_per_shard: int = 50,
            version: str = FEATURES, n_actions: int = N_ACTIONS, progress=None) -> dict:
    """Replay all files, every files_per_shard files one shard human-<nr>.npz (already existing shards
    are skipped: resume). Return: overall report."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks = [files[i:i + files_per_shard] for i in range(0, len(files), files_per_shard)]
    jobs = [(c, k, version, n_actions) for k, c in enumerate(chunks) if not (out_dir / f"human-{k:04d}.npz").exists()]
    total = {"hands": 0, "with_cards": 0, "ok": 0, "decisions": 0, "problems": {}, "shards": len(chunks),
             "skipped_existing": len(chunks) - len(jobs), "version": HUMANDATA_VERSION, "features": version,
             "n_actions": n_actions}
    t0 = time.time()

    def take(shard_no, out, rep):
        meta = {**rep, "shard": shard_no, "files": len(chunks[shard_no]), "version": HUMANDATA_VERSION,
                "features": version, "n_actions": n_actions}
        np.savez_compressed(out_dir / f"human-{shard_no:04d}.npz", **out, meta=json.dumps(meta))
        for k in ("hands", "with_cards", "ok", "decisions"):
            total[k] += rep[k]
        for k, v in rep["problems"].items():
            total["problems"][k] = total["problems"].get(k, 0) + v
        if progress:
            progress(shard_no, len(chunks), total, time.time() - t0)

    if workers > 1:
        with ProcessPoolExecutor(workers) as ex:
            for shard_no, out, rep in ex.map(_process_files, jobs):
                take(shard_no, out, rep)
    else:
        for j in jobs:
            take(*_process_files(j))
    total["elapsed_s"] = time.time() - t0
    (out_dir / "report.json").write_text(json.dumps(total, indent=1, ensure_ascii=False), "utf-8")
    return total


def load(out_dir: Path | str, max_shards: int | None = None) -> dict:
    """Merge shards (x float16, mask, a, metadata; player gets renumbered per shard ->
    here uniquely as 'player_key' = shard*1e6 + id)."""
    out_dir = Path(out_dir)
    files = sorted(out_dir.glob("human-*.npz"))[:max_shards]
    parts = [np.load(f, allow_pickle=False) for f in files]
    d = {k: np.concatenate([p[k] for p in parts]) for k in ("x", "mask", "a") + META_FIELDS}
    d["player_key"] = np.concatenate([p["player"].astype(np.int64) + 1_000_000 * i for i, p in enumerate(parts)])
    d["meta"] = [json.loads(str(p["meta"])) for p in parts]
    return d


# ---- Second extraction: ALL decisions without card knowledge (fold model, H11 step 2b) -------------------
# The first extraction knows no folds (those who fold do not show cards). Here every decision of every player
# is stored with a card-free public state: from this P(fold | state) and, with the shown
# cards of the non-folders, the distribution of continuing hands -> fold probability per hand class
# as Bayes remainder: P(cont | c, s) = P(c | s, cont) * P(cont | s) / P(c | s).

PUBLIC_FIELDS = ("street", "position", "n_players", "n_live", "pot_bb", "to_call_bb", "stack_bb", "raises_street",
                 "raises_pre", "facing", "aggressor", "board_paired", "board_suited", "board_high", "kind",
                 "amount_bb", "hole_class", "hand")


def public_rows(hand: dict, hand_no: int = 0):
    """All decisions of a HandHQ hand as card-free state lines (hole_class -1 = unknown)."""
    from ..poker import RANKS
    if hand.get("variant") != "NT":
        return False, "Variante", []
    blinds = hand.get("blinds_or_straddles") or []
    if len(blinds) < 2 or any(float(b) for b in blinds[2:]) or any(float(a) for a in (hand.get("antes") or [])):
        return False, "Antes/Straddles", []
    starts = hand.get("starting_stacks") or []
    players = hand.get("players") or []
    n = len(players)
    if n < 2 or len(starts) != n:
        return False, "Spieler", []
    holes: list[list[str] | None] = [None] * n
    board: list[str] = []
    for a in hand.get("actions") or []:
        p = a.split()
        if p[0] == "d" and p[1] == "db" and len(p) > 2:
            board += _split(p[2])
        elif p[0].startswith("p") and len(p) > 2 and p[1] == "sm" and "?" not in p[2]:
            s = int(p[0][1:]) - 1
            if 0 <= s < n:
                holes[s] = _split(p[2])
    stacks = [int(round(float(s) * SCALE)) for s in starts]
    sb, bb = int(round(float(blinds[0]) * SCALE)), int(round(float(blinds[1]) * SCALE))
    if bb <= 0 or min(stacks) <= 0:
        return False, "Stacks/Blinds", []
    button = 0 if n == 2 else n - 1
    try:
        h = Hand(stacks, button, sb, bb, deck=_deck(holes, board, hand_no), hand_id=f"hq-{hand_no}")
    except (ValueError, IllegalAction) as e:
        return False, f"Engine: {e}", []
    rows = []
    for a in hand.get("actions") or []:
        p = a.split()
        if p[0] == "d" or len(p) < 2 or p[1] == "sm" or not p[0].startswith("p"):
            continue
        seat = int(p[0][1:]) - 1
        if h.done or h.to_act != seat:
            return False, "Reihenfolge", []
        obs = h.observation(seat)
        if p[1] == "f":
            act = Action.fold()
        elif p[1] == "cc":
            act = Action.check() if obs.can_check else Action.call()
        elif p[1] == "cbr" and len(p) > 2:
            act = Action.raise_to(int(round(float(p[2]) * SCALE)))
        else:
            return False, "Aktion", []
        legal = clamp_action(obs, act)
        if legal != act and not (act.kind == "fold" and obs.can_check):
            return False, 'not compliant with rules', []
        live = [s for s in range(n) if obs.in_hand[s] and not obs.folded[s]]
        st_acts = obs.street_actions()
        aggressors = [x.seat for x in obs.history if x.kind in ("bet", "raise")]
        b = obs.board
        ranks = [c[0] for c in b]
        suits = [c[1] for c in b]
        rows.append({"street": STREETS[obs.street], "position": obs.position(), "n_players": n, "n_live": len(live),
                     "pot_bb": obs.pot / bb, "to_call_bb": obs.to_call / bb, "stack_bb": obs.my_stack / bb,
                     "raises_street": sum(1 for x in st_acts if x.kind in ("bet", "raise")),
                     "raises_pre": sum(1 for x in obs.street_actions("preflop") if x.kind in ("bet", "raise")),
                     "facing": int(obs.to_call > 0), "aggressor": int(bool(aggressors) and aggressors[-1] == seat),
                     "board_paired": int(len(set(ranks)) < len(ranks)) if b else 0,
                     "board_suited": max((suits.count(s) for s in set(suits)), default=0),
                     "board_high": max((RANKS.index(r) for r in ranks), default=-1),
                     "kind": KIND_ID[legal.kind],
                     "amount_bb": (legal.amount or 0) / bb if legal.kind == "raise" else 0.0,
                     "hole_class": CLASS_ID[hand_class(holes[seat])] if holes[seat] else -1, "hand": hand_no})
        try:
            h.apply(seat, legal)
        except IllegalAction as e:
            return False, f"Engine: {e}", []
    return True, None, rows


def _process_public(args):
    files, shard_no = args
    rows = []
    report = {"hands": 0, "ok": 0, "problems": {}}
    hand_no = shard_no * 10_000_000
    for f in files:
        for hand in iter_file(f):
            hand_no += 1
            report["hands"] += 1
            ok, problem, r = public_rows(hand, hand_no)
            if not ok:
                key = (problem or "?").split(":")[0]
                report["problems"][key] = report["problems"].get(key, 0) + 1
                continue
            report["ok"] += 1
            rows.extend(r)
    out = {}
    for k in PUBLIC_FIELDS:
        dt = np.float32 if k in ("pot_bb", "to_call_bb", "stack_bb", "amount_bb") else np.int32
        out[k] = np.array([r[k] for r in rows], dt)
    report["decisions"] = len(rows)
    return shard_no, out, report


def extract_public(files: list[Path], out_dir: Path | str, workers: int = 2, files_per_shard: int = 50,
                   progress=None) -> dict:
    """All decisions (with and without cards) as card-free lines, shards public-<nr>.npz."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks = [files[i:i + files_per_shard] for i in range(0, len(files), files_per_shard)]
    jobs = [(c, k) for k, c in enumerate(chunks) if not (out_dir / f"public-{k:04d}.npz").exists()]
    total = {"hands": 0, "ok": 0, "decisions": 0, "problems": {}, "shards": len(chunks), "version": HUMANDATA_VERSION}
    t0 = time.time()

    def take(shard_no, out, rep):
        np.savez_compressed(out_dir / f"public-{shard_no:04d}.npz", **out, meta=json.dumps({**rep, "shard": shard_no}))
        for k in ("hands", "ok", "decisions"):
            total[k] += rep[k]
        for k, v in rep["problems"].items():
            total["problems"][k] = total["problems"].get(k, 0) + v
        if progress:
            progress(shard_no, len(chunks), total, time.time() - t0)

    if workers > 1:
        with ProcessPoolExecutor(workers) as ex:
            for shard_no, out, rep in ex.map(_process_public, jobs):
                take(shard_no, out, rep)
    else:
        for j in jobs:
            take(*_process_public(j))
    total["elapsed_s"] = time.time() - t0
    (out_dir / "report-public.json").write_text(json.dumps(total, indent=1, ensure_ascii=False), "utf-8")
    return total


def load_public(out_dir: Path | str, max_shards: int | None = None) -> dict:
    files = sorted(Path(out_dir).glob("public-*.npz"))[:max_shards]
    parts = [np.load(f, allow_pickle=False) for f in files]
    return {k: np.concatenate([p[k] for p in parts]) for k in PUBLIC_FIELDS}
