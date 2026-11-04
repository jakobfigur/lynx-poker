# Goals for Lynx

Status: 28.10.2026. Scoreboard: `pc.cmd bench ziele <bot>`.
Measure anew: `--messen` (benchmarks 2 and 5, approx. 15–30 min), `--exploit` (benchmark 4).

Lynx is intended to win in PokerTH against humans. The goals are sorted by how close they are to achievement.

| # | Benchmark | What it measures | Levels |
|---|---|---|---|
| 1 | **Real PokerTH games** (Jakob plays, Lynx advises) | Placement and ROI in real Sit&Go’s (payout 50/30/20 %) | 50 tournaments with ROI > 0 → 200 tournaments with ROI > +20 % and win rate > 1/6 |
| 2 | **Human tables** `mensch480` | PokerTH format against bots simulating real 25NL behavior (HandHQ) | ROI ≥ +100 % → ROI ≥ +120 % |
| 3 | **Slumbot** (heads-up, 200 BB) | Strength against an almost error-free opponent | > −15 bb/100 → > 0 → lower 95% confidence bound > 0 (each ≥ 20,000 hands, all-in EV) |
| 4 | **Exploitability** | An exploiter learns against 5 copies of the bot, measured via its ROI | Exploiter ≤ +5 % |
| 5 | **Endgame heads-up with 20 BB** | Tournament endgame: `nash240` against push/fold-Nash, `kurz240` against human bots | nash240 ≥ 0 % → kurz240 > +20 % |

**Safeguard against regressions:** A new version must pass the league gate and a predefined confirmation on new human tables. Each runs once and is never repeated.

## Benchmark 1: record real tournaments

After each tournament enter:

```
pc.cmd bench turnier <Placement> --spieler 6 --notiz "against PokerTH bots"
```

Rules:
- Play is manual; Lynx only gives suggestions.
- No automatic clicks and no reading of DOM, network, or memory.
- The PokerTH log is only a reference and never used for training.

Results fluctuate strongly in Sit&Go’s. Before 100–200 tournaments the number says little.

## Intentionally no goal

- **Matching human actions:** Similarity is not a strength.
- **Training on Slumbot:** Slumbot is only a measuring stick. Lynx should become generally strong; the search also computes an equilibrium, not Slumbot adaptation.
