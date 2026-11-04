"""Logs decisions of any agent (bot or human) and evaluates
push/fold situations against the Nash equilibrium."""

from __future__ import annotations

from dataclasses import dataclass, field

from .agents import push_fold_spot
from .observation import Action, Observation, clamp_action
from .pushfold import decision_ev

PF_MAX_BB = 15   # above ~15 BB, push/fold is no longer the standard strategy (open-raise is legitimate)


def classify_pf_choice(obs: Observation, action: Action, spot: dict) -> str | None:
    if action.kind == "fold":
        return "fold"
    if spot["kind"] == "first_in":
        if action.kind == "check":
            return "fold"           # BB checks with zero bet = no push; counts like fold
        if action.kind == "raise" and obs.max_raise_to and action.amount >= 0.9 * obs.max_raise_to:
            return "push"
        return None                 # Mini-raise or limp: outside the push/fold model
    if spot["kind"] == "facing_push":
        if action.kind in ("call", "raise"):
            return "call"
    return None


@dataclass
class DecisionLog:
    decisions: int = 0
    pf_spots: list[dict] = field(default_factory=list)
    pf_outside_model: int = 0

    def summary(self) -> dict:
        n = len(self.pf_spots)
        loss = sum(s["ev_loss"] for s in self.pf_spots)
        wrong = [s for s in self.pf_spots if s["ev_loss"] > 0.01]
        return {"decisions": self.decisions, "pf_spots": n, "pf_outside_model": self.pf_outside_model,
                "pf_ev_loss_total_bb": round(loss, 2),
                "pf_ev_loss_per_spot_bb": round(loss / n, 3) if n else None,
                "pf_mistakes": len(wrong), "pf_mistake_pct": round(100 * len(wrong) / n, 1) if n else None}


class RecordingAgent:
    """Wrapper around an agent; forwards everything and logs."""

    def __init__(self, agent, log: DecisionLog | None = None):
        self.agent = agent
        self.log = log or DecisionLog()

    @property
    def name(self):
        return self.agent.name

    @name.setter
    def name(self, v):
        self.agent.name = v

    def act(self, obs: Observation) -> Action:
        action = self.agent.act(obs)
        self.log.decisions += 1
        if obs.street == "preflop" and obs.hole_cards and obs.stack_bb <= PF_MAX_BB:
            spot = push_fold_spot(obs)
            if spot["kind"] in ("first_in", "facing_push"):
                chose = classify_pf_choice(obs, clamp_action(obs, action), spot)
                if chose is None:
                    self.log.pf_outside_model += 1
                else:
                    ev = decision_ev(obs.hole_cards, spot, chose)
                    if ev:
                        ev["hand_id"] = obs.hand_id
                        self.log.pf_spots.append(ev)
        return action

    def hand_over(self, rec, seat):
        cb = getattr(self.agent, "hand_over", None)
        if cb:
            cb(rec, seat)
