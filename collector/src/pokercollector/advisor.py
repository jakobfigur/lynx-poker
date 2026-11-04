"""Baseline-Entscheidungshilfe: Equity gegen zufaellige Haende + Pot Odds.

Das ist bewusst die einfachste ehrliche Baseline, keine Strategie:
- Gegner werden mit zufaelligen Karten angenommen (keine Ranges) -> Equity wird
  gegen reale Gegner, die noch im Pot sind, meist ueberschaetzt.
- Zukuenftige Einsaetze (implied odds, reverse implied odds) fehlen.
- Positions- und Stacktiefe fliessen nicht ein.
Spaetere Modelle muessen sich gegen diese Baseline messen lassen.
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
    pot: int | None          # Pot inkl. aller Einsaetze auf dem Tisch
    to_call: int | None
    hero_stack: int | None
    big_blind: int | None = None
    state_age_s: float | None = None
    issues: list[str] = field(default_factory=list)


@dataclass
class Advice:
    recommendation: str | None      # 'fold' | 'check' | 'call' | 'bet' | 'raise' | None
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
    """Baut den Spielzustand aus dem stabilisierten Feldzustand (Stabilizer.state())."""
    issues = []
    hero = st.get(f"seat.{hero_seat}.cards") or []
    if not hero or not all(is_card(c) for c in hero):
        issues.append("eigene Karten nicht sicher erkannt")
    board = [c for c in (st.get("board.cards") or []) if c is not None]
    if any(not is_card(c) for c in board):
        issues.append("Boardkarte unlesbar")
        board = [c for c in board if is_card(c)]
    opp = 0
    for s in range(10):
        if s == hero_seat:
            continue
        if st.get(f"seat.{s}.present") and not st.get(f"seat.{s}.folded") and \
                st.get(f"seat.{s}.cards_state") in ("backs", "faces"):
            opp += 1
    if opp == 0:
        issues.append("keine aktiven Gegner erkannt")
    pot = st.get("pot.total")
    to_call = None
    buttons = st.get("hero.buttons") or []
    for b in buttons:
        if b.get("action") == "call" and b.get("amount") is not None:
            to_call = b["amount"]
        elif b.get("action") == "check":
            to_call = 0
    if st.get("hero.to_act") and to_call is None:
        issues.append("zu callender Betrag nicht lesbar")
    blinds = st.get("info.blinds")
    return GameState(hero if not issues else [c for c in hero if is_card(c)], board, opp, pot, to_call,
                     st.get(f"seat.{hero_seat}.stack"), blinds[1] if blinds else None, issues=issues)


def advise(gs: GameState, iterations: int = 2500, seed: int = 0, margin: float = 0.05) -> Advice:
    assumptions = [
        "Gegner halten zufaellige Karten (keine Ranges) - Equity eher zu hoch",
        "keine zukuenftigen Einsaetze beruecksichtigt",
        f"Monte-Carlo mit {iterations} Durchlaeufen, Seed {seed}",
    ]
    if gs.issues or len(gs.hero_cards) != 2 or gs.opponents < 1:
        return Advice(None, [], None, None, None,
                      ["Keine Empfehlung: Zustand unvollstaendig"] + gs.issues, assumptions)
    eq: EquityResult = equity_vs_random(gs.hero_cards, gs.board, min(gs.opponents, 9), iterations, seed)
    reasons = [f"Equity {eq.equity:.1%} ± {1.96 * eq.std_error:.1%} gegen {eq.opponents} zufaellige Hand/Haende"]
    fair_share = 1.0 / (gs.opponents + 1)
    if gs.to_call is None:
        return Advice(None, [], eq.equity, eq.std_error, None,
                      reasons + ["Keine Empfehlung: zu callender Betrag unbekannt"], assumptions)
    if gs.to_call == 0:
        po = 0.0
        if eq.equity > fair_share + 0.15:
            rec, alts = "bet", ["check"]
            reasons.append(f"deutlich ueber fairem Anteil {fair_share:.0%} -> Wert-Einsatz denkbar")
        else:
            rec, alts = "check", ["bet"]
            reasons.append(f"nicht klar ueber fairem Anteil {fair_share:.0%} -> kostenlos weiter")
    else:
        if gs.pot is None:
            return Advice(None, [], eq.equity, eq.std_error, None,
                          reasons + ["Keine Empfehlung: Pot unbekannt"], assumptions)
        po = pot_odds(gs.to_call, gs.pot)
        reasons.append(f"Pot Odds: {gs.to_call} in {gs.pot + gs.to_call} -> benoetigt {po:.1%}")
        if eq.equity > po + margin and eq.equity > fair_share + 0.15:
            rec, alts = "raise", ["call", "fold"]
            reasons.append("Equity klar ueber Pot Odds und fairem Anteil")
        elif eq.equity > po + margin:
            rec, alts = "call", ["raise", "fold"]
            reasons.append("Equity ueber Pot Odds")
        elif eq.equity >= po - margin:
            rec, alts = "call", ["fold"]
            reasons.append("Grenzfall: Equity nahe an den Pot Odds")
        else:
            rec, alts = "fold", ["call"]
            reasons.append("Equity unter Pot Odds")
    if gs.state_age_s is not None and gs.state_age_s > 2:
        reasons.append(f"Achtung: Zustand ist {gs.state_age_s:.1f}s alt")
    return Advice(rec, alts, eq.equity, eq.std_error, po, reasons, assumptions)
