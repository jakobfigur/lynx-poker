"""Tournament mode (Sit & Go like PokerTH).

- All start with the same stack; blinds increase after `hands_per_level` hands
  (doubling or fixed list).
- Players who lose all chips are eliminated. If multiple are eliminated in the same hand,
  the one with the larger stack at hand start gets the better placement
  (in case of tie they share the place mathematically: equal average payouts).
- The button moves to the next seat with chips (simple "moving button").
- Play continues until one player has all chips; `max_hands` is a safety brake,
  then players are placed according to chips and result marked as aborted.

The values from PokerTH (start stack, blind structure) are adjustable in-game; the
screenshot showed 3000 start chips and blinds 10/20 with "↑8" displayed - probably
hands until next increase, not verified.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from .engine import HandRecord, play_hand
from .evaluate import AgentStats, _tally, t95

TOURNAMENT_VERSION = "tournament-1"


@dataclass(frozen=True)
class BlindSchedule:
    small_blind: int = 10
    big_blind: int = 20
    hands_per_level: int = 10
    mode: str = "double"                       # 'double' | 'list'
    levels: tuple[tuple[int, int], ...] = ()   # in mode='list': (sb, bb) per level; then last level doubled

    def at(self, hand_no: int) -> dict:
        """Blinds for hand number hand_no (0-based)."""
        lvl = hand_no // self.hands_per_level
        if self.mode == "list" and self.levels:
            if lvl < len(self.levels):
                sb, bb = self.levels[lvl]
            else:
                sb, bb = self.levels[-1]
                f = 2 ** (lvl - len(self.levels) + 1)
                sb, bb = sb * f, bb * f
        else:
            sb, bb = self.small_blind * 2 ** lvl, self.big_blind * 2 ** lvl
        return {"level": lvl, "sb": sb, "bb": bb,
                "hands_to_next_level": self.hands_per_level - hand_no % self.hands_per_level}


@dataclass(frozen=True)
class TournamentConfig:
    start_stack: int = 3000
    blinds: BlindSchedule = BlindSchedule()
    payouts: tuple[float, ...] = (0.5, 0.3, 0.2)   # Proportion of prize money per place (1st, 2nd, ...)
    max_hands: int = 3000

    def payout_for_place(self, place: int, players: int) -> float:
        """Payout in buy-ins: prize money = players * buy-ins."""
        if place - 1 < len(self.payouts):
            return self.payouts[place - 1] * players
        return 0.0


# PokerTH web standard (from log on 26.10.2026): 1000 chips, 10/20, increase after 9 hands
POKERTH_DEFAULT = TournamentConfig(start_stack=1000, blinds=BlindSchedule(10, 20, 9))

# Random formats for training: the bot should be able to handle any table size and pace
PLAYER_WEIGHTS = {2: 1.5, 3: 1.0, 4: 1.0, 5: 1.0, 6: 2.0, 7: 1.0, 8: 1.0, 9: 1.5, 10: 1.5}
HANDS_PER_LEVEL = (5, 6, 8, 9, 10, 12, 15, 20)


def random_players(rng, weights: dict[int, float] | None = None) -> int:
    w = weights or PLAYER_WEIGHTS
    return rng.choices(list(w), weights=list(w.values()))[0]


def random_config(rng, players: int) -> TournamentConfig:
    """Start stack 20-200 BB (log-uniform, often 50 BB like in PokerTH), blind tempo 5-20 hands,
    payout matches player count."""
    import math
    start_bb = 50 if rng.random() < 0.25 else int(round(math.exp(rng.uniform(math.log(20), math.log(200)))))
    if players <= 3:
        payouts = rng.choice([(1.0,), (0.65, 0.35)]) if players == 3 else (1.0,)
    elif players <= 6:
        payouts = rng.choice([(0.65, 0.35), (0.5, 0.3, 0.2), (1.0,)])
    else:
        payouts = rng.choice([(0.5, 0.3, 0.2), (0.45, 0.27, 0.18, 0.1), (0.65, 0.35)])
    return TournamentConfig(start_stack=start_bb * 20, blinds=BlindSchedule(10, 20, rng.choice(HANDS_PER_LEVEL)),
                            payouts=payouts)


@dataclass
class TournamentResult:
    seed: int
    names: list[str]
    places: list[float]          # Place by place index (1 = winner); average if shared place
    payouts: list[float]         # Payout in buy-ins by place index
    hands: int
    eliminations: list[dict]     # {hand, seat, name, place}
    finished: bool               # False = safety brake max_hands
    final_level: dict = field(default_factory=dict)
    records: list[HandRecord] = field(default_factory=list)


def _assign_places(busted: list[int], start_stacks: list[int], next_place: int, places: dict[int, float],
                   payout_of) -> dict[int, float]:
    """Multiple eliminated in one hand: larger start stack = better place; ties share.
    Returns payouts for these places."""
    pays = {}
    groups: dict[int, list[int]] = {}
    for s in busted:
        groups.setdefault(start_stacks[s], []).append(s)
    place = next_place - len(busted) + 1                 # best place to assign
    for stack in sorted(groups, reverse=True):
        members = groups[stack]
        span = list(range(place, place + len(members)))
        avg_place = sum(span) / len(span)
        avg_pay = sum(payout_of(p) for p in span) / len(span)
        for s in members:
            places[s] = avg_place
            pays[s] = avg_pay
        place += len(members)
    return pays


def play_tournament(agents: list, config: TournamentConfig = TournamentConfig(), seed: int = 0,
                    keep_records: bool = False, on_hand=None, stop=None) -> TournamentResult:
    """stop(stacks) -> True ends after the hand (e.g. training: learning bot is out)."""
    n = len(agents)
    names = [a.name for a in agents]
    stacks = [config.start_stack] * n
    places: dict[int, float] = {}
    payouts = [0.0] * n
    eliminations = []
    button = seed % n
    records = []
    hand_no = 0
    lv = config.blinds.at(0)
    while sum(1 for s in stacks if s > 0) > 1 and hand_no < config.max_hands:
        lv = config.blinds.at(hand_no)
        alive = [s for s in range(n) if stacks[s] > 0]
        info = {**lv, "players_left": len(alive), "start_players": n,
                "average_stack": round(sum(stacks) / len(alive)), "payouts": list(config.payouts),
                "hand_no": hand_no}
        before = list(stacks)
        rec = play_hand(agents, stacks, button, lv["sb"], lv["bb"], seed=seed * 1_000_003 + hand_no,
                        hand_id=f"T{seed}-{hand_no}", names=names, tournament=info)
        stacks = [r.end_stack for r in rec.results]
        if keep_records:
            records.append(rec)
        if on_hand:
            on_hand(rec, hand_no, before)
        busted = [s for s in range(n) if before[s] > 0 and stacks[s] == 0]
        if busted:
            next_place = sum(1 for s in stacks if s > 0) + len(busted)    # worst yet free place
            pays = _assign_places(busted, before, next_place, places,
                                  lambda p: config.payout_for_place(p, n))
            for s in busted:
                payouts[s] = pays[s]
                eliminations.append({"hand": hand_no, "seat": s, "name": names[s], "place": places[s]})
        hand_no += 1
        if stop and stop(stacks):
            break
        button = next((button + k) % n for k in range(1, n + 1) if stacks[(button + k) % n] > 0)
    finished = sum(1 for s in stacks if s > 0) == 1
    # Assign remaining (winner or by chips if safety brake) places
    remaining = sorted((s for s in range(n) if s not in places), key=lambda s: -stacks[s])
    place = 1
    i = 0
    while i < len(remaining):
        same = [s for s in remaining[i:] if stacks[s] == stacks[remaining[i]]]
        span = list(range(place, place + len(same)))
        for s in same:
            places[s] = sum(span) / len(span)
            payouts[s] = sum(config.payout_for_place(p, n) for p in span) / len(span)
        place += len(same)
        i += len(same)
    assert sum(stacks) == config.start_stack * n
    return TournamentResult(seed, names, [places[s] for s in range(n)], payouts, hand_no, eliminations,
                            finished, lv, records)


@dataclass
class TournamentStats:
    name: str
    tournaments: int = 0
    place_sum: float = 0.0
    wins: float = 0.0
    itm: int = 0
    hands_survived: int = 0
    per_unit: list[float] = field(default_factory=list)   # Net in buy-ins per sample unit

    def result(self, per_unit_tournaments: int) -> dict:
        n = len(self.per_unit)
        mean = sum(self.per_unit) / n if n else 0.0
        var = sum((x - mean) ** 2 for x in self.per_unit) / (n - 1) if n > 1 else float("nan")
        se = math.sqrt(var / n) / per_unit_tournaments if n > 1 else float("nan")
        roi = mean / per_unit_tournaments * 100      # Net per tournament in % of buy-in
        se_roi = se * 100
        return {"agent": self.name, "tournaments": self.tournaments,
                "roi_pct": round(roi, 1), "ci95": [round(roi - t95(n) * se_roi, 1), round(roi + t95(n) * se_roi, 1)],
                "avg_place": round(self.place_sum / self.tournaments, 2) if self.tournaments else None,
                "win_pct": round(100 * self.wins / self.tournaments, 1) if self.tournaments else None,
                "itm_pct": round(100 * self.itm / self.tournaments, 1) if self.tournaments else None,
                "avg_hands_survived": round(self.hands_survived / self.tournaments, 1) if self.tournaments else None}


def run_tournaments(agents: list, count: int, config: TournamentConfig = TournamentConfig(), seed: int = 1,
                    duplicate: bool = True, progress=None, keep_example: bool = False) -> dict:
    """count tournaments; with duplicate=True each tournament card setup
    is played with all seat rotations (count * len(agents) tournaments)."""
    n = len(agents)
    names = [a.name for a in agents]
    if len(set(names)) != n:
        raise ValueError(f"Agent names must be unique: {names}")
    tstats = [TournamentStats(nm) for nm in names]
    hstats = [AgentStats(nm) for nm in names]
    rotations = range(n) if duplicate else [0]
    example = None
    t0 = time.perf_counter()
    played = hands_total = 0
    unfinished = 0
    for k in range(count):
        tseed = seed * 7919 + k
        unit = [0.0] * n
        for r in rotations:
            seat_agent = [(i + r) % n for i in range(n)]
            seated = [agents[a] for a in seat_agent]
            dummy_unit = [0.0] * n
            res = play_tournament(seated, config, seed=tseed, keep_records=keep_example and example is None,
                                  on_hand=lambda rec, hn, before, sa=seat_agent, du=dummy_unit:
                                  _tally(rec, sa, hstats, du))
            if keep_example and example is None:
                example = res
            played += 1
            hands_total += res.hands
            unfinished += 0 if res.finished else 1
            elim_hand = {e["seat"]: e["hand"] for e in res.eliminations}
            for seat, ai in enumerate(seat_agent):
                st = tstats[ai]
                st.tournaments += 1
                st.place_sum += res.places[seat]
                if res.places[seat] == 1:
                    st.wins += 1
                if res.payouts[seat] > 0:
                    st.itm += 1
                st.hands_survived += elim_hand.get(seat, res.hands)
                unit[ai] += res.payouts[seat] - 1.0
        for i in range(n):
            tstats[i].per_unit.append(unit[i])
        if progress:
            progress(k + 1, count, played, time.perf_counter() - t0)
    per_unit = n if duplicate else 1
    elapsed = time.perf_counter() - t0
    results = sorted((s.result(per_unit) for s in tstats), key=lambda d: -d["roi_pct"])
    style = {h.name: h.result(1, 1) for h in hstats}
    for r in results:
        s = style[r["agent"]]
        r.update({k: s[k] for k in ("vpip", "pfr", "aggression", "wtsd", "wsd")})
    return {
        "tournament_version": TOURNAMENT_VERSION,
        "config": {"agents": names, "schemes": count, "tournaments_played": played, "seed": seed,
                   "duplicate": duplicate, "start_stack": config.start_stack,
                   "blinds": [config.blinds.small_blind, config.blinds.big_blind],
                   "hands_per_level": config.blinds.hands_per_level, "blind_mode": config.blinds.mode,
                   "payouts": list(config.payouts)},
        "hands_total": hands_total, "avg_hands_per_tournament": round(hands_total / played, 1) if played else 0,
        "unfinished": unfinished, "elapsed_s": round(elapsed, 1),
        "results": results, "example": example,
    }


def tournaments_markdown(res: dict) -> str:
    c = res["config"]
    lines = [f"# Tournaments: {', '.join(c['agents'])}", "",
             f"{c['tournaments_played']} tournaments ({c['schemes']} card schemes"
             f"{' x seat rotation (duplicate)' if c['duplicate'] else ''}), start {c['start_stack']} chips, "
             f"blinds {c['blinds'][0]}/{c['blinds'][1]} {'doubling' if c['blind_mode'] == 'double' else 'by list'} "
             f"every {c['hands_per_level']} hands, payout {', '.join(f'{p:.0%}' for p in c['payouts'])}",
             f"Avg {res['avg_hands_per_tournament']} hands per tournament, {res['elapsed_s']} s"
             + (f", {res['unfinished']} ended by kill switch" if res["unfinished"] else ""), "",
             '| Agent | ROI % | 95% interval | Avg place | Win % | Money finishes % | Avg hands survived | VPIP | PFR |',
             "|---|---|---|---|---|---|---|---|---|"]
    for r in res["results"]:
        sig = "" if r["ci95"][0] <= 0 <= r["ci95"][1] else " *"
        lines.append(f"| {r['agent']} | {r['roi_pct']:+.1f}{sig} | {r['ci95'][0]:+.1f} .. {r['ci95'][1]:+.1f} "
                     f"| {r['avg_place']} | {r['win_pct']} | {r['itm_pct']} | {r['avg_hands_survived']} "
                     f"| {r['vpip']} | {r['pfr']} |")
    lines += ["", 'ROI = average profit per tournament as % of buy-in (prize money = number of players x buy-in).',
              '`*` = interval excludes 0.']
    return "\n".join(lines)


def tournament_text(res: TournamentResult) -> str:
    out = [f"Tournament seed {res.seed}: {res.hands} hands, final stage blinds {res.final_level.get('sb')}/"
           f"{res.final_level.get('bb')}{'' if res.finished else ' (kill switch)'}"]
    for e in res.eliminations:
        out.append(f"  Hand {e['hand']:4d}: {e['name']} is eliminated -> place {e['place']:g}")
    winner = min(range(len(res.places)), key=lambda s: res.places[s])
    out.append(f"  Winner: {res.names[winner]}")
    return "\n".join(out)
