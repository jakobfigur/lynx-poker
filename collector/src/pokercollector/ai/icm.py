""" ICM (Independent Chip Model, Malmuth-Harville): tournament equity from the stacks.

P(player i finishes first) = s_i / S. P(i is second) = sum over j != i of P(j first) * s_i / (S - s_j),
and so on until the last paid place. Prizes in buy-ins per place (e.g. 6 players, 50/30/20% -> 3.0, 1.8, 1.2).

Only for the reward in training and for evaluations; the bot does not see ICM directly.
"""

from __future__ import annotations


def icm_equity(stacks: list[int] | list[float], prizes: list[float], seat: int) -> float:
    """ Expected payout (in buy-ins) for `seat` given these stacks. Eliminated (0) have 0."""
    if stacks[seat] <= 0 or not prizes:
        return 0.0
    alive = [i for i, s in enumerate(stacks) if s > 0]
    if len(alive) == 1:
        return float(prizes[0])
    total = float(sum(stacks[i] for i in alive))
    others = [i for i in alive if i != seat]
    s_i = float(stacks[seat])
    places = min(len(prizes), len(alive))

    def finish_prob(remaining_total: float, excluded: tuple[int, ...], depth: int) -> list[float]:
        """ Probabilities that seat finishes at place depth, depth+1, ... given those in `excluded`
        have already finished ahead (remaining_total = sum of remaining stacks including seat)."""
        out = [0.0] * (places - depth + 1)
        out[0] = s_i / remaining_total
        if depth < places:
            for j in others:
                if j in excluded:
                    continue
                p_j = stacks[j] / remaining_total
                sub = finish_prob(remaining_total - stacks[j], excluded + (j,), depth + 1)
                for k, v in enumerate(sub):
                    out[k + 1] += p_j * v
        return out

    probs = finish_prob(total, (), 1)
    return float(sum(p * prizes[k] for k, p in enumerate(probs) if k < len(prizes)))


def icm_equities(stacks: list[int] | list[float], prizes: list[float]) -> list[float]:
    return [icm_equity(stacks, prizes, i) for i in range(len(stacks))]


def prizes_from(payouts, players: int) -> list[float]:
    """ Payout shares (0.5, 0.3, 0.2) -> prizes in buy-ins with `players` buy-ins prize pool."""
    return [float(f) * players for f in (payouts or ())]
