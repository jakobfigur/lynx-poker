"""Search during play - basis for Pluribus-like lookahead.

Pluribus' strength did not come solely from its base strategy ("blueprint"), but from search:
In every situation, it looks ahead a bit and refines the decision.
Here are the building blocks and a first simple search:

1. Belief state: opponents' ranges (ranges.py) -> from that, sample possible opponent hands ("worlds").
2. world_from_obs(): build a complete game state from observation + sampled cards (stacks from hand start, button, blinds, public history replayed).
   From that one can simulate every action (Hand.clone()).
3. SearchAgent (level 1, "rollout search"): For each allowed action in many worlds play out the hand with
   the blueprint strategy (one of our networks) for ALL players to the end; same worlds for
   all actions (paired comparison, less noise). Choose action with best average - only override if clearly better
   than the blueprint choice, otherwise keep it.

Difference to Pluribus (later levels): Pluribus solves a limited subgame with CFR at every decision,
where opponents during the search horizon can choose among multiple continuation strategies (robust against exploitation).
Level 1 assumes all continue after the blueprint. Building blocks 1 and 2 are the same for both levels.
"""

from __future__ import annotations

import random

import numpy as np

from ..poker import FULL_DECK
from .agents import BaseAgent, make_agent
from .cfr import abstract_mask
from .engine import Hand
from .features import N_ACTIONS, to_action
from .observation import Action, Observation, clamp_action
from .ranges import opponent_ranges, sample_hands

SEARCH_VERSION = "search-1"


def world_from_obs(obs: Observation, opp_hands: dict[int, list[str]], rng: random.Random,
                   hand_id: str = "world") -> Hand:
    """Complete game state that looks the same to player obs.seat as obs.
    opp_hands: assumed cards of opponents still in hand; folded opponents get
    arbitrary free cards (they no longer matter). Upcoming board cards are random."""
    n = obs.num_seats
    start = [obs.stacks[s] + obs.committed[s] for s in range(n)]
    used = set(obs.hole_cards) | set(obs.board) | {c for h in opp_hands.values() for c in h}
    rest = [c for c in FULL_DECK if c not in used]
    rng.shuffle(rest)
    it = iter(rest)
    deck: list[str | None] = [None] * 52
    for s in range(n):
        if not obs.in_hand[s]:
            continue
        cards = obs.hole_cards if s == obs.seat else opp_hands.get(s) or [next(it), next(it)]
        deck[2 * s], deck[2 * s + 1] = cards
    for k, c in enumerate(obs.board):
        deck[20 + k] = c
    deck = [c if c is not None else next(it) for c in deck]
    h = Hand(start, obs.button, obs.small_blind, obs.big_blind, deck=deck, hand_id=hand_id,
             names=list(obs.names) if obs.names else None, tournament=obs.tournament)
    for a in obs.history:
        if a.kind in ("post_sb", "post_bb"):
            continue
        if h.to_act != a.seat:
            raise ValueError(f"History does not match: {a} (engine expects seat {h.to_act})")
        if a.kind == "fold":
            act = Action.fold()
        elif a.kind == "check":
            act = Action.check()
        elif a.kind == "call":
            act = Action.call()
        else:
            act = Action.raise_to(a.amount_to)
        h.apply(a.seat, act)
    if h.done or h.to_act != obs.seat:
        raise ValueError('Reconstructed game state is not at the point of observation')
    return h


def play_out(h: Hand, agents, seat: int) -> float:
    """Plays out the hand to the end with given agents (list per seat or one agent for all).
    Returns result for `seat` in Big Blinds."""
    while not h.done:
        s = h.to_act
        obs = h.observation(s)
        a = agents[s] if isinstance(agents, list) else agents
        h.apply(s, clamp_action(obs, a.act(obs)))
    return h.record.results[seat].net / h.bb


class SearchAgent(BaseAgent):
    """Rollout search over a blueprint strategy. last_q: estimated value per action (BB) - also
    usable for live recommendations. min_gain: minimum advantage (BB) over blueprint choice."""
    name = "search"

    def __init__(self, blueprint: str, worlds: int = 24, min_gain: float = 0.25, seed: int = 0,
                 name: str | None = None):
        super().__init__(seed, name)
        self.blueprint_spec = blueprint
        self.blueprint = make_agent(f"{blueprint}:bp", seed)
        self.worlds = worlds
        self.min_gain = min_gain
        self.last_q: np.ndarray | None = None
        self.searches = 0
        self.overrides = 0

    def act(self, obs: Observation) -> Action:
        bp_action = clamp_action(obs, self.blueprint.act(obs))
        mask = abstract_mask(obs)
        if len(obs.hole_cards) != 2 or mask.sum() <= 1:
            return bp_action
        rng = self.rng(obs)
        nrng = np.random.default_rng(rng.randrange(1 << 30))
        ranges = opponent_ranges(obs)
        #Candidates: the abstracted actions and - if not among them - the blueprint choice
        idxs = [int(a) for a in np.flatnonzero(mask)]
        cands = [clamp_action(obs, to_action(obs, a)) for a in idxs]
        if bp_action not in cands:
            idxs.append(-1)
            cands.append(bp_action)
        bp_col = cands.index(bp_action)
        rows = []
        for k in range(self.worlds):
            hands = sample_hands(ranges, list(obs.hole_cards) + list(obs.board), nrng)
            if hands is None:
                continue
            try:
                world = world_from_obs(obs, hands, random.Random(rng.randrange(1 << 30)), hand_id=f"w{k}")
            except ValueError:
                return bp_action
            row = []
            for j, act in enumerate(cands):
                h = world.clone()
                h.hand_id = f"{obs.hand_id}|w{k}|c{j}"        # own randomness per continuation
                h.apply(obs.seat, act)
                row.append(play_out(h, self.blueprint, obs.seat))
            rows.append(row)
        if len(rows) < 4:
            return bp_action
        vals = np.array(rows)                                 # Worlds x candidates, same worlds per column
        means = vals.mean(0)
        q = np.full(N_ACTIONS, -np.inf)
        for j, a in enumerate(idxs):
            if a >= 0:
                q[a] = means[j]
        self.last_q = q
        self.searches += 1
        best = int(np.argmax(means))
        if best == bp_col:
            return bp_action
        # Only override when clear advantage: paired difference per world, mean > 2 standard errors
        d = vals[:, best] - vals[:, bp_col]
        se = d.std(ddof=1) / np.sqrt(len(d))
        if d.mean() < max(self.min_gain, 2.0 * se):
            return bp_action
        self.overrides += 1
        return cands[best]


def make_search_agent(params: str, seed: int = 0) -> SearchAgent:
    """'search?bp=pros-2@300,worlds=24' (bp = net run@checkpoint; ',' or '&' separate - ',' is cmd-safe)."""
    kv = dict(p.partition("=")[::2] for p in params.replace(",", "&").split("&") if p)
    if "bp" not in kv:
        raise ValueError("search-bot: 'search?bp=<run>@<ckpt>[&worlds=24&gain=0.25]'")
    return SearchAgent(f"nn?run={kv['bp']}", int(kv.get("worlds", 24)), float(kv.get("gain", 0.25)), seed)
