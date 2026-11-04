"""ICM (Independent Chip Model, Malmuth-Harville): Turnier-Eigenkapital aus den Stacks.

P(Spieler i wird Erster) = s_i / S. P(i wird Zweiter) = Summe ueber j != i von P(j Erster) * s_i / (S - s_j),
usw. bis zum letzten bezahlten Platz. Preise in Buy-ins je Platz (z. B. 6 Spieler, 50/30/20 % -> 3.0, 1.8, 1.2).

Nur fuer die Belohnung im Training und fuer Auswertungen; der Bot sieht ICM nicht direkt.
"""

from __future__ import annotations


def icm_equity(stacks: list[int] | list[float], prizes: list[float], seat: int) -> float:
    """Erwartete Auszahlung (in Buy-ins) fuer `seat` bei diesen Stacks. Ausgeschiedene (0) haben 0."""
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
        """Wahrscheinlichkeiten, dass seat Platz depth, depth+1, ... belegt, gegeben die in `excluded`
        schon vor ihm fertig sind (remaining_total = Summe der uebrigen Stacks inkl. seat)."""
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
    """Auszahlungsanteile (0.5, 0.3, 0.2) -> Preise in Buy-ins bei `players` Buy-ins Preisgeld."""
    return [float(f) * players for f in (payouts or ())]
