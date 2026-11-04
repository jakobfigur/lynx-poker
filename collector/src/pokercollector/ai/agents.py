"""Gegner-Pool: regelbasierte Bots mit einstellbarem Stil plus Baseline-Agenten.

Alle Bots sehen nur die Observation. Zufall ist pro Entscheidung aus (Seed, Hand,
Verlaufslaenge) abgeleitet: gleiche Situation -> gleiche Entscheidung. Das macht
Matches reproduzierbar und Duplicate-Bewertungen fair.

Stile (angelehnt an typische PokerTH-Bot-Typen; NICHT deren echter Code):
  station  spielt viele Haende, callt viel, erhoeht fast nie
  rock     sehr eng, setzt nur mit starken Haenden
  tag      eng-aggressiv (solider Standard)
  lag      locker-aggressiv
  maniac   extrem locker und aggressiv, viele Bluffs
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from ..poker import FULL_DECK, evaluate
from .observation import Action, Observation
from .tables import preflop_equity, preflop_percentile

AGENTS_VERSION = "agents-1"


def mc_equity(hole: list[str], board: list[str], opponents: int, iterations: int, rng: random.Random) -> float:
    """Equity gegen `opponents` zufaellige Haende (kleines Monte-Carlo)."""
    from ..fastpoker import HAVE_NUMBA, mc_stats
    if HAVE_NUMBA:
        return mc_stats(hole, board, opponents, iterations, rng.getrandbits(31))[0] / iterations
    opponents = max(1, min(opponents, 9))
    known = set(hole) | set(board)
    deck = [c for c in FULL_DECK if c not in known]
    need = 5 - len(board)
    total = 0.0
    for _ in range(iterations):
        draw = rng.sample(deck, need + 2 * opponents)
        full = board + draw[:need]
        hv = evaluate(hole + full)
        n_eq, lost = 0, False
        for i in range(opponents):
            ov = evaluate(draw[need + 2 * i: need + 2 * i + 2] + full)
            if ov > hv:
                lost = True
                break
            if ov == hv:
                n_eq += 1
        if not lost:
            total += 1.0 / (n_eq + 1)
    return total / iterations


def push_fold_spot(obs: Observation) -> dict:
    """Ordnet eine Preflop-Situation dem Push/Fold-Modell zu.
    first_in: niemand hat vor uns erhoeht (Limper zaehlen als Spieler dahinter).
    facing_push: genau eine Erhoehung vor uns, wir sind einer der Spieler dahinter.
    other: mehrere Erhoehungen oder bereits Caller vor uns."""
    pre = [a for a in obs.history if a.street == "preflop"]
    aggr = [i for i, a in enumerate(pre) if a.kind in ("bet", "raise")]
    total = lambda s: obs.stacks[s] + obs.bets[s]
    bb = obs.big_blind or 1
    if not aggr:
        behind = [s for s in range(obs.num_seats)
                  if s != obs.seat and obs.in_hand[s] and not obs.folded[s] and not obs.allin[s]]
        eff = min(total(obs.seat), max((total(s) for s in behind), default=0))
        return {"kind": "first_in", "behind": len(behind), "stack_bb": eff / bb}
    if len(aggr) == 1:
        i = aggr[0]
        pusher = pre[i].seat
        folded_before = {a.seat for a in pre[:i] if a.kind == "fold"}
        callers_after = [a for a in pre[i + 1:] if a.kind == "call"]
        order = [(pusher + k) % obs.num_seats for k in range(1, obs.num_seats)]
        behind = [s for s in order if obs.in_hand[s] and s not in folded_before]
        if not callers_after and obs.seat in behind:
            eff = min(total(obs.seat), pre[i].amount_to or 0)
            return {"kind": "facing_push", "behind": len(behind), "index": behind.index(obs.seat),
                    "stack_bb": eff / bb, "pusher": pusher}
    return {"kind": "other"}


class BaseAgent:
    name = "base"

    def __init__(self, seed: int = 0, name: str | None = None):
        self.seed = seed
        if name:
            self.name = name

    def rng(self, obs: Observation) -> random.Random:
        return random.Random(f"{self.name}|{self.seed}|{obs.hand_id}|{len(obs.history)}|{obs.street}")

    def act(self, obs: Observation) -> Action:
        raise NotImplementedError

    @staticmethod
    def passive(obs: Observation) -> Action:
        return Action.check() if obs.can_check else Action.fold()

    @staticmethod
    def raise_to(obs: Observation, amount: float) -> Action:
        if not obs.can_raise:
            return Action.check() if obs.can_check else Action.call()
        amt = int(round(max(obs.min_raise_to, min(obs.max_raise_to, amount))))
        return Action.raise_to(amt)


class RandomAgent(BaseAgent):
    """Zufaellig unter den erlaubten Aktionen - Untergrenze fuer jede Bewertung."""
    name = "random"

    def act(self, obs):
        r = self.rng(obs)
        choice = r.choice(obs.legal())
        if choice == "raise":
            hi = min(obs.max_raise_to, max(obs.min_raise_to, obs.current_bet + obs.pot))
            return Action.raise_to(r.randint(obs.min_raise_to, hi))
        return Action(choice)


class CallAgent(BaseAgent):
    """Checkt oder callt immer (deterministisch, fuer Tests)."""
    name = "caller"

    def act(self, obs):
        return Action.check() if obs.can_check else Action.call()


@dataclass(frozen=True)
class Style:
    vpip: float            # Anteil gespielter Starthaende (nach Perzentil)
    pfr: float             # Anteil Starthaende, mit denen eroeffnet wird
    value_margin: float    # Equity ueber fairem Anteil fuer Value-Bet
    raise_margin: float    # Equity ueber fairem Anteil fuer Raise gegen Einsatz
    call_slack: float      # callt auch, wenn Equity bis zu diesem Wert unter den Pot Odds liegt
    bluff: float           # Bluff-Wahrscheinlichkeit, wenn niemand gesetzt hat
    bet_size: float        # Einsatz als Anteil des Pots
    open_size: float       # Preflop-Eroeffnung in BB
    push_bb: float = 0.0   # ab diesem Stack (in BB) nur noch Push/Fold preflop; 0 = nie
    nash_stack_factor: float = 1.0   # Push/Fold "als haette man x-mal so viele BB": >1 enger, <1 lockerer
    respect: float = 0.0   # Respekt vor Einsaetzen nach dem Flop: verlangt zum Callen zusaetzlich
                           # respect x (Einsatz/Pot) Equity. Die Equity gegen ZUFALLSkarten ueberschaetzt
                           # die Lage gegen jemanden, der setzt; echte Spieler folden viel oefter (HandHQ).
    sticky: float = 0.0    # "Call-Down": je spaeter die Strasse, desto weniger Respekt (0 = gleich, 1 = am River
                           # gar keiner). Menschen geben am Flop oft auf, rufen spaeter aber oft bis zum Ende.


STYLES = {
    "station": Style(vpip=0.60, pfr=0.03, value_margin=0.30, raise_margin=0.45, call_slack=0.15, bluff=0.00,
                     bet_size=0.5, open_size=2.5, push_bb=0),
    "rock":    Style(vpip=0.12, pfr=0.08, value_margin=0.20, raise_margin=0.30, call_slack=-0.05, bluff=0.00,
                     bet_size=0.6, open_size=3.0, push_bb=8, nash_stack_factor=1.6),
    "tag":     Style(vpip=0.20, pfr=0.15, value_margin=0.10, raise_margin=0.25, call_slack=0.00, bluff=0.10,
                     bet_size=0.66, open_size=3.0, push_bb=12),
    "lag":     Style(vpip=0.35, pfr=0.25, value_margin=0.05, raise_margin=0.15, call_slack=0.05, bluff=0.25,
                     bet_size=0.75, open_size=3.0, push_bb=15, nash_stack_factor=0.85),
    "maniac":  Style(vpip=0.65, pfr=0.45, value_margin=0.00, raise_margin=0.05, call_slack=0.10, bluff=0.45,
                     bet_size=1.0, open_size=4.0, push_bb=20, nash_stack_factor=0.6),
}


class StyleBot(BaseAgent):
    def __init__(self, style: str, seed: int = 0, iterations: int = 120, name: str | None = None):
        super().__init__(seed, name or style)
        self.style = STYLES[style]
        self.iterations = iterations

    def _push_fold(self, obs: Observation, p: float, r: random.Random) -> Action:
        """Kurzer Stack: All-in oder Fold nach der Nash-Push/Fold-Tabelle (pushfold.py).
        Der Stil verschiebt den Stack, mit dem nachgeschlagen wird (enger/lockerer)."""
        from .pushfold import call_probability, push_probability

        f = self.style.nash_stack_factor
        spot = push_fold_spot(obs)
        if spot["kind"] == "first_in":
            prob = push_probability(obs.hole_cards, spot["stack_bb"] * f, spot["behind"])
            if prob is None:
                return self.passive(obs)
            if r.random() < prob:
                return self.raise_to(obs, obs.max_raise_to or 0)
            return self.passive(obs)
        if spot["kind"] == "facing_push":
            prob = call_probability(obs.hole_cards, spot["stack_bb"] * f, spot["behind"], spot["index"])
            if prob is not None and r.random() < prob:
                return Action.call()
            return self.passive(obs)
        # Mehrere Einsaetze vor uns: Modell passt nicht -> nur mit klar genug Equity mitgehen
        eq = preflop_equity(obs.hole_cards, obs.opponents_in_hand)
        po = obs.to_call / (obs.pot + obs.to_call) if obs.to_call else 0.0
        return Action.call() if eq >= po + 0.05 else self.passive(obs)

    def _preflop(self, obs: Observation, r: random.Random) -> Action:
        st = self.style
        p = preflop_percentile(obs.hole_cards)
        if st.push_bb and obs.stack_bb <= st.push_bb:
            return self._push_fold(obs, p, r)
        raises = sum(1 for a in obs.street_actions() if a.kind in ("bet", "raise"))
        bb = obs.big_blind
        if raises == 0:
            limpers = sum(1 for a in obs.street_actions() if a.kind == "call")
            if p <= st.pfr:
                return self.raise_to(obs, (st.open_size + limpers) * bb)
            if p <= st.vpip:
                return Action.check() if obs.can_check else Action.call()
            return self.passive(obs)
        po = obs.to_call / (obs.pot + obs.to_call) if obs.to_call else 0.0
        eq = preflop_equity(obs.hole_cards, obs.opponents_in_hand)
        if raises == 1:
            if p <= st.pfr * 0.3:
                return self.raise_to(obs, obs.current_bet * 3)
            if p <= st.vpip * 0.6 and eq >= po - st.call_slack:
                return Action.call()
            return self.passive(obs)
        if p <= st.pfr * 0.1:
            return self.raise_to(obs, obs.max_raise_to or 0)
        if p <= st.pfr * 0.25 and eq >= po - st.call_slack:
            return Action.call()
        return self.passive(obs)

    def _postflop(self, obs: Observation, r: random.Random) -> Action:
        st = self.style
        opp = max(1, obs.opponents_in_hand)
        eq = mc_equity(obs.hole_cards, obs.board, opp, self.iterations, r)
        fair = 1.0 / (opp + 1)
        if obs.can_check:
            if eq > fair + st.value_margin or (r.random() < st.bluff and obs.raises_this_street() == 0):
                return self.raise_to(obs, obs.current_bet + st.bet_size * obs.pot)
            return Action.check()
        po = obs.to_call / (obs.pot + obs.to_call)
        if st.respect:
            later = {"flop": 0.0, "turn": 0.5, "river": 1.0}.get(obs.street, 0.0)
            eq -= st.respect * (1 - st.sticky * later) * min(obs.to_call / max(1, obs.pot - obs.to_call), 1.5)
        if eq > fair + st.raise_margin and obs.can_raise:
            return self.raise_to(obs, obs.current_bet * 2 + obs.pot * st.bet_size)
        if eq >= po - st.call_slack:
            return Action.call()
        return Action.fold()

    def act(self, obs):
        r = self.rng(obs)
        if obs.street == "preflop":
            return self._preflop(obs, r)
        return self._postflop(obs, r)


class EquityAgent(BaseAgent):
    """Die Baseline aus advisor.py als Agent: Equity gegen Zufallshaende vs. Pot Odds."""
    name = "equity"

    def __init__(self, seed: int = 0, iterations: int = 300, name: str | None = None):
        super().__init__(seed, name)
        self.iterations = iterations
        self.last_advice = None

    def act(self, obs):
        from ..advisor import GameState, advise

        issues = [] if len(obs.hole_cards) == 2 else ["eigene Karten unbekannt"]
        gs = GameState(obs.hole_cards, obs.board, max(1, obs.opponents_in_hand),
                       obs.pot, 0 if obs.can_check else obs.to_call, obs.my_stack, obs.big_blind,
                       issues=issues)
        adv = advise(gs, iterations=self.iterations, seed=self.rng(obs).randrange(1 << 30))
        self.last_advice = adv
        rec = adv.recommendation
        if rec in ("bet", "raise"):
            return self.raise_to(obs, obs.current_bet + max(obs.current_bet * 2, 0.66 * obs.pot))
        if rec == "call":
            return Action.check() if obs.can_check else Action.call()
        if rec == "check":
            return Action.check() if obs.can_check else Action.fold()
        return self.passive(obs)


REGISTRY = {
    "random": lambda seed=0: RandomAgent(seed),
    "caller": lambda seed=0: CallAgent(seed),
    "equity": lambda seed=0: EquityAgent(seed),
    **{k: (lambda seed=0, k=k: StyleBot(k, seed)) for k in STYLES},
}


def make_agent(spec: str, seed: int = 0) -> BaseAgent:
    """'tag', 'tag:Name' (Name zur Unterscheidung) oder mit eigenen Stilwerten
    'tag?bluff=0.2&vpip=0.25:Name' (nur fuer Stil-Bots)."""
    # Name steht hinter dem LETZTEN Doppelpunkt und enthaelt keine Parameterzeichen -
    # so bleibt 'hus?bp=run:lynx-5t@1&...:kand' intakt (31.10.: partition(":") zerlegte 'run:' -> KeyError 'run')
    body, sep, name = spec.rpartition(":")
    if not sep or not name or any(c in name for c in "=&?@/"):
        body, name = spec, ""
    kind, _, params = body.partition("?")
    if kind == "search":                   # Netz + Suche waehrend des Spiels (search.py)
        from .search import make_search_agent
        a = make_search_agent(params, seed)
        a.name = name or body
        return a
    if kind == "hus":                      # Netz + heads-up Neuloesen ab dem Turn (husearch.py)
        from .husearch import make_husearch_agent
        a = make_husearch_agent(params, seed)
        a.name = name or body
        return a
    if kind == "cfr":                      # Gleichgewichts-Bot (cfr.py)
        from .cfr import make_cfr_agent
        a = make_cfr_agent(params, seed)
        a.name = name or body
        return a
    if kind == "nn":                       # lernender Bot (nn_agent.py), braucht PyTorch zum Laden
        from .nn_agent import make_nn_agent
        a = make_nn_agent(params, seed)
        a.name = name or body
        return a
    if kind not in REGISTRY:
        raise ValueError(f"unbekannter Agent '{kind}'. Verfuegbar: {', '.join(sorted(REGISTRY))}")
    a = REGISTRY[kind](seed)
    if params:
        if not isinstance(a, StyleBot):
            raise ValueError(f"Parameter nur fuer Stil-Bots ({', '.join(STYLES)}), nicht fuer '{kind}'")
        changes = {}
        for kv in params.split("&"):
            k, _, v = kv.partition("=")
            if k not in Style.__dataclass_fields__:
                raise ValueError(f"unbekannter Stilwert '{k}'. Moeglich: {', '.join(Style.__dataclass_fields__)}")
            changes[k] = float(v)
        a.style = replace(a.style, **changes)
        a.name = body
    if name:
        a.name = name
    return a
