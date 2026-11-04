"""Opponent model: statistics per opponent over previous hands (like a HUD).

Only public information from hand history (HandRecord.actions) is counted, updated after each hand via
hand_over(). Per opponent (key: name at table, else seat number):
  vpip  voluntarily put money in preflop (call/raise, blinds don’t count)
  pfr   raised preflop
  agg   fraction of bets/raises among all bets/raises/calls after the flop (aggression rate)
  ftb   fold to a bet after the flop (fraction of cases where facing a bet)
Few hands say little: every ratio starts at an average value (prior) and adjusts with
observations; 'conf' = hands / (hands + 20) tells the network the reliability of the numbers.

Features for the network (8, OPP_FEATURES): the opponent currently playing against (last aggressor
this street, else average of opponents in hand) with vpip, pfr, agg, ftb, conf, and the
average of all opponents in the hand with vpip, agg, ftb.
"""

from __future__ import annotations

import numpy as np

from .observation import Observation

PRIOR = {"vpip": (0.28, 8.0), "pfr": (0.16, 8.0), "agg": (0.45, 6.0), "ftb": (0.45, 6.0)}
CONF_HANDS = 20.0
OPP_FEATURES = 8
_KEYS = ("vpip", "pfr", "agg", "ftb")


def _prior_stats() -> dict:
    return {**{k: PRIOR[k][0] for k in _KEYS}, "conf": 0.0}


DEFAULT_FEATURES = np.array([PRIOR["vpip"][0], PRIOR["pfr"][0], PRIOR["agg"][0], PRIOR["ftb"][0], 0.0,
                             PRIOR["vpip"][0], PRIOR["agg"][0], PRIOR["ftb"][0]], np.float32)


class OpponentTracker:
    def __init__(self, fuzzy: bool = False):
        # per opponent: hands, vpip, pfr, aggr (bets/raises post flop), pas (calls post flop), ftb_n, ftb
        self.c: dict[str, dict[str, int]] = {}
        # fuzzy (live): map noisy recognized names from OCR ('Card S//"arp') to known names
        self.fuzzy = fuzzy
        self.alias: dict[str, str] = {}
        self.seat_last: dict[int, str] = {}       # who last sat in the seat (fuzzy fallback)

    def _key(self, names, seat: int) -> str:
        n = names[seat] if names and seat < len(names) else None
        if not n:
            return f"seat{seat}"
        if not self.fuzzy or n in self.c:
            return n
        if n not in self.alias:
            from difflib import SequenceMatcher
            best = max(self.c, key=lambda k: SequenceMatcher(None, k, n).ratio(), default=None)
            ok = best is not None and not best.startswith("seat") and SequenceMatcher(None, best, n).ratio() >= 0.6
            if ok:
                self.alias[n] = best
            elif seat in self.seat_last:
                return self.seat_last[seat]       # unreadable name: same seat as last time (do not remember)
            else:
                return n
        return self.alias[n]

    def _cnt(self, key: str) -> dict[str, int]:
        if key not in self.c:
            self.c[key] = {"hands": 0, "vpip": 0, "pfr": 0, "aggr": 0, "pas": 0, "ftb_n": 0, "ftb": 0}
        return self.c[key]

    def update(self, rec, me: int):
        """After each hand (simulator, HandRecord): evaluate history (me = own seat, does not count)."""
        dealt = [r.seat for r in rec.results if r.start_stack > 0]
        self._count(rec.names, dealt, [(a.street, a.seat, a.kind, a.amount_to) for a in rec.actions], me)

    def update_collector(self, hand: dict, me: int):
        """After each hand (collector, reconstructed hand as a dict like in hands.json)."""
        seats = {int(k): v for k, v in (hand.get("seats") or {}).items()}
        names = [None] * (max(seats, default=0) + 1)
        for k, v in seats.items():
            names[k] = v.get("name")
        acts = [(a["street"], a["seat"], a["type"], a.get("amount_to")) for a in hand.get("actions", [])
                if a.get("type") in ("post_sb", "post_bb", "fold", "check", "call", "bet", "raise")]
        self._count(names, list(seats), acts, me)

    def _count(self, names, dealt: list[int], actions: list[tuple], me: int):
        for seat in dealt:
            if seat != me:
                key = self._key(names, seat)
                self._cnt(key)["hands"] += 1
                self.seat_last[seat] = key
        vp, pr = set(), set()
        street, level, contrib = None, 0, {}
        for a_street, s, kind, amount_to in actions:
            if a_street != street:
                street, level, contrib = a_street, 0, {}
            facing = level > contrib.get(s, 0)
            if s != me and kind not in ("post_sb", "post_bb"):
                c = self._cnt(self._key(names, s))
                if street == "preflop":
                    if kind in ("call", "bet", "raise"):
                        vp.add(s)
                    if kind in ("bet", "raise"):
                        pr.add(s)
                else:
                    if kind in ("bet", "raise"):
                        c["aggr"] += 1
                    elif kind == "call":
                        c["pas"] += 1
                    if facing:
                        c["ftb_n"] += 1
                        c["ftb"] += kind == "fold"
            if amount_to is not None:
                contrib[s] = amount_to
                level = max(level, amount_to)
        for s in vp:
            self._cnt(self._key(names, s))["vpip"] += 1
        for s in pr:
            self._cnt(self._key(names, s))["pfr"] += 1

    def stats(self, key: str) -> dict:
        c = self.c.get(key)
        if not c:
            return _prior_stats()

        def rate(name, hits, n):
            p, k = PRIOR[name]
            return (hits + p * k) / (n + k)

        return {"vpip": rate("vpip", c["vpip"], c["hands"]), "pfr": rate("pfr", c["pfr"], c["hands"]),
                "agg": rate("agg", c["aggr"], c["aggr"] + c["pas"]), "ftb": rate("ftb", c["ftb"], c["ftb_n"]),
                "conf": c["hands"] / (c["hands"] + CONF_HANDS), "hands": c["hands"]}

    def features(self, obs: Observation) -> np.ndarray:
        opps = [s for s in range(obs.num_seats)
                if s != obs.seat and obs.in_hand[s] and not obs.folded[s]]
        if not opps:
            return DEFAULT_FEATURES.copy()
        st = {s: self.stats(self._key(obs.names, s)) for s in opps}
        avg = {k: float(np.mean([st[s][k] for s in opps])) for k in (*_KEYS, "conf")}
        aggr = [a.seat for a in obs.street_actions() if a.kind in ("bet", "raise") and a.seat in st]
        t = st[aggr[-1]] if aggr else avg
        return np.array([t["vpip"], t["pfr"], t["agg"], t["ftb"], t["conf"],
                         avg["vpip"], avg["agg"], avg["ftb"]], np.float32)


def describe(st: dict) -> str:
    """Brief display like a HUD: 'H 23  VPIP 35 %  PFR 12 %  Agg 40 %  FvB 55 %'."""
    return (f"H {st.get('hands', 0):3d}  VPIP {st['vpip']:4.0%}  PFR {st['pfr']:4.0%}  "
            f"Agg {st['agg']:4.0%}  FvB {st['ftb']:4.0%}")
