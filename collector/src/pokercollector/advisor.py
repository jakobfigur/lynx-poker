"""Baseline decision aid: equity against random hands + pot odds.

This is deliberately the simplest honest baseline, no strategy:
- Opponents are assumed random cards (no ranges) -> equity is
  usually overestimated against real opponents who remain in the pot.
- Future bets (implied odds, reverse implied odds) are missing.
- Position and stack depth are not considered.
Later models must be measured against this baseline.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .poker import EquityResult, equity_vs_random, is_card, pot_odds

ADVISOR_VERSION = "baseline-equity-1"


@dataclass
class GameState:
    hero_cards: list[str]
    board: list[str]
    opponents: int
    pot: int | None          # Pot including all bets on the table
    to_call: int | None
    hero_stack: int | None
    big_blind: int | None = None
    state_age_s: float | None = None
    issues: list[str] = field(default_factory=list)


@dataclass
class Advice:
    recommendation: str | None      #'fold' | 'check' | 'call' | 'bet' | 'raise' | None
    alternatives: list[str]
    equity: float | None
    equity_std_error: float | None
    pot_odds: float | None
    reasoning: list[str]
    assumptions: list[str]
    version: str = ADVISOR_VERSION

    def to_dict(self):
        return asdict(self)


def state_from_snapshot_state(st: dict, hero_seat: int = 0) -> GameState:
    """Builds the game state from the stabilized field state (Stabilizer.state())."""
    issues = []
    hero = st.get(f"seat.{hero_seat}.cards") or []
    if not hero or not all(is_card(c) for c in hero):
        issues.append('own cards not recognized reliably')
    board = [c for c in (st.get("board.cards") or []) if c is not None]
    if any(not is_card(c) for c in board):
        issues.append('Board card unreadable')
        board = [c for c in board if is_card(c)]
    opp = 0
    for s in range(10):
        if s == hero_seat:
            continue
        if st.get(f"seat.{s}.present") and not st.get(f"seat.{s}.folded") and \
                st.get(f"seat.{s}.cards_state") in ("backs", "faces"):
            opp += 1
    if opp == 0:
        issues.append('no active opponents recognized')
    pot = st.get("pot.total")
    to_call = None
    buttons = st.get("hero.buttons") or []
    for b in buttons:
        if b.get("action") == "call" and b.get("amount") is not None:
            to_call = b["amount"]
        elif b.get("action") == "check":
            to_call = 0
    if st.get("hero.to_act") and to_call is None:
        issues.append('amount to call not readable')
    blinds = st.get("info.blinds")
    return GameState(hero if not issues else [c for c in hero if is_card(c)], board, opp, pot, to_call,
                     st.get(f"seat.{hero_seat}.stack"), blinds[1] if blinds else None, issues=issues)


def advise(gs: GameState, iterations: int = 2500, seed: int = 0, margin: float = 0.05) -> Advice:
    assumptions = [
        'opponents hold random cards (no ranges) - equity rather too high',
        'no future bets considered',
        f"Monte Carlo with {iterations} runs, seed {seed}",
    ]
    if gs.issues or len(gs.hero_cards) != 2 or gs.opponents < 1:
        return Advice(None, [], None, None, None,
                      ['No recommendation: state incomplete'] + gs.issues, assumptions)
    eq: EquityResult = equity_vs_random(gs.hero_cards, gs.board, min(gs.opponents, 9), iterations, seed)
    reasons = [f"Equity {eq.equity:.1%} ± {1.96 * eq.std_error:.1%} versus {eq.opponents} random hand/hands"]
    fair_share = 1.0 / (gs.opponents + 1)
    if gs.to_call is None:
        return Advice(None, [], eq.equity, eq.std_error, None,
                      reasons + ['No recommendation: amount to call unknown'], assumptions)
    if gs.to_call == 0:
        po = 0.0
        if eq.equity > fair_share + 0.15:
            rec, alts = "bet", ["check"]
            reasons.append(f"clearly above fair share {fair_share:.0%} -> value bet plausible")
        else:
            rec, alts = "check", ["bet"]
            reasons.append(f"not clearly above fair share {fair_share:.0%} -> free continuation")
    else:
        if gs.pot is None:
            return Advice(None, [], eq.equity, eq.std_error, None,
                          reasons + ['No recommendation: pot unknown'], assumptions)
        po = pot_odds(gs.to_call, gs.pot)
        reasons.append(f"Pot Odds: {gs.to_call} in {gs.pot + gs.to_call} -> requires {po:.1%}")
        if eq.equity > po + margin and eq.equity > fair_share + 0.15:
            rec, alts = "raise", ["call", "fold"]
            reasons.append('Equity clearly above pot odds and fair share')
        elif eq.equity > po + margin:
            rec, alts = "call", ["raise", "fold"]
            reasons.append('Equity above Pot Odds')
        elif eq.equity >= po - margin:
            rec, alts = "call", ["fold"]
            reasons.append('Borderline case: Equity close to Pot Odds')
        else:
            rec, alts = "fold", ["call"]
            reasons.append('Equity below Pot Odds')
    if gs.state_age_s is not None and gs.state_age_s > 2:
        reasons.append(f"Warning: State is {gs.state_age_s:.1f}s old")
    return Advice(rec, alts, eq.equity, eq.std_error, po, reasons, assumptions)
