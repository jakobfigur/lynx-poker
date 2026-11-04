# Poker Collector – Status as of 25.10.2026

Visual capture of PokerTH web games: Screen → recognition → journal with evidence →
hand reconstruction → independent comparison with the PokerTH export → baseline recommendation.
Plan and principles: `PROJECT_HANDOVER.md`. This document describes what has been **built**.

Everything runs from the USB stick: Python 3.12, all packages and an offline package cache are located under `tools\`.
Nothing is installed on the computer. The drive letter does not matter.

## Quick Start

Open a command prompt in the folder of the stick:

```
pc.cmd calibrate C:\Path\screenshot.png      Check screenshot, overlay image with all recognitions
pc.cmd analyze C:\Path\recording.mp4          Analyze recording (OBS/Game Bar) → new session
pc.cmd windows PokerTH                           List windows
pc.cmd live --window "PokerTH Web"              Live monitoring: automatically starts/stops sessions
pc.cmd live --window "PokerTH Web" --advice    adds baseline recommendation when it's your turn
pc.cmd reconstruct last                          Reconstruct hands of the last session
pc.cmd compare last C:\Path\export.pdb         Compare with PokerTH export (see compare.md)
pc.cmd inspect-reference C:\Path\export.pdb    Show schema of an export file
pc.cmd advise C:\Path\screenshot.png            Baseline recommendation for a screenshot
pc.cmd harvest-cards image1.png image2.png       Learn card templates (asks for correct value)
pc.cmd verify last                               Check checksums of a session
tests.cmd                                        Run all automated tests
```

Data ends up in `data\sessions\<Zeit>_<id>\`:
`observations.jsonl` (immutable event journal), `evidence\` (image snippet per event),
`video\` (segments + timestamp per frame, live mode only), `hands.json`/`hands.md` (reconstruction),
`index.sqlite`, `manifest.json` (SHA-256), `session.json` (source, versions, gaps, errors, statistics).

The collector **only reads**. It clicks, types and controls nothing remotely and does not read DOM, network, or memory.

## What has been built

| Component | File | Status |
|---|---|---|
| Table/Layout Recognition (felt, 10 seats, board, pot, info line, action bar, D/SB/BB) | `layout.py`, `profiles\pokerth_web_v1.json` | Tested on real screenshot, also at 85% and 125% window size |
| OCR (native Windows text recognition, cache for unchanged areas, fallback variants) | `ocr.py` | Tested |
| Parser for amounts, blinds, street, game/hand, action words including typical OCR misreads | `parse.py` | Unit tests |
| Card recognition (face up / back / empty, rank, suit, learnable templates) | `cards.py` | 6♠ 9♥ recognized; ♦ and ♣ **untested** |
| Frame analysis with confidence, raw value, image area, method per field | `analyzer.py` | On screenshot: all fields correct |
| Temporal stabilization, short-lived values logged as “transient” | `stabilize.py` | Unit tests |
| Journal, evidence images, SQLite index, manifest | `journal.py` | End-to-end test |
| Hand reconstruction (blinds, fold/check/call/bet/raise, streets, winners, gaps, contradictions, stack balance) | `reconstruct.py` | Synthetic hands; **not** tested on real game |
| Sources: video, image folder, live window; segmented recording | `capture.py` | Recorder tested; live loop smoke test |
| Automatic sessions (table recognized → recording, gone → end), analysis thread with backlog | `pipeline.py` | **not** tested on real live game |
| Import PokerTH log (SQLite) | `reference.py` | Only against self-made test file – **schema/card encoding untested** |
| Field-wise comparison (precision/recall, amount semantics, visibility) | `compare.py` | Unit tests |
| Baseline recommendation (equity vs random hands + pot odds, with assumptions) | `advisor.py`, `poker.py` | Unit tests |

Performance on screenshot (1905×980): first analysis approx. 200 ms, unchanged frames approx. 40 ms.

## Honest limitations

- **Only one screenshot** (preflop, hand 1) has been the basis so far. Flop/turn/river cards, showdown, action labels
  at seats, all-in, side pots, seat changes: code exists, but **not seen** on a real image.
- **Board slot positions** are derived from empty slots; the exact appearance of open board cards is unknown.
- **Card suits**: diamonds/clubs via shape heuristics, untested. Remedy: `harvest-cards` with real screenshots.
- **Live capture** uses a screen area (mss). If another window overlaps PokerTH, its contents would be captured.
  Therefore recording is by default only done if the window is in the foreground; otherwise a gap.
  True window capture independent of overlap: Windows.Graphics.Capture (C#, next step).
- **Below about 80%** of reference size (window narrower than about 1500 px) recognition becomes unreliable.
- **Video codec**: `mp4v` (OpenCV). H.264 would require an additional library.
- **Reference export**: table and column names as well as card encoding (0–51, suits d,h,s,c) come from
  PokerTH desktop source. Whether the web client exports exactly the same is shown only by `inspect-reference` on a real file.
- **Baseline recommendation** is not a strategy: opponents are random hands, no ranges, no future bets.

## What's needed next (test data)

1. A **screen recording** (Game Bar: Win+Alt+R or OBS) of 10–20 hands, PokerTH window maximized,
   with fold, check, call, bet, raise, flop/turn/river and at least one showdown.
2. The **hand history export of exactly this session** (keep separately).
3. A few **screenshots** with open board cards of all four suits, for `harvest-cards`.
4. Then: `pc.cmd analyze aufnahme.mp4`, then `pc.cmd compare last export.pdb` → first real metrics.
   Keep calibration recordings and test recordings separate.

## AI part: Simulator, bots, evaluation (levels 1–3)

Code: `collector\src\pokercollector\ai\`

```
pc.cmd sim agents                                   available bots
pc.cmd sim match --hands 500                        bots against each other (Duplicate mode), results in data\sim\
pc.cmd sim match --agents tag,tag:tag2,random --hands 1000 --show 3
pc.cmd sim hand --agents tag,station,maniac --seed 5   one hand with progression
pc.cmd sim review last --agent tag                  your real decisions of a session vs. bot
pc.cmd sim tournament --tournaments 30              Sit&Go tournaments like PokerTH (Duplicate)
pc.cmd sim tournament --stack 3000 --blinds 10/20 --level-hands 8 --payouts 100
pc.cmd sim pushfold --stack 10 --behind 1           Nash push/fold matrix (13x13) for pusher and caller
pc.cmd sim pushfold --overview                      push-% for all stacks (1-25 BB) and positions
pc.cmd live --window "PokerTH Web" --advice --agent equity
```

| Component | File | Status |
|---|---|---|
| **Common interface** `Observation` → `Action` (visible only, raise = "up" amount) | `ai/observation.py` | Basis for all |
| **Rule engine** No-Limit Hold'em 2–10 players: blinds, heads-up order, minimum raise, short all-in does not reopen, side pots, odd chips, uncalled chips returned | `ai/engine.py` | 18 rule tests including 600 random hands with chip conservation |
| **Preflop table**: equity of all 169 starting hands vs 1–9 opponents | `ai/tables.py`, `ai/preflop_equity.json` | Deviation from known values < 1 percentage point |
| **Bots**: random, caller, equity (baseline), station, rock, tag, lag, maniac | `ai/agents.py` | only allowed actions (test), reproducible |
| **Evaluation**: duplicate matches, bb/100 with 95% interval, VPIP/PFR/aggression/WTSD/W$SD stats | `ai/evaluate.py` | Tests: identical bots = exactly 0, random bot reliably loses |
| **Bridge to collector**: reconstructed hand → decision points; live state → observation | `ai/replay.py` | tested on synthetic hand |
| **Tournament mode**: same start stack, blinds double every N hands (or fixed list), elimination, placement (simultaneous eliminated: higher stack better, ties shared), payout, duplicate tournaments, ROI with interval | `ai/tournament.py` | 9 tests |
| **Tournament behavior of bots**: push/fold on short stack (threshold per style), tournament info in player view (level, players left, average stack) | `ai/agents.py` | tested |
| **Equity matrix** of all 169×169 starting hand pairings with exact card blocker weights (4000 samples each pair) | `ai/pushfold.py`, `ai/hand_vs_hand.json` | AA–KK 82%, 22–AKo ~52%, AKo–AA ~7% checked |
| **Nash push/fold table**: 1–25 BB, 1–8 players behind, push and call ranges per position | `ai/pushfold.py`, `ai/pushfold_nash.json` | Heads-up exact (exploitability < 0.001 BB/hand); 10 BB: SB pushes 58.3%, BB calls 37.4% |

First contest of strength (3000 hands, Seed 1): tag +140 bb/100 (statistically significant), lag +51, rock +36, equity +20,
maniac −62, station −185 (statistically significant). The other differences are not yet statistically significant at this hand count.
Tempo: approx. 50–135 hands/s depending on the bots (the equity bot calculates the most).

First tournament contest of strength (180 tournaments, 3000 chips, 10/20 doubled every 10 hands, 50/30/20): rock +57% ROI,
tag +39%, lag +21% (all statistically significant), maniac −14%, station −25%, random −78%. In the tournament the tight style wins, in cash games the tight-aggressive style—survival pays off with 3 paid places.

Push/Fold model: chip EV (no ICM). Heads-up is the exact equilibrium. With multiple opponents behind, the equilibrium is that of a simplified model (at most one caller, caller independent)—max exploitability in
the model 0.013 BB. The bots use the table; they shift styles (rock plays "as if he had 1.6× as many BB").

Limits: PokerTH's exact blind structure (doubling? every how many hands or minutes?) has not been verified;
the “↑8” indicator is cautiously interpreted live as "hands until the raise" and marked as uncertain. Push/Fold
now uses the Nash table (see above). The bots are style replicas, **not** the real PokerTH bot code;
their comparison to real PokerTH bots is level 4 (requires your recordings).

Next levels: 4 opponent models from recordings and recreation of the PokerTH bots; 5 learning agent (PPO self-play,
later CFR); 6 model registry with adoption only after passing evaluation.

## You against the bots

```
pc.cmd play                                         Sit&Go against tag, rock, lag, station, maniac (rated)
pc.cmd play --coach                                 plus Push/Fold hints AFTER your decision
pc.cmd play --mode cash --opponents tag             Heads-up cash against tag (rebuy at 0)
pc.cmd play --opponents tag,tag:tag2,maniac --stack 1500
pc.cmd play-stats                                   your bb/100, playing style, tournament places, Push/Fold errors
```

Inputs: `f` Fold · `c` Call/Check · `k` Check only · `r 120` Raise to 120 · `r` Minimum raise · `p` Pot ·
`a` All-in · `?` Help · `q` Quit. You see only what a player at the table sees; opponent cards only in showdown.
Each hand is saved in `data\play\`. Rated tournaments go with placement into the league (your rating).

## League, rating, benchmark

```
pc.cmd league show                                  Table + progress graph data\league\report.html
pc.cmd league run --rounds 30                       League games (Duplicate Sit&Go) among all active bots
pc.cmd league add tag-v2 "tag?push_bb=15&bluff=0.15"   register new bot version
pc.cmd league bench [name]                          Benchmark against fixed opponents (Cash + SNG)
pc.cmd league retire tag-v1                         remove from automatic rounds
```

Metrics:
- **Rating** (Weng-Lin/Plackett-Luce like OpenSkill, Elo-like scale, start 1500 ± 400): development curve.
  “safe” = rating − 3σ; sorting is done accordingly.
- **Benchmark** versus fixed opponents with fixed seed: bb/100 (cash) and ROI (SNG) with 95% interval—comparable across
  versions, no drift.
- **Push/Fold loss**: wasted BB per short-stack decision (≤ 15 BB) versus Nash, 0 = perfect.
- Playing style (VPIP/PFR/Aggression) in benchmark.

First league (30 games): rock > tag > lag > equity > maniac ≈ station > random. Push/Fold loss reveals a
concrete weakness: tag switches to Push/Fold only at 12 BB (0.05 BB/situation lost), lag at 15 BB (0.004).
Candidate to try: `league add tag-v2 "tag?push_bb=15"`.

## Self-improvement (Level 5, Step 1)

```
pc.cmd train cem                                    Optimize style parameters + admission test + optionally league
pc.cmd train cem --generations 15 --start lag --champion tag
pc.cmd train cem --resume data\train\<folder>       continue aborted training
pc.cmd train gate "tag?push_bb=15" --champion tag   test arbitrary variant
pc.cmd train cem --opponents fixed                  old mode: always the same fixed pool
```

Process: Cross-Entropy Method over 10 style parameters (VPIP, PFR, value/raise thresholds, call tolerance, bluff,
bet sizes, Push/Fold threshold and factor). Each candidate plays Duplicate Sit&Gos; all candidates of a
generation get the same cards and the same opponent tables.

**Opponents (default `--opponents league`):** For each card scheme a separate table with 5 opponents is drawn from all
active league bots. Stronger (higher rating) appear more often, weak ones never very rarely (minimum weight 0.1),
and in 20% of tables the current training state himself is present (self-play). New `opt-...` bots become
training opponents of the next generation this way (league training like in AlphaStar). Background: opt-1,
trained only against fixed pool, was the tournament best there, but was below tag in the league
(overfitting). In the admission test the title holder is not an opponent at the table. Then
**admission test** on 48 fresh card schemes, paired against the title holder: only with statistically significant
lead (95% interval of difference > 0) is the bot entered as `opt-...` into the league.
Example: `tag?push_bb=15` failed (−4.6% ROI, interval −12.8 … +3.7)—the guess from the
Push/Fold metric was not confirmed.

**Admission test rule:** do not repeat with new seeds until it passes by chance. For borderline results at most one pre-defined,
larger confirmation test, whose result counts.
(opt-1 was admitted after a second test with 120 schemes, the first with 48 narrowly failed.)

History:
- opt-1 (fixed pool, start tag): Gate vs tag +8.9% [1.1; 16.7] → league. Benchmark-SNG best bot, but league rating below tag → overfitting to pool.
- League training 1 (start tag, 10 × 12 candidates × 16 schemes, 22 min): Gate vs rock on 120 schemes +5.2%
  [−3.1; 13.4], confirmation on 300 schemes −5.3% [−10.1; −0.5] → failed. ROI fluctuations between generations
  (+5% … +47%) were card luck; tables were equally strong.
- League training 2 (start rock, 24 schemes/generation, 36 min) → opt-2: Gate vs rock +8.5% [1.0; 16.0], league
  afterwards only 4th place, confirmation on 300 new schemes +1.9% [−2.2; 6.1] → removed from league
  (`league retire`). Found during this: all gates had used the same test set (Seed 777), which was worn down across
  multiple candidates. Now each training run has its own (100000 + `--seed`).

Conclusion: With the 10 style parameters, the limit is roughly reached—rock, tag, and opt-1 lie within a few percent,
fiddling further with controls only produces noise. More playing strength requires a
bot that learns its decisions itself (next step).

Long runs keep the computer awake (standby would disconnect the USB stick; happened once). Shutdown with
`pc.cmd --allow-sleep ...`. Training saves its state after each generation (`--resume`).

Limit: optimized against bots—whether it works against humans will be shown only in games against you and real
PokerTH recordings. Next step: neural agent (self-play) using the same pipeline.

## Learning bot (neural net, level 5 step 2)

```
pc.cmd train bc --teacher rock --run nn-1             Imitate teacher bot -> data\rl\nn-1\ckpt_000000.pt
pc.cmd train bc --dataset pluribus --run pros-1       Imitate from real hands (all players)
pc.cmd train bc --dataset pluribus --players Pluribus --run plu-1    only Pluribus itself
pc.cmd train rl --run pros-1 --iterations 200 --anchor-coef 0.3      Self-play (PPO) with leash
pc.cmd train rl --run nn-1 --iterations 300           continue until iteration 300
pc.cmd data pluribus                                  Import Pluribus hands -> data\datasets\pluribus.npz
pc.cmd data agree nn-1 --ckpt 0,100,200               Measure agreement with Pluribus
pc.cmd league add pros-bc "nn?run=pros-1@0"           Network (run@checkpoint) into league
```

**What it sees** (`ai/features.py`): 46 preprocessed numbers instead of raw cards – equity (preflop table or
Monte-Carlo), hand type, board texture, pot odds, stack/pot, effective stack, position, raises/aggressor,
tournament situation. **What it can do:** Fold, Check/Call, Raise ½ / 1 / 2 pot, All-in. **Network** (`ai/nn_agent.py`):
46 → 128 → 128 → 6 action probabilities + 1 value. Learned with PyTorch (CPU, stored on the stick),
played with a numpy copy (fast, 12 processes). Played mixed, randomness derived from the situation
(Duplicate-fair).

**How it learns** (`ai/rl.py`): (1) Imitation of a teacher or a dataset → Checkpoint 0. (2) PPO: per
iteration 96 Sit&Go games against league tables and earlier versions of itself (30%), reward = chip change per
hand. Optional **Leash** (`--anchor-coef`, piKL as in Meta’s Cicero): penalty for deviation from the anchor (default:
own Checkpoint 0), only for stacks ≥ 25 BB because the Pluribus anchor only has experience there.

**Storage:** `data\rl\<lauf>\` – `config.json`, `bc.json`, `log.jsonl` (per iteration), `eval.jsonl` (every 10 iterations:
ROI against fixed pool + Pluribus agreement), `ckpt_<It>.pt` (about ~100 KB each), `state.pt` (resume),
`gate_<It>.json`. Played hands are not saved.

**Data:** PHH dataset from Univ. Toronto (MIT), github.com/uoftcprg/phh-dataset. Only the Pluribus part is
fetched under `data\external\phh-dataset` (10,000 hands Pluribus vs. pros, 6-max, 100 BB, **all cards known**).
Every 10,000 hands are run through our engine with identical end stacks (±1 chip on split pots) – an
independent verification that the engine is correct. 91,356 decisions, of which 15,169 are by Pluribus.
HandHQ (21.6 million real online hands 2009) shows cards only at showdown → not for imitation, but for
player profiles of real winners (next step).

Results so far:
- **nn-1** (imitated rock, PPO without leash): against the fixed pool from +23% to +84% ROI, but qualifying test
  against rock after 100 iterations −3.7%, after 300 iterations −8.5% → failed. Pluribus agreement dropped from 63%
  to 13%: It hardly folds anymore and raises almost always – it learned to exploit our bots' weaknesses,
  not to play good poker. The improvement against own starting point was real (+23% without rock at the table).
- **plu-1 / pros-1** (imitated Pluribus and all players): 84% agreement with Pluribus; in Sit&Go against rock −9.2%
  respectively −3.8% (not significant) – Pluribus does not know short stack tournament play.

## Testbench, speed and CFR

```
pc.cmd bench run rock                                  Bot on the testbench (league name or specification)
pc.cmd bench run "nn?run=pros-1@200" --name pros-1@200 --exploit     including exploiter test
pc.cmd bench show                                      Table -> data\bench\report.md
pc.cmd train exploit "nn?run=pros-1@200"               exploiter test only
pc.cmd train cfr --run cfr-1 --rounds 400              Equilibrium via Monte-Carlo CFR (Pluribus method)
```

**Testbench** (`ai/bench.py`): fixed test sets that never change – `fest48` (48 Sit&Go games versus fixed pool),
`mix96` (96 Sit&Go games at mixed, stronger tables including opt-1 and pro imitators), `cash` (300 duplicate hands,
bb/100), `pluribus` (agreement), optional `exploit`. The table shows per test set the **paired difference to rock**
on the same cards. One run takes about 40 s. PPO runs place themselves on the testbench every 50 iterations, CFR
runs every 25 rounds. Acceptance into the league still requires the qualifying test with fresh cards.

**Speed:** Profile showed 95% of the time in Monte-Carlo equity (Python hand evaluation ~70 µs). New:
`fastpoker.py` with numba (machine code), same ranking as before (test over 40,000 comparisons).
Result: ~37 → ~3100 hands/s per core (**~85×**), PPO iteration 11 s → 1 s, testbench 40 s.

**CFR** (`ai/cfr.py`): self-play where in every own decision all possible actions are played through
(copy of the game state); actions that would have been better are played more often. The average approaches
an equilibrium – hard to exploit, no matter against whom. Like Pluribus: external sampling, linear CFR,
abstraction (street, hand strength class, position, player, pot odds, stack, raises, aggressor). Hands with
2–6 players and 3–150 BB. Storage `data\rl\<lauf>\cfr_state.npz` (resume), `cfr_avg.npz` (strategy).
League: `cfr?run=<lauf>`. **Do not start two trainings simultaneously:** each uses all cores with own processes;
together with testbench 16 GB RAM was insufficient (abort “Not enough system resources”, 26.10.). Cause
was also a loading error (compressed arrays unpacked newly per entry), fixed. Difference to PPO: PPO exploits
current opponents, CFR seeks robustness.

First testbench table (mix96, Δ to rock): nn-1@100 +19 (but Pluribus agreement 15%, after 300 iterations −3 → overfitting), pros-1 with leash @0 −20 → @100 +3 → @200 +8 at stable 80% Pluribus agreement.

## Robustness, ranges and search (status evening 26.10.)

```
pc.cmd train rl --run X --random-share 0.3 --exploit-every 50     Random opponents + exploiter in training
pc.cmd bench run "search?bp=pros-2@300,worlds=16" --name search-2   Network + search on the testbench
```

**Exploiter test** (specifically trained bot against the test subject, ROI vs. 5 copies; the smaller, the more robust):
pros-2 **+3.8%** [−7; +15] – rock **+100%** [+86; +115] – CFR table (round 200) +69% [+59; +78].
pros-2 is thus not only stronger than rock but also hardly exploitable.

**Random opponents** (`--random-share`): seats are filled with style bots with random values (calling station
to perpetual bluffer, `optimize.RANDOM_SPACE`). **Exploiter in training** (`--exploit-every`): every N iterations
an exploiter learns against the current state and then becomes opponent (PSRO/AlphaStar principle, toward equilibrium);
exploitability is found in `eval.jsonl`, exploiter under `<lauf>\expl-<It>\`.

**Ranges** (`ai/ranges.py`): per opponent weights over 1326 starting combinations, shifted by their actions
(Raise/3-bet/Call preflop, Bet/Call/Check per board strength). Equity against these ranges via numba Monte-Carlo.
Example: QJ versus open + 3-bet: 41% vs random hands, 23% vs the ranges. **Features feat-2** = feat-1 + 3
range features; each network stores its version and plays with it (old nets unchanged). Datasets per
version: `pluribus.npz` (feat-1), `pluribus-feat-2.npz`.

**Search** (`ai/search.py`, level 1): `world_from_obs` builds an exact game state from observation + drawn opponent cards
(tested against real states). `SearchAgent`: for each allowed action in 16–24 “worlds” (opponent cards from
ranges) play out the hand to the end with the network as the strategy for all; same worlds for all actions;
the network choice is overridden only with clear advantage (> 2 standard errors). ~0.2 s per decision.
Level 2 (like Pluribus): solve subgames by CFR; opponents may choose continuations at the horizon.

## Training on a Linux server

```
# once on the server
curl -LsSf https://astral.sh/uv/install.sh | sh
# copy project folder WITHOUT tools/ and without collector/.venv, data/ as needed (rl/, datasets/, league/)
chmod +x pc.sh && ./pc.sh --help
nohup ./pc.sh train deepcfr --run dcfr-2 --iterations 300 > dcfr-2.log 2>&1 &
```

Speed rule of thumb: Our trainings use all cores fully. A VPS with 4 *shared* vCPUs is about ⅓ as fast
as the laptop (10 cores) and will be throttled under sustained load – good for long, patient runs without a laptop,
not for speed. For speed: dedicated cores (Hetzner CCX/AX), rent by hour. RAM: about 0.5 GB per
process + Deep-CFR buffer ~1 GB; 8 GB sufficient for 4–6 processes.

## Architecture (data flow)

```
Source (video | images | window)
  -> analyzer.FrameAnalyzer: layout + OCR + cards -> TableSnapshot (field -> value, confidence, raw value, rectangle)
  -> stabilize.Stabilizer: change / transient / unknown events
  -> journal.Session: observations.jsonl (+ supporting image), video segments
  -> reconstruct.reconstruct(journal) -> hands.json     (recomputable at any time)
  -> compare.compare(hands, reference)  -> compare.json/.md (export only here)
  -> advisor.advise(state)              -> recommendations + assumptions
```

Seat numbers: 0 = own seat bottom center, then clockwise (= order of action) up to 9.

## Development

Code: `collector\src\pokercollector\`, tests: `collector\tests\`, test image: `collector\testdata\`.
New table layout: copy profile JSON, adjust anchors/regions, check with `pc.cmd --profile mein.json calibrate bild.png`.
