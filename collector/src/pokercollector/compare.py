"""Field-wise comparison of the visual reconstruction with the reference export.

The comparison only runs after the visual reconstruction is finalized
(hands.json). Information present in the export but not visible (e.g.,
hidden opponent cards) is classified as 'not visible' and not counted as
recognition errors.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .reference import RefHand

COMPARE_VERSION = "compare-1"


def _norm_name(n: str | None) -> str:
    if not n:
        return ""
    n = n.replace("...", "").replace("…", "")
    return re.sub(r"[^a-z0-9]", "", n.lower())


def map_seats(visual_hands: list[dict], ref_hands: list[RefHand]) -> dict[int, int]:
    """Visual seat -> reference seat via player names (prefix, since names may be truncated)."""
    vis_names: dict[int, Counter] = defaultdict(Counter)
    for h in visual_hands:
        for s, si in h.get("seats", {}).items():
            if si.get("name"):
                vis_names[int(s)][_norm_name(si["name"])] += 1
    ref_names: dict[str, set[int]] = defaultdict(set)
    for h in ref_hands:
        for s, si in h.seats.items():
            if si.get("name"):
                ref_names[_norm_name(si["name"])].add(s)
    mapping = {}
    for vs, cnt in vis_names.items():
        name = cnt.most_common(1)[0][0]
        if not name:
            continue
        cands = [rn for rn in ref_names if rn.startswith(name) or name.startswith(rn)]
        seats = set().union(*(ref_names[c] for c in cands)) if cands else set()
        if len(seats) == 1:
            mapping[vs] = next(iter(seats))
    return mapping


@dataclass
class FieldTally:
    match: int = 0
    mismatch: int = 0
    missing: int = 0       # in reference, not visually detected
    extra: int = 0         # visually detected, not in reference
    not_visible: int = 0   # in reference but was not visible

    def add(self, kind: str):
        setattr(self, kind, getattr(self, kind) + 1)

    def as_dict(self):
        d = self.__dict__.copy()
        judged = self.match + self.mismatch + self.missing + self.extra
        d["precision"] = round(self.match / (self.match + self.mismatch + self.extra), 3) if (
            self.match + self.mismatch + self.extra) else None
        d["recall"] = round(self.match / (self.match + self.mismatch + self.missing), 3) if (
            self.match + self.mismatch + self.missing) else None
        d["judged"] = judged
        return d


@dataclass
class CompareResult:
    seat_map: dict[int, int]
    hands_visual: int
    hands_reference: int
    hands_matched: int
    tallies: dict[str, FieldTally] = field(default_factory=lambda: defaultdict(FieldTally))
    amount_semantics: Counter = field(default_factory=Counter)
    details: list[dict] = field(default_factory=list)

    def to_dict(self):
        return {
            "compare_version": COMPARE_VERSION,
            "seat_map": {str(k): v for k, v in self.seat_map.items()},
            "hands_visual": self.hands_visual,
            "hands_reference": self.hands_reference,
            "hands_matched": self.hands_matched,
            "fields": {k: v.as_dict() for k, v in sorted(self.tallies.items())},
            "amount_semantics": dict(self.amount_semantics),
            "details": self.details,
        }


_ACTION_TYPES = {"fold", "check", "call", "bet", "raise", "post_sb", "post_bb", "allin"}


def _align(vis: list[dict], ref: list) -> list[tuple]:
    """ LCS alignment of two action sequences over (seat, coarse type)."""

    def key_v(a):
        return (a["ref_seat"], "aggr" if a["type"] in ("bet", "raise") else a["type"])

    def key_r(a, allin_as=None):
        t = a.type
        if t == "allin":
            t = allin_as or "aggr"
        return (a.seat, "aggr" if t in ("bet", "raise") else t)

    n, m = len(vis), len(ref)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            same = key_v(vis[i])[0] == ref[j].seat and (
                key_v(vis[i]) == key_r(ref[j]) or (ref[j].type == "allin" and vis[i].get("allin")))
            dp[i][j] = dp[i + 1][j + 1] + 1 if same else max(dp[i + 1][j], dp[i][j + 1])
    out, i, j = [], 0, 0
    while i < n and j < m:
        same = key_v(vis[i])[0] == ref[j].seat and (
            key_v(vis[i]) == key_r(ref[j]) or (ref[j].type == "allin" and vis[i].get("allin")))
        if same:
            out.append((vis[i], ref[j]))
            i, j = i + 1, j + 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            out.append((vis[i], None))
            i += 1
        else:
            out.append((None, ref[j]))
            j += 1
    out += [(v, None) for v in vis[i:]] + [(None, r) for r in ref[j:]]
    return out


def compare(visual_hands: list[dict], ref_hands: list[RefHand], hero_seat_visual: int = 0) -> CompareResult:
    seat_map = map_seats(visual_hands, ref_hands)
    ref_by_id = defaultdict(list)
    for r in ref_hands:
        ref_by_id[r.hand_id].append(r)
    res = CompareResult(seat_map, len(visual_hands), len(ref_hands), 0)
    T = res.tallies
    used = set()
    for vh in visual_hands:
        hid = vh.get("hand_no")
        cands = [r for r in ref_by_id.get(hid, []) if id(r) not in used] if hid is not None else []
        if len(cands) > 1 and vh.get("game_no") is not None:
            cands = [r for r in cands if r.game_id == vh["game_no"]] or cands
        detail = {"visual_hand": hid, "game": vh.get("game_no"), "status": vh.get("status"), "issues": []}
        if not cands:
            detail["issues"].append('no matching reference hand (hand number)')
            res.details.append(detail)
            T["hand"].add("extra")
            continue
        if len(cands) > 1:
            detail["issues"].append(f"{len(cands)} reference hands with number {hid} - ambiguous, first taken")
        rh = cands[0]
        used.add(id(rh))
        res.hands_matched += 1
        T["hand"].add("match")

        def seat_cmp(fieldname, vis_seat, ref_seat):
            if ref_seat is None:
                return
            if vis_seat is None:
                T[fieldname].add("missing")
                detail["issues"].append(f"{fieldname}: not recognized (reference seat {ref_seat})")
            elif seat_map.get(vis_seat) == ref_seat:
                T[fieldname].add("match")
            else:
                T[fieldname].add("mismatch")
                detail["issues"].append(f"{fieldname}: visual seat {vis_seat} -> {seat_map.get(vis_seat)}, reference {ref_seat}")

        seat_cmp("dealer", vh.get("dealer"), rh.dealer_seat)
        seat_cmp("sb_seat", vh.get("sb_seat"), rh.sb_seat)
        seat_cmp("bb_seat", vh.get("bb_seat"), rh.bb_seat)

        if rh.blinds and all(b is not None for b in rh.blinds):
            vb = vh.get("blinds")
            if vb is None:
                T["blinds"].add("missing")
            elif list(vb) == list(rh.blinds):
                T["blinds"].add("match")
            else:
                T["blinds"].add("mismatch")
                detail["issues"].append(f"Blinds: visual {vb}, reference {rh.blinds}")

        # Starting stacks
        for vs, si in vh.get("seats", {}).items():
            rs = seat_map.get(int(vs))
            if rs is None or rs not in rh.seats:
                continue
            ref_cash = rh.seats[rs].get("cash")
            if ref_cash is None:
                continue
            if si.get("start_stack") is None:
                T["start_stack"].add("missing")
            elif si["start_stack"] == ref_cash:
                T["start_stack"].add("match")
            else:
                T["start_stack"].add("mismatch")
                detail["issues"].append(f"Start stack seat {vs}: visual {si['start_stack']}, reference {ref_cash}")

        # Cards: own always visible; opponents’ only at showdown
        for vs, si in vh.get("seats", {}).items():
            rs = seat_map.get(int(vs))
            if rs is None or rs not in rh.seats:
                continue
            ref_cards = rh.seats[rs].get("cards")
            vis_cards = si.get("cards")
            fname = "hero_cards" if int(vs) == hero_seat_visual else "shown_cards"
            if ref_cards is None:
                if vis_cards:
                    T[fname].add("extra")
                continue
            if vis_cards is None:
                T[fname].add("missing" if fname == "hero_cards" else "not_visible")
                continue
            if sorted(vis_cards) == sorted(ref_cards):
                T[fname].add("match")
            else:
                T[fname].add("mismatch")
                detail["issues"].append(f"Cards seat {vs}: visual {vis_cards}, reference {ref_cards}")

        # Board
        vb = vh.get("board") or [None] * 5
        for i, rc in enumerate(rh.board[:5]):
            vc = vb[i] if i < len(vb) else None
            if rc is None:
                if vc is not None:
                    T["board"].add("extra")
                continue
            if vc is None or vc == "??":
                T["board"].add("missing")
            elif vc == rc:
                T["board"].add("match")
            else:
                T["board"].add("mismatch")
                detail["issues"].append(f"Board {i + 1}: visual {vc}, reference {rc}")

        # Actions per street
        for street in ("preflop", "flop", "turn", "river"):
            vis = [dict(a, ref_seat=seat_map.get(a["seat"])) for a in vh.get("actions", [])
                   if a["street"] == street and a["type"] in _ACTION_TYPES]
            ref = [a for a in rh.actions if a.street == street and a.type in _ACTION_TYPES]
            for va, ra in _align(vis, ref):
                if va and ra:
                    T["action"].add("match")
                    if ra.amount is not None and va.get("amount_to") is not None:
                        if ra.amount == va.get("amount_to"):
                            res.amount_semantics["referenz=gesamt_auf"] += 1
                            T["action_amount"].add("match")
                        elif ra.amount == va.get("added"):
                            res.amount_semantics["referenz=zusaetzlich"] += 1
                            T["action_amount"].add("match")
                        else:
                            T["action_amount"].add("mismatch")
                            detail["issues"].append(
                                f"{street} seat {va['seat']} {va['type']}: amount visual at {va.get('amount_to')}"
                                f" (+{va.get('added')}), reference {ra.amount}")
                elif ra:
                    T["action"].add("missing")
                    detail["issues"].append(f"{street}: reference action missing visually: seat {ra.seat} {ra.raw} {ra.amount}")
                else:
                    T["action"].add("extra")
                    detail["issues"].append(f"{street}: visual action without reference: seat {va['seat']} {va['type']}")

        # Winner
        ref_win = {a.seat for a in rh.actions if a.type == "collect"}
        vis_win = {seat_map.get(a["seat"]) for a in vh.get("actions", []) if a["type"] == "collect"}
        for s in ref_win | vis_win:
            if s in ref_win and s in vis_win:
                T["winner"].add("match")
            elif s in ref_win:
                T["winner"].add("missing")
            else:
                T["winner"].add("extra")
        res.details.append(detail)
    for rh in ref_hands:
        if id(rh) not in used:
            T["hand"].add("missing")
    return res
