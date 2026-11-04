# Poker Project “Lynx”: Complete Documentation

Status: **28.10.2026, approx. 11:30 PM**, Addendum 8.6 from 29.10. 2:00 AM. Composed from code, data, and logs on the stick (`<Projektordner>`), working notes, and session history since 25.10.2026.

This documentation describes the actual status. Where something has not been measured or checked, it is explicitly stated. Older documents:
- `PROJECT_HANDOVER.md`: original plan and rules (25.10.)
- `GETTING_STARTED.md`: user manual, status until evening 26.10.
- `GOALS.md`: the five benchmarks
- `data/rl/OVERNIGHT_LOG.md`: protocols of the two night runs

---

## Contents

1. [Goal, Rules, and Principles](#1-goal-rules-and-principles)
2. [Hardware, Environment, Folder Structure, Operation](#2-hardware-environment-folder-structure-operation)
3. [The Collector: visual capture](#3-the-collector-visual-capture)
4. [The AI: engine, bots, networks, training, search](#4-the-ai-engine-bots-networks-training-search)
5. [Live Operation: suggestions, Lynx bar, tournament recognition](#5-live-operation-suggestions-lynx-bar-tournament-detection)
6. [Benchmarks: methodology and all results](#6-benchmarks-methodology-and-all-results)
7. [Chronicle: what was attempted, including failures](#7-chronicle-what-was-tried-including-failures)
8. [Current status, assessment, weaknesses, roadmap](#8-current-status-assessment-weaknesses-roadmap)
9. [Appendix: terms, files, specifications](#9-appendix-terms-files-specifications)

---

## 1. Goal, Rules, and Principles

### 1.1 Goal

The project has three parts:

1. **Collector:** It captures PokerTH web games in the browser **exclusively visually**, i.e., through what is visible on the screen. It reconstructs the hands from this, annotates every detail, and independently verifies the result against the PokerTH log. This is the experiment: Can it be done solely through the image?
2. **Lynx:** a proprietary poker AI that is to become “maximally good.” It is trained in the simulator and is intended to win against humans in PokerTH.
3. **Live Advisor:** While Jakob himself plays, Lynx shows action suggestions (Fold, Check, Call, Raise to X). Jakob makes the decisions and clicks himself.

Lynx is to become generally strong, not just against a specific opponent. Slumbot is explicitly only a benchmark, not a training goal (directive from 28.10.).

### 1.2 Fixed Rules (from `PROJECT_HANDOVER.md`, confirmed by the user)

| Rule | Implementation |
|---|---|
| No browser remote control, no automatic clicks, keys, bets, or actions | The Collector reads only screen pixels (mss). The bar is for display only and never takes focus. There is no input function in the code. |
| No DOM, no network, no memory, no internal game state as source | The source is exclusively the image: Windows OCR, shape comparison, colors. |
| PokerTH log is only an independent reference | It is read only in `compare.py` and `reference.py`, never by the capture component. It is never used for training. The card templates deliberately do not come from export. |
| Never estimate opponent cards or treat them as known | Observation contains only visible information. Ranges are distributions, not facts. |
| Report gaps instead of inventing | Uncertain values are noted in `Observation.uncertain`, gaps and contradictions in every hand. |
| Everything remains local | Data is on the stick, with a backup under `C:\Poker-Backup\Poker-Projekt-Windows`. Only HandHQ or PHH data (download) and the Slumbot API as external services are permitted, both explicitly authorized. |

### 1.3 Methodological Principles Proven Effective

- **Paired measurement:** Two bots play the same cards at the same tables in all seat rotations. The difference per schema is compared to remove most of the luck of the cards.
- **Always specify 95% confidence intervals.** “Better” applies only if the lower bound of the difference is above zero.
- **Do not repeat the gate test until it randomly passes.** If the result is close, at most one pre-set larger confirmation is performed, and its result applies. This was introduced after experiences with opt-1 and opt-2 (section 7).
- **Each training run has its own test set seed** (100000 + training seed). Previously, all gates shared seed 777, and the test set “wore out.”
- **Fixed test bench sets for tracking, fresh cards for decisions.** Being ahead on a frequently viewed set can mean luck with exactly these cards.
- **New live standard only after passed confirmations:** league gate plus human tables, both predefined and one-off.
- **Results of individual hands are never training labels.**

---

## 2. Hardware, Environment, Folder Structure, Operation

### 2.1 Hardware and System

| | |
|---|---|
| Laptop | Intel i5-1335U (10 cores: 2 performance + 8 efficiency, 12 threads), 16 GB RAM, **no GPU** |
| System | Windows 11 Pro (10.0.26200), PowerShell 5.1 and Git Bash |
| Stick | Intenso cMobile Line, label "POKER", exFAT, usually drive `D:` |
| Browser | Google Chrome, window “PokerTH Web Client — Free Texas Hold’em in Your Browser” |
| Possible later | Hetzner VPS (4 shared vCPUs, 8 GB, about 1/3 speed of the laptop), a new ThinkPad (4 cores, 8 threads, 16 GB) |

### 2.2 Runtime Environment (all on the stick, nothing installed)

- **Python:** `tools\python\cpython-3.12.12-windows-x86_64-none\python.exe`, portable
- **uv:** `tools\uv\uv.exe` with offline cache `tools\uv-cache`
- **Project venv:** `collector\.venv` (Python 3.12)
- **Dependencies** (`collector/pyproject.toml`): numpy ≥ 2.1, opencv-python, mss, torch (CPU index), numba, pillow, winrt packages for Windows.Media.Ocr; pytest for tests
- **Start scripts:**
  - `pc.cmd`: all commands, uses `uv run --no-sync` to avoid disturbing running trainings
  - `tests.cmd`: all tests
  - `sync.cmd`: update packages, run only if nothing else is running
  - `pc.sh`: Linux or server

### 2.3 Folder Structure

```
<project folder>\
  PROJECT_HANDOVER.md   plan & rules (25.10.)
  GETTING_STARTED.md           operation (up to 26.10.)
  GOALS.md              the 5 benchmarks
  DEVELOPMENT_LOG.md      this document
  pc.cmd / tests.cmd / sync.cmd / pc.sh
  train_*.sh, night*.sh, morning.sh, morgen_lynx3.sh, slumbot_long.sh, measure.sh   training run scripts
  collector\
    pyproject.toml
    src\pokercollector\           Collector (capture) ~25 modules
      ai\                         AI ~35 modules
      profiles\pokerth_web_v1.json  table profile
    tests\                        31 test files, 171 tests (all green, evening 28.10.)
    testdata\                     test image(s)
  data\
    sessions\<UTC time>_<id>\     recorded PokerTH sessions
    rl\<run>\                    training runs (checkpoints, logs, gates)
    bench\                        test bench: results.jsonl, report.md, slumbot\*.jsonl, *.txt
    league\                       league: players.json, games.jsonl, report.md/html
    humans\                       HandHQ evaluation, human bots (mensch-25nl.json)
    datasets\                     pluribus.npz, pluribus-feat-2.npz
    external\phh-dataset          Pluribus portion of PHH dataset
    ziele\pokerth.jsonl           real PokerTH tournaments (goal 1)
    live\leiste.json              position of the Lynx bar
    sim\, play\, train\, templates\
  tools\                          Python, uv, cache
```

Code size: about **13,800 lines** of Python in `src` (Collector about 4,800, AI about 9,000), plus tests.

### 2.4 Most Important Commands

**Collector and Live:**
```
pc.cmd windows PokerTH                         list windows
pc.cmd live --bar                              Live: capture + Lynx suggestions in the bar (+ sound)
pc.cmd live --bar --silent                     without sound
pc.cmd live --bar --mixed                      suggestion from mixed strategy instead of most probable action
pc.cmd live --bar --no-entry                   do not automatically enter end of turn
pc.cmd live --hwnd <Number>                     specific window
pc.cmd live --advice --agent <Bot>             suggestions only in console, different advisor
pc.cmd bar-demo [--silent] [--seconds N]       demo bar without table
pc.cmd live-replay <session>                    play recording like live (suggestions + opponent model)
pc.cmd analyze recording.mp4                     evaluate video -> new session
pc.cmd reconstruct last                         reconstruct hands anew
pc.cmd compare last export.pdb                   verify against PokerTH log (compare.md)
pc.cmd inspect-reference export.pdb              show schema of a log file
pc.cmd calibrate screenshot.png                   check recognition on an image (overlay)
pc.cmd harvest-cards image1.png ...               learn card templates
pc.cmd verify last                               checksums
```

**Simulation, League, Training:**
```
pc.cmd sim agents | match | hand | tournament | pushfold | review
pc.cmd play [--coach]                           play against bots yourself (terminal)
pc.cmd league show | run | add | retire | bench
pc.cmd train bc | rl | cem | gate | cfr | deepcfr | exploit | humans-fit
pc.cmd data pluribus | humans | agree
```

**Test Bench and Goals:**
```
pc.cmd bench run <bot> --sets mensch480,precise [--exploit] [--name X]
pc.cmd bench show                               table -> data\bench\report.md
pc.cmd bench compare A B                        paired comparison across all common sets
pc.cmd bench slumbot "<spec>" --name X --hands N --workers 4    against Slumbot (continuable)
pc.cmd bench slumbot x --name X --hands 0       display evaluation only
pc.cmd bench goals <bot> [--measure] [--exploit] [--slumbot NAME]
pc.cmd bench tournament <Place> --players 6 [--bot X] [--note "..."]   manual tournament entry
```

Single tests: `cd collector && PYTHONIOENCODING=utf-8 ../tools/uv/uv.exe run --quiet --no-sync pytest -q -p no:cacheprovider tests/test_x.py`

### 2.5 Pitfalls (each occurred at least once)

| Problem | Cause | Remedy |
|---|---|---|
| **Stick fails** ("No Media", event "disk 11 controller error"): 27.10. 07:10, 28.10. 04:15, 28.10. afternoon | USB power saving. Windows disconnects the stick during standby or black screen (Modern Standby). | On 28.10., **selective USB power saving was disabled via `powercfg` for both plugged in and battery**. Long runs keep the computer awake (`system.keep_awake`, SetThreadExecutionState). After a failure, only reconnecting helps; `pnputil` does not work without admin rights. In emergencies, work from SSD or backup. |
| **Memory guardian by development tooling** terminates background jobs when RAM is low | 16 GB is not enough for training plus test bench plus Slumbot plus analysis simultaneously | Run sequentially, reduce workers (4 instead of 6). Often only the shell is terminated and the compute processes continue, so check the process list. Do not restart on your own after an abort. |
| **Stopped monitor kept running** (28.10.) | `TaskStop` on one monitor did not terminate child processes. The chain ran twice, Slumbot and PokerTH comparison thus ran concurrently twice. | Check process list after stopping (`Get-CimInstance Win32_Process`). |
| `&` in bot specifications | cmd splits the line | Use Python scripts for `hus?bp=...&iters=...`. Write network specs without `&` (`nn?run=lauf@ckpt`). |
| Running trainings load modules lazily | A code refactor during a run can disturb it | Develop in a copy `dev/` (PYTHONPATH) or wait until the run finishes |
| Live only records in foreground | mss captures the screen. An overlapping window would also be recorded. | The PokerTH window must be active and uncovered, otherwise there is a gap ("source lost"). |
| Window width below approx. 1500 px | Recognition becomes unreliable (below approx. 80% of reference size) | Keep window large or maximized |

---

## 3. The Collector: visual capture

### 3.1 Data flow

```
Source (WindowSource live | VideoFileSource | ImageDirSource)            capture.py
  -> FrameAnalyzer: layout + OCR + cards -> TableSnapshot                analyzer.py, layout.py, ocr.py, cards.py, glyphs.py, parse.py
       (per field: value, confidence, raw value, image area, method)
  -> Stabilizer: change / transient / unknown                            stabilize.py
  -> Session/Journal: observations.jsonl (+ evidence image), video segments   journal.py
  -> Reconstructor: hands with actions, gaps, contradictions             reconstruct.py   (recomputable anytime)
  -> compare(hands, reference log)  (only here the log is read)          compare.py, reference.py
  -> live: LiveBot -> Observation -> Lynx -> bar                         ai/live.py, ai/replay.py, overlay.py
```

`pipeline.py` connects everything. In `LiveRunner` (live), recording has priority: frames go immediately into the recorder; analysis runs in its own thread with a limited queue. If analysis lags, **analysis frames are dropped (counted), never video frames**. The session starts automatically when the table is stably detected, and ends about 20 seconds after it disappears.

### 3.2 Components in detail

| Module | Task | Technology / Details |
|---|---|---|
| `capture.py` (335 lines) | Image sources, segmented recording | `WindowSource` via mss on client area. Checks if window is in foreground, otherwise gap. Video as `mp4v` (OpenCV) in segments with timestamp per frame. Windows.Graphics.Capture (overlay-safe) was planned but never built. |
| `layout.py` (279 lines) | Table, seat panels, board, marker (D/SB/BB), action bar | Seats are **not searched at fixed positions** because PokerTH arranges them differently depending on number of players. All panels are recognized; the largest one at bottom center is seat 0 (Jakob), the others are numbered clockwise around table center (= action order). **SeatMemory** keeps numbers stable even if a panel disappears. Scale is derived from measured panel width. Tested on 10-player (test image), 6- and 4-player tables. |
| `ocr.py` (221 lines) | Text recognition | Windows.Media.Ocr via winrt, no additional program. Cache for unchanged areas, alternative approaches (enlargement, contrast). |
| `parse.py` | Amounts, blinds, street, game/hand number, action words | including typical OCR misreads (e.g. `$O` instead of `$0`) |
| `cards.py` (306 lines) + `glyphs.py` (80 lines) | Card slot (empty/back/open), rank, suit | **Rank:** Windows OCR poorly delivers isolated single characters (measured: 3 of 7 ranks). Therefore pattern matching against the 13 ranks, drawn in several standard fonts, normalized and compared by correlation, including aspect ratio ("10" wide, "7" narrow). Also learnable templates (`harvest-cards`). **Suit:** red/black from ink, shape via templates or contour heuristics. |
| `analyzer.py` (347 lines) | Frame → TableSnapshot | field keys including `table.found`, `info.street`, `info.game_hand`, `info.blinds`, `info.total`, `pot.total`, `board.cards`, `hero.buttons`, `seat.<n>.present/name/stack/bet/folded/active/cards/action_label/marker` |
| `stabilize.py` (120 lines) | temporal stabilization | A value is considered stable only after `min_frames` and `min_ms`. Short-lived values are **not averaged out**, but reported as `transient`. Unreadable replaces a stable value only after `unknown_after_ms`. |
| `journal.py` (218 lines) | session folder | `observations.jsonl` (append-only, immutable), `evidence/` (image crop per event), `video/segment_NNNN.mp4` + `.frames.jsonl`, `hands.json/.md`, `index.sqlite`, `manifest.json` (SHA-256), `session.json` (source, versions, gaps, errors, statistics) |
| `reconstruct.py` (735 lines) | rule-based hand reconstruction | State machine over field events, details in 3.3 |
| `reference.py` (270 lines) | import PokerTH log (SQLite `.pdb`) | Tables Game/Player/Hand/Action according to PokerTH desktop source. The schema is now used on real web exports (comparison 26.10.), card coding 0..51 per suit d,h,s,c. |
| `compare.py` (281 lines) | field-wise comparison | Precision/Recall per field, amount semantics ("on" vs "additional"), visibility class. What is in the log but not visible (covered cards) does not count as error. |
| `advisor.py` / `poker.py` | baseline recommendation, hand evaluation | Equity against random hands plus pot odds. Deliberately the simplest honest baseline, now replaced by Lynx. |
| `fastpoker.py` (201 lines) | fast hand evaluation, Monte Carlo equity | numba, cards as 0..51, evaluation as integer (category << 20 | ranks). Ranking order identical with `poker.evaluate`, tested over 40,000 comparisons. About 85× faster. |
| `system.py` | prevent standby | SetThreadExecutionState (system + display), because in Modern Standby turning off display leads to standby |

### 3.3 Hand reconstruction (`reconstruct.py`, version `reconstruct-2`)

- **Hand boundaries:** defined by the hand number (`info.game_hand`, "observed") or derived ("inferred"). PokerTH switches the hand number before the table is cleaned up. Therefore, seat events are buffered up to **SETTLE_S = 2.5 s** until markers and blinds are set ("settling in"). Afterwards, starting stacks, dealer, SB/BB are set from the table state and the buffered events are replayed in order.
- **Source of each action** (provenance):

  | Source | Meaning |
  |---|---|
  | `observed_label` | Action label read at the seat (e.g., "Check") |
  | `observed_fold` | Fold via label or hidden panel |
  | `derived_bet` | From the change of visible bet |
  | `derived_turn` | Change of highlight without bet change → Check |
  | `derived_stack` | From a stack increase (win/refund), also credited after hand change |
  | `inferred_gap` | The order requires an action that was not seen |
  | `inferred_street_end` | Inferred at street end: who is still in the hand has called or checked. The final call is practically never seen because bets are collected immediately. |

- **Time constants:**
  - TURN_GRACE_S 0.9 s: Waiting time after a highlight change to see if a bet follows
  - SWEEP_WINDOW_S 2.0 s: A bet drops to 0 near a street change → that is collecting chips, not an action
  - LATE_S 1.5 s: A late fold or bet belongs to the previous street
- **Stack balance per seat:** Start = End − wins + bets. Deviations are marked as contradictions.
- **Status of each hand:** `complete` or `partial`, with reasons, e.g. "Dealer not seen", "Winner not observed", "n gaps".
- **Consensus across multiple images:** for board and player cards (`board_votes`, `card_votes`), so that a single erroneous image does not fix a card

### 3.4 Accuracy against the PokerTH log (independent reference)

First real capture on 26.10.2026 (6-player table against PokerTH bots, 12 hands in the log). The same session was processed twice: once with the morning version, once after the day's corrections (seat memory, pattern comparison for ranks, reconstruction timing).

| Field | first analysis (`20261026-220836`) | after corrections (`20261026-224738`) |
|---|---|---|
| Hands assigned | 12/12 | 12/12 |
| Blinds | 100 % | 100 % |
| Dealer | 11 % | **92 %** |
| SB/BB seat | 0 % / 11 % | **100 % / 100 %** |
| Board cards | Precision 60 %, Recall 5.5 % | **100 % / 100 %** (55/55) |
| Shown cards (showdown) | 0 % | **100 %** (2/2, 11 not visible) |
| Actions | Precision 18 %, Recall 5 % | **Precision 88 %, Recall 89 %** (147 hits, 18 missing, 20 extra) |
| Action amounts | – | **98.7 %** (76/77) |
| Starting stacks | 0 % | **90 %** (53/59) |
| Winner | 0 % | **Recall 100 %, Precision 87 %** (13 hits, 2 extra) |

A 4-player table also worked on the same evening (sessions `230753`, `231440`). A formal comparison for that is not available as compare.md.

**Remaining error classes** (analysis from 26.10.):
1. **Blinds as actions:** The log records "posts SB/BB" as an individual action. The reconstruction knew SB/BB but did not write it as an action. Since then, blinds are output as `post_sb`/`post_bb`.
2. **Checks too late, duplicate, or at wrong seat:** The "Check" label sometimes remains displayed into the next street or is visible so briefly that it is skipped at 4 frames/s. Thus, most missing or extra checks occur. **Open:** Checks sometimes land on the wrong seat.
3. **Incorrect starting stacks:** The stack is read before the last pot is credited; there are also OCR outliers (e.g., "9511" instead of "511").

**Known semantic pitfalls** (important for live, fixed 28.10.):
- `info.total` ("total") is the **collected pot excluding bets from the current street**.
- `pot.total` (center of table) is missing entirely in some sessions (`230753`, `231440`) and has OCR outliers, e.g. 9280 instead of 280.
- `replay.live_pot()` therefore uses `pot.total` only if it matches `info.total + Einsätze`; otherwise `info.total + Einsätze`. `LiveBot.observation` takes the pot from the reconstructed live sequence if the image pot is below 90 % of that.

**PokerTH format** (from the log): PokerTH Web starts with **1000 chips at 10/20 = 50 BB, blind increase after 9 hands**. From that, the test format `pokerth` or `mensch` was derived.

**Timing metrics:**
- Analysis on screenshot (1905×980): first analysis approx. 200 ms, unchanged frames approx. 40 ms
- Live at 4 fps alongside ongoing training: 718 analysis frames skipped, video remained complete

### 3.5 Not yet tested by the collector

- **Diamonds and Clubs:** So far only Spades and Hearts are reliably checked against real images. However, in comparisons all 55 board cards matched. A systematic test of all four suits is missing.
- **Special cases:** Side pots, split pots, seat changes and connection losses are not specifically tested.
- **Table sizes:** 2, 3, 7–10 players live untested. The 10-player table was only checked on the test image.
- **Overlay:** An overlay-proof capture (Windows.Graphics.Capture, C#) has not been built.

---

## 4. The AI: Engine, Bots, Networks, Training, Search

### 4.1 Common interface

`ai/observation.py`: **Observation → Action**. The same observation is produced in the simulator, replay, and live from the collector. It contains own cards, board, stacks, bets, positions, the public action history, and `uncertain`, never opponents' hole cards. Raises are given as the "to" amount. `clamp_action` makes each action conform with the rules.

### 4.2 Engine and tools

| Module | Content |
|---|---|
| `engine.py` (348 chars) | NLHE for 2–10 players. Heads-up order (Button = SB, preflop first, postflop last). Minimum raise = last full raise (≥ 1 BB). A short all-in does not restart the betting round. Side pots, uncalled chips returned, odd chips to the first winner left of the button. Cards: seat i receives `deck[2i], deck[2i+1]`, board `deck[20:25]`, ensuring Duplicate fairness. `Hand.clone()` for search and CFR. **Validation:** 18 rule tests, 600 random hands with chip conservation, **all 10,000 Pluribus hands from the PHH dataset run with identical end stacks** (±1 chip for split pots). Fixed bug: A short all-in in BB forced SB to top up. |
| `tournament.py` (304 chars) | Sit&Go: same starting stacks, blinds double after N hands or by list, elimination, placement (simultaneous eliminations: larger starting stack better), payout, ROI with interval, “moving button” |
| `evaluate.py` (189 chars) | Duplicate cash matches, bb/100 with 95% CI, VPIP/PFR/Aggression/WTSD/W$SD |
| `tables.py` | Preflop equity of all 169 classes against 1–9 random opponents (deviation < 1 percentage point) |
| `pushfold.py` (337 chars) | Equity matrix 169×169 with exact blocker weights (`hand_vs_hand.json`). Nash push/fold via fictitious play for 1–25 BB and 1–8 players behind. HU exact (exploitability < 0.001 BB/hand), e.g. 10 BB: SB pushes 58.3%, BB calls 37.4%. Multiway as simplified model (max one caller), max exploitability in model 0.013 BB. Chip-EV, **no ICM**. |
| `league.py` (297 chars) | League with Weng-Lin/Plackett-Luce rating (like OpenSkill), display 1500 + 48·(μ−25), “safe” = rating − 3σ. One league game is a duplicate sit&go schema over all rotations. `players.json` contains 17 entries (style bots, opt-1/2, nets). The league report (`report.md`) is outdated (90 games, as of 26.10.). The league mainly serves today as opponent pool and gate registry. |

### 4.3 Bot Pool (`agents.py`, 323 chars)

- **Rule Bots:**
  - `random`, `caller`, `equity` (baseline)
  - Style bots `station`, `rock`, `tag`, `lag`, `maniac` (based on PokerTH bot types, not their code)
  - Style parameters: vpip, pfr, value_margin, raise_margin, call_slack, bluff, bet_size, open_size, push_bb, nash_stack_factor, plus `respect` and `sticky` (call-down)
  - Push/fold per Nash table under `push_bb`
  - Random derived from seed, hand, and history length: same situation → same decision (duplicate-fair)
- **Random style bots** (`optimize.RANDOM_SPACE`): rolled parameters from calling station to chronic bluffer, for robustness in training
- **NASH_BOT** = `tag?push_bb=40&nash_stack_factor=1`: plays only push/fold under 40 BB per Nash, as endgame benchmark
- **Human bots** (`humanbots.py`, `data/humans/mensch-25nl.json`): see 4.4

### 4.4 Real Player Data (allowed: PHH / HandHQ)

**Pluribus dataset** (PHH format by Univ. Toronto, MIT License, `phh.py`):
- 10,000 hands of Pluribus vs pros, 6-max, 100 BB, all cards known
- 91,356 decisions, of which 15,169 by Pluribus
- Used for behavior cloning (`pluribus.npz`, `pluribus-feat-2.npz`) and as anchor or leash in PPO
- Metric “Pluribus match”: How often does the network choose the same action?

**HandHQ** (`humans.py`, `pc.cmd data humans`, 27.10.):
- PokerStars + Party, 25NL, **5.72 million hands, 121,391 players**
- Cards known only at showdown, imitation thus impossible. Measured: **how** humans play (HUD stats per player).
- **Data traps:**
  - PokerStars `winnings` missing limp pots
  - Party `winnings` contains rakeback
  - “????” appears in the middle of history at all-in
  - Antes and straddles skipped
- **Six player types and their human bots** (target vs achieved after CEM adjustment):

| Bot | Type | Share | VPIP | PFR | Agg | Fold to Bet | 3-Bet | C-Bet | WTSD |
|---|---|---|---|---|---|---|---|---|---|
| human-1 | Nit (very tight) | 27 % | 15/16 | 7/4 | 73/81 | 66/75 | 2/0 | 71/79 | 25/24 |
| human-2 | Average | 25 % | 20/15 | 14/14 | 76/74 | 62/53 | 5/3 | 73/66 | 26/33 |
| human-3 | Average | 17 % | 21/20 | 9/11 | 63/45 | 57/49 | 3/2 | 50/48 | 30/20 |
| human-4 | Passive casual | 14 % | 31/43 | 7/13 | 62/66 | 49/48 | 2/0 | 76/74 | 33/23 |
| human-5 | TAG/Reg | 9 % | 9/8 | 8/7 | 80/78 | 71/58 | 4/2 | 79/85 | 39/39 |
| human-6 | Average (loose) | 9 % | 37/35 | 19/19 | 69/74 | 48/50 | 7/5 | 68/79 | 32/30 |

(Values in %, “Target/Bot”.) The preflop part is well matched. Postflop individual values fit less, e.g. WTSD for human-3 and human-4. In version 1 the style bots were calling stations (fold to bet 6–17% instead of 50–70%), so parameters `respect` and `sticky` were added. For each type the better version from v1 and v2 was adopted.

### 4.5 Features, Actions, Network

**Features** (`features.py`): preprocessed instead of raw cards.

| Version | Count | Content |
|---|---|---|
| feat-1 | 46 | Equity (preflop table or Monte Carlo vs random hands), hand type, board texture, pot odds, stack/pot, effective stack, position, raises/aggressor, player count, tournament situation |
| feat-2 | 49 | + Equity against estimated **ranges** of opponents, distance to random equity, tightness of ranges |
| feat-3 | 57 | + 8 features from **opponent model** (VPIP, PFR, aggression, fold to bet, toughness of current opponent; average opponents in hand) |

Each version extends the previous only at the end. `widen_net` sets new inputs to 0, so the network initially plays identically.

**Actions:**
- **act-1 (6 actions):** Fold, Check/Call, Raise ½ pot, Raise pot, Raise 2× pot, All-in
- **act-2 (8 actions):** additionally Raise ⅓ pot and Min-raise. New actions start as copy of “Raise ½” with logit −2.
- Fold is masked when checking is allowed. Mask contains no duplicates to Min-raise.

**Network** (`nn_agent.py`, version `nn-mlp-1`):
- MLP: features → 128 → 128 (ReLU) → policy (6 or 8 logits) + value (1)
- Trained with PyTorch on CPU, played back with numpy copy (fast, many processes)
- Played **mixed** (sampling by probability, randomness from situation); live **greedy** (most probable action)
- Spec: `nn?run=<Lauf>@<Checkpoint>`, one checkpoint about 100 KB

### 4.6 Training (`rl.py`, 590 chars, version `ppo-1`)

1. **Behavior Cloning:** Imitation of a teacher bot or the Pluribus dataset → Checkpoint 0
2. **PPO:**
   - Many Sit&Go games are played in parallel per iteration
   - Reward per hand = chip change / starting stack × reward_scale
   - GAE with γ = 1 within a hand
   - Optimizes **chip EV, not tournament payout** (no ICM yet)

**Hyperparameters** (as of lynx-3):

| Parameter | Value | Parameter | Value |
|---|---|---|---|
| hidden | 128 | Tournaments/Iteration | 512 |
| Learning Rate | 3e-4 | Epochs | 4 |
| Minibatch | 2048 | Clip | 0.2 |
| vf_coef | 0.5 | ent_coef | 0.01 |
| λ (GAE) | 0.95 | max_grad_norm | 0.5 |
| reward_scale | 10 | Self-Play Ratio | 0.3 |

**Important options** (the “recipe” that worked):

| Option | Meaning | lynx-3 |
|---|---|---|
| `--anchor-coef` / `--anchor` | Leash (piKL as in Meta's Cicero): KL penalty against an anchor bot | 0.3 vs `pros-r1:0` (Pluribus imitator) |
| `--anchor-min-players` / `anchor_min_bb` | Leash active only where anchor has experience | from 4 players, from 25 BB |
| `--human-share` | Fraction of human bots at tables | 0.4 |
| `--random-share` | Random-style bots | 0.05 |
| `--self-play-seats` | Seats with own previous versions | 0.3 |
| `--random-formats` | 2–10 players, 20–200 BB, blind tempo 5–20 hands, various payouts | on |
| `--table-weights` | Frequency per player count | 2:3, 3:2, 4:2, 5:2, 6:3, 7–10:1 |
| `--exploit-every` / `--exploit-iters` | Every N iterations a new exploiter opponent (PSRO/AlphaStar principle) | 100 / 30 |
| `--bench-every` / `--bench-sets` / `--bench-ref` | Testbench during training, paired against a reference (`best.json`) | 100 / human480, precise, pluribus / lynx-2@500 |
| `--gate-schemes`, `--champion` | Entrance test per section | 600 fresh tournaments vs league best |
| `--widen-from`, `--features`, `--actions`, `--lr` | Network widening or adjustment, learning rate | `--widen-from lynx-2@500` |

One iteration takes about 7 seconds with 512 tournaments plus testbenches and exploiters. 1500 iterations constitute an overnight run.

### 4.7 Additional Methods (implemented but not main path)

- **CEM style optimization** (`optimize.py`): Cross-Entropy over 10 style parameters. Result: opt-1/opt-2. Method is exhausted, see chronicle.
- **Table MCCFR** (`cfr.py`): like the Pluribus blueprint (External Sampling, Linear CFR, coarse abstraction, about 77,000 infosets). At laptop-scale computation clearly weaker than the nets (cfr-1@200: mix96 Δ rock −22.7) and highly exploitable (exploiter +69%).
- **Deep CFR** (`deepcfr.py`): Advantage network plus strategy network with reservoir buffer. Promising at iteration 10/20 (mix96 +5%, 66% Pluribus agreement without Pluribus data), crash at iteration 30 (−16%), at iteration 60 −31%. **Abandoned on 27.10.**, would be a server experiment.
- **Rollout search stage 1** (`search.py`, `search?bp=...,worlds=16`): 16–24 “worlds” per action fully played out with the net. **Harmful** (mix96 −18.9 instead of +49%): Assumes all opponents play like our net (fold a lot) and thus overrides folds with large raises. Rejected. `world_from_obs` is still used.

### 4.8 Ranges and Opponent Model

**`ranges.py`:**
- For each opponent, weights over all **1326 combinations**, shifted by their actions (Bayes-like, heuristic)
- **Preflop:**
  - Raise ≈ upper q % with OPEN_Q = 30/10/4.5/3 % (Open/3-Bet/4-Bet/5-Bet)
  - Call ≈ CALL_Q = 60/35/14/6 %
  - Short all-ins broader
  - **Heads-up own quantiles** (28.10.): OPEN_Q_HU = 85/15/6/3.5 %, CALL_Q_HU = 90/70/45/12 %
- **Postflop**, with s = strength percentile on the current board:
  - Bet/Raise ×(0.15 + 0.85·s^1.5)
  - Call ×(0.3 + 0.7·s^0.6)
  - Check ×(1 − 0.35·s^4)
- Equity via numba Monte-Carlo against the ranges. Example: QJ versus Open + 3-Bet has 41% against random hands, but 23% against the ranges.
- `opponent_ranges(obs, heads_up=...)`

**`opponents.py`:**
- OpponentTracker like a HUD (VPIP, PFR, Agg, fold to bet) with prior (28/16/45/45 %), conf = hands / (hands + 20)
- Live with fuzzy name match against OCR noise and fallback to seat number

### 4.9 Heads-up Search at Runtime (`husearch.py`, 634 lines) – “hus”

**Idea:** From the moment only two players remain in the hand, a subgame is solved per decision by **CFR+ over all 1326 combinations of both players simultaneously**, instead of just following the net. Modeled after Libratus, DeepStack, and ReBeL. The opponent is the worst case (equilibrium in the subgame), no exploitation.

**Specification:** `hus?bp=<Liga-Name>|run:<Lauf>@<N>&iters=120&iters_river=300&streets=turn,river&ranges=pre,flop`, standard streets since 30.10. `turn,river`, standard ranges since 30.10. 14:08 `pre,flop` (6.8) (The preflop solver cost about 25 points in the tournament format in the night diagnosis, 6.8; `streets=preflop,...` activates it).

**Blueprint ranges (`bpranges.py`, 30.10.):** The ranges at street start no longer come from the rule of thumb in `ranges.py` (“Button opens 85%, BB defends 70%”), but from the blueprint net itself. The hand is replayed from the engine; at each preflop decision of either player, for all 169 hand classes it is queried what probability the net would have chosen exactly that action (`forward_batch`, joint mask, `from_action` assigns the size). The product is the range, distributed over 1326 combinations; flop and turn actions still get heuristic factors, with `ranges=pre,flop` also giving flop actions over all combinations from the net. For own player this is exact (preflop plays blueprint), for the opponent the assumption “plays like our net.” Cost: about 50 ms (preflop) or 470 ms (with flop) per street, cached per hand. If the run does not match the engine (live uncertainty), the search falls back to `public_ranges` (`last["ranges"]` = “bp” or “heur”). Example 50 BB, button 2.5 BB, BB calls, flop check/check: net gives caller only 4.7% top-15 mass (he 3-bets strong hands) and opener 35%; heuristic had 20.5% vs 16.8%, so ratios nearly reversed. `ranges=heur` reproduces the old behaviour. Tests `test_bpranges.py` (5).

**Technology:**
- **Calculation core in numba** (`nogil`, `cache`), BFS-flat tree as arrays
- **Functions:**
  - `_solve`: alternating CFR+, weighted average with t^GAMMA, GAMMA = 2
  - `_best_response`: exploitability, over `solve(..., exploit=True)`
  - `_showdown` and `_fold_sums` with exact blockers
- **Turn tree** with all 44 possible rivers (div = 44)
- **Bet sizes:**

  | Street | Bets (× Pot) | Raises |
  |---|---|---|
  | River | 0.33 / 0.75 / 1.5 | 1.0 |
  | Turn | 0.66 | – |
  | River in Turn tree | 0.75 | – |
  | always | All-in | MAX_RAISES = 4 per street, sizes over 85% of the stack → All-in (ALLIN_SNAP) |

- **Important correction from 28.10.: Solve from the street's beginning with the actual path.**
  - `root_state(obs)` outputs (State, Opponent, Path). `build_tree(root, path)` inserts the **actually played sizes** as branches (SAME_SIZE 4%, `_matches`), `Tree.current` is the current decision.
  - The ranges (`public_ranges`) use only the progression **up to the start of the street**. This way, the starting distribution matches the tree.
  - Previously, from the current node, a heuristic range was resolved anew. This led to a massive number of lost all-ins: hus-2 was at −440 bb/100 and was discontinued.
- **Protection:** `applies()` requires `obs.street in iters`. This fixes a KeyError “preflop” in 6-player tournaments when only two players remained preflop.
- **Exploitability in subgame:**
  - Turn with 60 It about 3% of the pot, with 120 It about 1.5%
  - River with 300 It under 1%
- **Computation time:** approximately **2.4 s per search** (Match hus against bp: 156 searches in 383 s)

### 4.10 Heads-up Preflop Solver (`hupreflop.py`, 252 lines)

- **Motivation:** Against Slumbot, the biggest leak was preflop. The BB 3-bet about 50% and barely called. Hands ending preflop (50% of all hands) cost −18.7 bb/100.
- **Method:** CFR+ over the **169 starting hand classes**, ITERATIONS = 800, `strategy()` with lru_cache (Slumbot: almost only cache hits)
- **Actions:**
  - SB: Fold, Limp, Open 2.5 BB, All-in
  - BB against Limp: Check, Raise to 4 BB (ISO), All-in
  - Against a Raise: Fold, Call, Reraise with factor 3.0 (3-Bet) / 2.3 (4-Bet) / 2.2 (5-Bet), as long as under 45% of the stack, otherwise All-in
  - The actual sizes are inserted as additional branches
- **Postflop model** (not played out):
  - The pot is split according to realized equity
  - OOP_REALIZE = 0.80, ALPHA = 1.3 (strong hands realize more), compared to 1 at small SPR
  - All-in with exact equity from the 169×169 matrix
- **Exploitability** in the model under 0.2 BB/100
- **Results:**

  | Stack | SB folds | BB against 2.5×: Fold / Call / 3-Bet |
  |---|---|---|
  | 100 BB | 14% | 30 / 50 / 18% |
  | 200 BB | 11% | 32 / 49 / 20% |

  AA is often limped in the model (trap).
- **Integration:** in `HUSearchAgent.preflop()`, applies only at a real heads-up table (`sum(in_hand) == 2`)

---

## 5. Live Operation: Suggestions, Lynx Bar, Tournament Detection

### 5.1 LiveBot (`ai/live.py`)

- Alongside capture, a **Reconstructor runs live**:
  - Completed hands feed the opponent model.
  - The progression of the running hand is included in the Observation. Until 27.10. it was empty live; the bot saw no raises ahead.
- **“Your turn”** means: own panel highlighted **and** Call/Check buttons visible. An old bug: `hero.to_act` remained set permanently, resulting in only one suggestion per session.
- **Quiet time:** A suggestion appears only after the situation has been **quiet for 0.7 s** (`SETTLE_S` in `live.py`, since 28.10.; before 0.4 s), and is recalculated if cards, bets, board, or pot change thereafter.
- **The street** is determined by the number of board cards because the street display lags.
- **Pot** as in 3.4 (image, otherwise progression). Minimum raise min_raise_to ≥ max(bets) + BB.
- **Standard advisor:** **lynx-3-300**, greedy

### 5.2 Lynx Bar (`overlay.py`, 282 lines)

- **Window:** small Tk window above the taskbar (next to clock and battery), in its own thread with thread-safe queue
- **Behavior:**
  - topmost, borderless, `WS_EX_NOACTIVATE` + `WS_EX_TOOLWINDOW`: never takes focus, no taskbar button
  - **Visible but masked (since 3.11.2026):** The bar is a normal window, visible in all screen captures. It registers its window with the capture, and `WindowSource` fills its area with background color on every frame (8.7). Until 2.11. it hid itself via `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` from all captures (verification with mss: 0% bar color in the photo, without lock 94%).
- **Display:**
  - When it is your turn, the bar lights up in the action color and plays a sound (winsound): Fold low, Check/Call medium, Raise high, All-in double
  - Also alternatives (`alternatives()`): “Check” when check is possible, and “Min-Raise”
  - Warnings when pot is uncertain or estimated call amount
  - Status dot green/yellow/red (capture / table recognized or analysis delayed / source lost)
- **Controls:** Drag moves it (saved in `data/live/leiste.json`). Right-click: sound on/off, reset position.
- Windows 11 no longer supports taskbar deskbands, thus the floating window
- The user found the bar “really fits well as is”

### 5.3 Automatic Tournament Detection (`TournamentWatch`, evening 28.10.)

- **Elimination:**
  - After a hand, own stack is 0. The place is 1 plus the number of opponents still having chips.
  - **Confirmed** by the starting stacks of the next hand, which after stabilization contain recorded winnings. If chips are present there (OCR error "0"), elimination is discarded.
- **Win:** Only oneself has chips left. Counts as place 1, final at session end (Ctrl+C) or next game.
- **Entry:** At most one result per game (`info.game_hand`). Automatically entered in `data/ziele/pokerth.jsonl` (`quelle=auto`, hands, game, last hand). Console and bar show e.g. “Tournament over: Place 2 of 6 after 87 hands” and the balance.
- **Tournament start missed:** Then the entry is flagged because player count may be too low.
- **Tested:** Unit tests and no errors in all 6 real recordings. **A real tournament end has not yet occurred**, live test running since evening 28.10.

### 5.4 Procedure of a Live Evening

1. Open PokerTH Web, do not start a game yet.
2. Start `pc.cmd live --leiste`, **before** tournament start.
3. Start game against PokerTH bots, keep window front and uncovered.
4. Read suggestions in the bar, **click yourself**, follow as consistently as possible (then Lynx is measured, not Jakob).
5. Note conspicuous hands (wrong cards or pot, deviations).
6. After a win, terminate `live` with Ctrl+C to register the win.
7. Afterwards: Evaluate recordings with `live-replay` and `compare` (log only as cross-check).

---

## 6. Benchmarks: Methodology and All Results

### 6.1 Test Bench (`ai/bench.py`, Version bench-1)

**Fixed Test Sets** (fixed decks and fixed tables):

| Set | Contents | Format |
|---|---|---|
| `fest48` | 48 Sit&Go schemas against rock/tag/lag/station/maniac | 6 players, 3000 chips 10/20 (150 BB), ×2 every 10 hands, 50/30/20 |
| `mix96` | 96 schemas, tables from a stronger mix (including opt-1, pros-bc) | as above |
| `cash` | 300 duplicate cash hands | bb/100 |
| `pluribus` | Match vs Pluribus | networks only |
| Formats each 48 | `hu48`, `3max48`, `10max48`, `turbo48` (30 BB, blinds every 5), `deep48` (200 BB), `pokerth48` (6 players, 1000 chips = 50 BB, every 9 hands) | |
| **`mensch480`** | 480 schemas, PokerTH format, 5 opponents from human bots by proportion | Main measure Target 2 |
| `praezise` | mix960 + pokerth480 + hu480 + 10max240 | Intervals about 3× narrower (±3 instead of ±12) |
| `nash240` | Heads-up 20 BB (400 chips, 10/20, every 10 hands, winner takes all) vs NASH_BOT | Target 5 |
| `kurz240` | the same against a human bot | Target 5 |

The number in the name is freely chosen. Larger sets start with the schemas of the smaller ones.

**Key Metrics:**
- **ROI** = average net payout in buy-ins. With 6 players and 50/30/20 blinds, a maximum of +200% is possible (win = 3 buy-ins net +2).
- **Δ rock** or **Δ Ref** = paired difference on the same decks

**Further Tests:**
- **Exploiter Test** (`train exploit`): A network (start pros-1@0) learns 30–40 iterations against 5 copies of the subject. Its ROI on 48 fresh schemas is measured. The smaller the ROI, the more robust the subject.
- **Admission Test** (`gate`): 120–600 fresh schemas, paired against the defending champion, passed if lower confidence interval boundary > 0
- **Confirmation** (`confirm.py`): one-time, fresh human tables or a league gate with own seed, predetermined

### 6.2 Development of Playing Strength (Main Line)

| Date | Bot | Core Result | Status |
|---|---|---|---|
| 25.10. | rock (rule-based bot) | Reference Δ rock = 0, exploiter **+100 %** | best rule-based bot |
| 25./26.10. | opt-1 (CEM) | Gate vs tag +8.9 [1.1; 16.7], mix96 −2.4 | Overfitting |
| 26.10. | nn-1 (PPO without leash) | mix96 +19 @100, then collapse, Pluribus 63 → 13 % | Exploiting the league, not good poker |
| 26.10. | pros-1 (BC Pluribus + leash) | mix96 −20 @0 → +8 @200 → +14 @500, Pluribus 80 % | |
| 26.10. | **pros-2** (+ 512 tournaments/iteration) | **Gate vs rock +19.8 % [8.8; 30.7]**, mix96 +22.8, exploiter +3.8 % | first big jump |
| 26.10. | pros-r1@300 (+ ranges, feat-2) | mix96 +23.0, fest48 +25.0, Pluribus 82 % | later confirmed as best (precise) |
| 27.10. | pros-r3-200 (multi-format) | Gate vs pros-ppo2 +13.3 [3.0; 23.6] | in the league, not better on precision |
| 27.10. | **pros-h1@600** (feat-3, act-2, self-play seats, many HU tables) | precision vs pros-r1@300: hu +8.3*, mix960 +2.9, pokerth +1.4, 10max +8.3; confirmation 600 schemas +6.0 [1.4; 10.6] | Name **Lynx** |
| 27.10. | **lynx-2@500** (+ 40 % human bots) | vs Lynx: human480 **+17.7***, mix960 +8.1*, hu480 +8.5*; confirmations +12.1 [7.0; 17.3] and +7.4 [2.6; 12.3] | biggest jump from human bots |
| 28.10. | **lynx-3-300** (lynx-2 continued, night run) | Gate +4.5 [0.3; 8.6]; confirmation human tables **+9.2 [4.8; 13.6]**, league **+6.7 [2.3; 11.0]** | **current best and live standard** |

(* = 95% confidence interval above 0)

### 6.3 Large Test Sets (excerpt from `data/bench/report.md`, ROI, Δ rock paired in parentheses)

| Bot | 10max240 | hu480 | human480 | mix960 | pokerth480 |
|---|---|---|---|---|---|
| rock | +43.9 % | −16.9 % | +43.8 % | +24.6 % | +21.1 % |
| pros-r1@300 | +56.2 (+12.2) | +35.6 (+52.5) | +73.0 (+29.3) | +41.3 (+16.8) | +32.6 (+11.5) |
| pros-h1@600 | +64.5 (+20.6) | +44.0 (+60.8) | +75.9 (+32.1) | +44.3 (+19.7) | +33.9 (+12.8) |
| pros-h1@200 | +59.3 (+15.4) | +48.3 (+65.2) | +76.8 (+33.0) | +45.4 (+20.8) | +31.4 (+10.3) |
| lynx-2@500 | +72.9 (+29.0) | +52.5 (+69.4) | +93.6 (+49.9) | +52.4 (+27.8) | +37.1 (+16.0) |
| lynx-2@300 | +73.3 (+29.4) | +52.9 (+69.8) | +94.8 (+51.0) | +59.2 (+34.7) | +42.8 (+21.6) |
| **lynx-3@300** | +73.6 (+29.6) | +49.6 (+66.5) | **+96.8 (+53.0)** | +50.6 (+26.0) | +35.2 (+14.1) |
| lynx-3@500 | +72.0 (+28.0) | +51.0 (+67.9) | +103.2 (+59.5) | +53.2 (+28.7) | +37.9 (+16.8) |
| lynx-3@1000 | +74.9 (+30.9) | +49.8 (+66.7) | +103.2 (+59.4) | +51.8 (+27.2) | +40.1 (+18.9) |
| lynx-3@1100 | +61.5 (+17.6) | +50.2 (+67.1) | **+108.5 (+64.7)** | +47.0 (+22.4) | +39.4 (+18.3) |
| lynx-3@1500 | +69.0 (+25.0) | +50.8 (+67.7) | +100.4 (+56.6) | +51.5 (+27.0) | +37.1 (+16.0) |

**Classification:**
- Later lynx-3 versions score sometimes higher on human480, e.g. @1100 with +108.5%, but **did not pass their gate against lynx-3-300** (@600 −3.7, @900 +0.1, @1200 −2.5, @1500 +2.8).
- According to the methodological rule, lynx-3-300 remains the best. A peak on the often-viewed human480 alone is not enough.
- best.json (paired against lynx-2@500) was at @1000 with mean +2.22, with human480 +9.6 [4.5; 14.6].

### 6.4 Format Test Stand from 27.10. morning (Δ rock, each 48 schemas, CI ±15–20)

| Bot | hu48 | 3max48 | 10max48 | turbo48 | deep48 | pokerth48 | Ø |
|---|---|---|---|---|---|---|---|
| pros-r2@350 | +50.0 | +17.1 | +30.7 | +4.1 | +24.2 | +9.4 | +22.6 |
| pros-r3@200 | +50.0 | +13.6 | +19.3 | −1.2 | +26.9 | +19.4 | +21.3 |
| pros-r1@300 | +41.7 | +13.1 | +13.4 | +12.1 | +23.5 | +20.4 | +20.7 |
| pros-2@300 | +54.2 | +29.2 | +12.4 | −7.9 | +29.6 | +3.8 | +20.2 |

Conclusion then: all roughly equal within noise. From this, the larger, more precise sets were developed.

### 6.5 Exploitability (Exploiter ROI, smaller = more robust)

| Bot | Exploiter ROI |
|---|---|
| rock | **+100.2 %** [85.9; 114.5] |
| cfr-1 (table) | +68.8 % [59.4; 78.1] |
| pros-2@300 | +3.8 % [−7.1; 14.6] |
| pros-h1@600 | approx. +10 % |
| lynx-2@500 | approx. +1 % (lynx-2@300 on the other hand +28 %, thus exploitable) |
| **lynx-3-300** | **+2.3 %** [−11.5; 16.1] |

### 6.6 Endgame heads-up 20 BB (Target 5)

| Bot | nash240 (vs Push/Fold Nash) | kurz240 (vs Human Bots) |
|---|---|---|
| lynx-3-300 | **+17.9 %** [10.4; 25.5] | **+83.3 %** [78.3; 88.3] |

Beating a Nash push/fold strategy is possible because Nash push/fold is not optimal against a player who also makes smaller raises and postflop plays.

### 6.7 Slumbot (Heads-up 200 BB Cash, Target 3)

**Methodology:**
- **Format:** API from slumbot.com, blinds 50/100, 20,000 chips per hand. Each hand is immediately written to `data/bench/slumbot/<name>.jsonl` (resumable), with 4–6 parallel sessions.
- **raw:** actual winnings in bb/100
- **All-in EV:** In any all-in before the river, equity is counted instead of the dealt cards.
- **Baseline:** Slumbot reports per hand what **Slumbot itself would have won at our seat with the same cards**. This is a measure of card luck with an expected value of 0.
  - The old column "vs Baseline" (winnings − Baseline) is **biased and hardly more accurate**: the correlation is only about 0.4–0.6 because Slumbot plays the cards differently.
  - On 27.10., with r = 0.15, it was even called "useless". This referred to the raw winnings.
- **New main measure since 28.10.: “adjusted”** = All-in EV − β·Baseline with estimated optimal β (control variable, `slumbot.adjusted`). This is unbiased and has the smallest error bars. It is also displayed in the target table.

**All runs** (bb/100, 95% interval):

| Bot | Hands | raw | All-in EV | Card Luck | **adjusted** | β |
|---|---|---|---|---|---|---|
| pros-r1@300 | 15,767 | −21.5 ±17 | −22.7 [−39; −6] | −42.8 | **−13.7 [−29; +2]** | 0.21 |
| pros-h1@200 | 8,935 | −6.0 ±28 | −8.0 [−36; +20] | +4.7 | **−9.8 [−34; +15]** | 0.38 |
| pros-h1@600 (Lynx 1) | 7,666 | −33.2 ±24 | −38.6 [−61; −16] | −16.7 | **−35.4 [−57; −14]** | 0.20 |
| lynx-2@500 | 20,000 | −27.2 ±16 | −26.3 [−42; −11] | −31.0 | **−18.6 [−33; −4]** | 0.25 |
| **lynx-3@300** | 10,000 | −21.3 ±24 | −23.0 [−45; −1] | −23.4 | **−17.2 [−38; +4]** | 0.25 |
| hus-1 (old search, from Turn) | 3,000 | −16.5 ±75 | −12.6 [−83; +58] | −25.3 | +2.5 [−49; +54] | 0.60 |
| hus-2 (search, error) | 458 | −396 | −382 [−661; −103] | −335 | −81.6 [−211; +48] | 0.89 |
| **hus-3** (search from street start + preflop solver) | 8,167 | −8.7 ±36 | −8.2 [−43; +27] | **+29.4** | **−23.7 [−52; +5]** | 0.53 |
| **lynx-4@300** (29.10., 2 sessions) | 10,000 | −10.3 ±42 | −7.2 [−46; +31] | −13 | **+0.2 [−29; +30]** | |
| **hus-4** (30.10., Search Turn+River without preflop solver, blueprint pre+flop ranges) | 3,000 | −41.0 ±91 | −48.7 [−125; +28] | −17 | **−39.0 [−95; +17]** | |
| **hus-5** (30./31.10., cash configuration: preflop solver + equilibrium ranges `eq,flop` + network leaves) | 10,000 | −15.3 ±37 | −7.4 [−41; +26] | +1 | **−8.0 [−35; +19]** | |

**Lessons learned:**
0. **lynx-4-300 is on par with Slumbot** (adjusted +0.2 after 10,000 hands, raw −10 with card luck −13). This is about +17 bb/100 better than lynx-3@300 and meets level 1 of goal 3 (> −15); level 2 (> 0 assured) requires many more hands or a clearly stronger version. The trend fluctuated strongly (+38 after 1,800, +42 after 4,400, +16 after 5,700, +9 after 6,600, +19 after 7,200 hands), interim results under 5,000 hands remain worthless. Since the competition analysis, Slumbot is only a stage-1 baseline, the main measure is GTO Wizard AIVAT.
1. **Against Slumbot, Lynx honestly loses about 15–20 bb/100.** The first stage of goal 3 (> −15) is narrowly missed.
2. **The search (hus-3) is not demonstrably better than the network alone against Slumbot.** Its apparent gain (temporarily +54 bb/100 after 1,833 hands, final all-in EV −8) was **card luck**: Slumbot itself would have won +29 bb/100 with these cards.
3. **Preflop is repaired by the preflop solver:** preflop portion +0.7 instead of −18.7 bb/100, SB fold 12%, BB fold against open 10%, 3-bet 26%. The network thus loses postflop.
4. Raw interim results under about 5,000 hands are worthless; the interval is ±60–130. Only the adjusted measure after many thousands of hands is reliable.
5. pros-h1@200 has the best Slumbot estimate (−9.8) but is weaker on PokerTH-like sets. A HU specialist is not automatically the best PokerTH bot.
6. **Leak analysis lynx-2** (`scratchpad/slumbot_leaks.py`, 27./28.10.):
   - Hands that end preflop (50%) cost −18.7 bb/100
   - The BB 3-bet against opens 53%
   - Earlier (pros-r1): Button folds immediately 40% (strong would be 10–20%), BB folds 51% against opens (strong would be 25–35%)

### 6.8 Search versus network in PokerTH formats

- **Heads-up versus blueprint locally** (HU 200 BB, 300 duplicate hands): **+41.8 bb/100 [−36; +119]**, not significant
- **PokerTH comparison** `hus?bp=lynx-3-300&iters=60&iters_river=150` on hu480 and mensch480 versus the net alone (reference net hu480 +49.6% [44.2; 54.9]): **started twice, never completed.** It was aborted by the memory guard or at the start of play on the evening of October 28th; no result available.
- **October 29 (17:20–21:12, isolated, 4 processes): `hus?bp=lynx-4-300&iters=60&iters_river=150` (hus-1, Turn+River in the tree, playing out) on hu480, paired against lynx-4@300:** Search +17.1% [11.1; 23.1], net alone +46.5% → Difference −29.4 [−36.8; −21.9].** The search in this format is **significantly worse** than its own blueprint net. Together with Slumbot (hus-3 −23.7 against lynx-3 −17.2, 6.7), this means: the search in its current form helps nowhere. It will **not** become live standard. The cause is unknown (too few iterations, opponent range from own blueprint, playing out to leaf, action mapping); it must be found **before** computing time is spent on the value net (milestone 3 builds on the search). Next diagnosis: Search directly against its blueprint (duplicate HU), convergence with 5× iterations, sampling individual decisions against the net.
- **Night diagnosis 29/30.10 (`bench_diag_nacht.py` instead of hus-2), Phase A (21:16–21:59):** `hus?bp=lynx-4-300&streets=preflop`, i.e. **only the preflop solver** (hupreflop), postflop the net, on hu480 paired: **+21.2% [15.4; 27.1] against net +46.5 → Difference −25.2 [−32.3; −18.1]**; against hus-1 +4.2 [−1.9; +10.3]. **The leak is preflop:** the heads-up equilibrium model (built for 200 BB cash, good against Slumbot: preflop share +0.7 instead of −18.7) costs about 25 points in 50 BB tournament with blinds increasing every 10 hands against the pool bots; the turn/river search itself contributes only about −4 (not significant). Consequences: (1) `streets=preflop` is wrong for the tournament format, the preflop solver belongs only in deep cash spots (or must learn stack depth/ICM/blind increases); (2) testbeds against pool bots reward exploitation, an equilibrium player always loses to nets trained for that, therefore GTO Wizard remains the measure of "strong against humans"; (3) phases B and C show whether the postflop search without preflop solver at least keeps pace and whether it beats its blueprint in the home format 200 BB.
- **Phase B (21:59–23:15):** `hus?bp=lynx-4-300&streets=turn,river&iters=60&iters_river=150` (search **without** preflop solver) on hu480: **+37.9% [32.1; 43.7] against net +46.5 → Difference −8.5 [−14.7; −2.3]**; against hus-1 +20.8 [+13.2; +28.5]. Breakdown of the −29.4 from hus-1: about 25 points preflop solver, about 8 points postflop search. The postflop search is still worse than the trained net in the tournament format against pool bots, but only barely significant; the preflop solver is the real problem.
- **Phase C (23:15–00:14):** hus-1 against lynx-4@300 directly, HU 200 BB cash duplicate, 40 tasks × 25 leaves = 2000 hands: **−0.6 bb/100 [−62.2; +61.0]**, draw. The measurement is far too coarse for this format: the standard deviation per 50-hand task is about 200 bb/100 (many all-ins at 200 BB, VPIP ~68%), for an interval of ±10 about 75,000 hands would be needed. Remarkable is the trend: tasks 0–23 average +103, tasks 24–39 average −156 (14 of 16 negative). Seeds are deterministic (1000+k), husearch has no time budget, so the seed randomness is expected; to be sure tasks 2 (+455.3) and 30 (−283.3) were recalculated individually (`data/bench/diag-nacht-repro.txt`).
- **Overall interpretation of night diagnosis:** (1) **Main leak is the preflop solver** (about 25 of 29 points): its heads-up equilibrium is computed for 200 BB cash and does not fit the 50 BB tournament with blinds increasing every 10 hands; also it plays non-exploitatively against the pool bots. (2) **The postflop search** still costs about 8 points on hu480 against the trained net, equilibrium versus exploitation. (3) **Even in the home format 200 BB** no advantage of search over its blueprint can be demonstrated; the earlier +41.8 [−36; +119] and this −0.6 [−62; +61] both say nothing. Thus the search as teacher or oracle for the value net is **not proven**. Next steps before Hetzner tranche: (a) deactivate hupreflop in `hus` by default (`streets=turn,river`), preflop solver only in deep cash spots; (b) derive ranges of subgame solution from the blueprint instead of the heuristic (`ranges.py` public_ranges/opponent_ranges HU) and test on hu480 against net, target difference ≥ 0; (c) a low-variance home format evaluation (all-in EV adjustment as in Slumbot protocol or fixed third opponent) instead of 2000 raw hands; (d) the 1000-test of river data (~0.06 €) is independent and can run after Jakob’s Go, the 500k tranche only after (b) proves the search better.
- **Recheck Phase C (00:52–00:58):** Individual recalculation of tasks 2 and 30 resulted in exactly +455.3 and −283.3, measurement is deterministic, sign change between halves was seed randomness.
- **October 30, 09:04, rebuild and measurements D/E (`bench_hus1bp.py`, `data/bench/hus1bp.txt`):** Standard of search now `streets=turn,river` without preflop solver and `ranges=pre` (blueprint ranges, 4.9). Measured on hu480 paired: D `hus1bp-lynx-4-300` (ranges=pre) and E `hus1bpf-lynx-4-300` (ranges=pre,flop), each against net +46.5, against heuristic search hus1np +37.9 (Phase B) and against hus-1 +17.1. Success criterion: difference to net ≥ 0 (Phase B was −8.5). The first run of D died after 85 minutes with the parent process (cause unknown, no traceback); since then `run_set` saves every finished block (`bench/partial-*.json`, `resume=True`) and reports intermediate results.
- **Measurement D finished (10:59–12:15):** `hus1bp-lynx-4-300` (streets=turn,river, ranges=pre) on hu480: **+41.2% [35.5; 47.0]**. Against net +46.5 → **−5.2 [−11.6; +1.1]** (no longer significant); against heuristic search hus1np +37.9 → **+3.3 [−0.3; +7.0]** (barely not significant); against hus-1 +17.1 → +24.2 [+16.6; +31.7]. **Interpretation:** Blueprint ranges bring about 3 points, the gap to net shrunk from −29 (hus-1) via −8.5 (without preflop solver) to −5.2. The search on hu480 is now statistically on par with the trained net, but not yet proven better. What remains is presumably the fundamental conflict equilibrium versus exploitation: the net exploits pool bots, the search plays unexploitable in the subgame. Measurement E (also evaluating flop actions from the net) is running.
- **Measurement E finished (12:15–14:05):** `hus1bpf-lynx-4-300` (ranges=pre,flop) on hu480: **+44.0% [38.3; 49.7]**. Against net +46.5 → **−2.5 [−8.7; +3.7]** (even), against heuristic search hus1np +37.9 → **+6.0 [+1.8; +10.3]**, first time significantly better; against hus-1 +26.9 [+19.1; +34.7]; against D (preflop only from net) +2.7 [−1.4; +6.8]. **The sequence search vs. net is now −29.4 → −8.5 → −5.2 → −2.5** (preflop solver out, blueprint preflop ranges, blueprint preflop+flop ranges). So the ranges were indeed the second lever after the preflop solver. `ranges=pre,flop` has been standard of the search since 14:08 (~0.5 s additional per street). On hu480 the limit is reached: the exploitative net beats the pool bots, an equilibrium player can at best tie there. The next measurement for the search belongs to Slumbot and GTO Wizard where equilibrium is rewarded.
- **Slumbot hus-4 (15:02–17:20, 3000 hands, 4 sessions):** exactly this configuration (streets=turn,river, ranges=pre,flop) versus Slumbot: **raw −41.0 [−132; +50], all-in EV −48.7, adjusted −39.0 [−95; +17]** (6.7). Not significantly worse than the net (+0.2), but in the sequence hus-1 −12.6 / hus-3 −23.7 / hus-4 −39.0, the search against Slumbot lags behind the net. Breakdown raw by contribution in bb/100: **River −99 (net −65, hus-3 −32)**, position BB −62 (net −4), showdown hands −4.8 bb per hand (net −2.7), pots over 50 BB −67 (net −46); preflop, flop and turn about like the net. **Interpretation:** The leak is the search’s river play, i.e., calls and bluffs at showdown, which is a range problem: blueprint ranges assume “the opponent plays like our net,” Slumbot does not, and without preflop solver the preflop ranges of a tournament net for 200 BB come in. hus-3 with preflop solver was the best search against Slumbot (−8.7 raw over 8167 hands). That is the mirror image of hu480 results: there the net fits as opponent model, with Slumbot it does not. **Next step (not yet built): format-dependent configuration.** Deep cash: preflop solver on, and preflop ranges drawn directly from its CFR solution (exact equilibrium ranges per preflop line instead of heuristic or blueprint). Tournament: as now. Then GTO Wizard as measure against human-like equilibrium.
- **Measurement V finished (18:08–18:52, `bench_hus1v.py`):** `hus1v-lynx-4-300` = configuration E, but river subtrees in turn tree replaced by value net `kaggle-t2-big` (2048×3, trained on 752,000 situations, of which 252,000 from real search leaves). hu480: **+43.1% [37.3; 48.9]**; against E (exact river subtrees) +44.0 → **−0.8 [−3.9; +2.3]**, paired and thus practically equally strong; against net −3.3 [−9.4; +2.8]; against heuristic search +5.2 [+0.8; +9.6]. Runtime of measurement 44 vs. 110 minutes, per turn decision 1.1 vs. 4.8 s. **Interpretation:** The first step of the DeepStack ladder works. The river net replaces the exact river solution at leaves without measurable loss and speeds up the turn search 4.4 times. This makes the flop search (hus-2 tree, previously 17 to 62 s per decision) affordable, and the way to turn data and turn net is open. The net is not yet standard (spec parameter `vnet=kaggle-t2-big/vnet-river`, requires checkpoint locally).
- **Evening 30.10, three steps in parallel (Jakob: “keep going”):** (1) **Flop search with net leaves** measured locally: 1.6 s per flop decision (hus-2 tree k 6/6, 1323 nodes) instead of 17 to 62 s; with k 4/4 0.9 s. Measurement F (`bench_hus2v.py`, `hus2v-lynx-4-300`: streets=flop,turn,river, iters_flop 40, vnet) started on hu480 against V, E and net at 20:11. (2) **Tranche 3** (additional 252,000 leaf situations, shards 1010–1019) started on cpx62 at 20:12, approx. €0.50. (3) **Equilibrium ranges for deep cash** constructed: `hupreflop.path_ranges` provides the ranges of both players after actual preflop history as product of average strategy (also for concluded histories), `equilibrium_ranges(obs)` grids the stack like `decide`; in `bpranges` the mode `eq` (preflop from equilibrium, allocation via `sb_seat`, requires no net), specification `ranges=eq` or `eq,flop`. Test `test_gleichgewichts_ranges_preflop_fuer_cash`. Then **Slumbot hus-5** started at 20:15: `streets=preflop,turn,river&ranges=eq,flop&vnet=kaggle-t2-big/vnet-river`, 3000 hands, 2 sessions, the cash configuration (preflop solver on, equilibrium ranges, net leaves). Expectation: better than hus-4 (−39) and hus-3 (−23.7); target ≥ net (+0.2).
- **Measurement F finished (20:11–22:39):** `hus2v-lynx-4-300` (search from flop, k 6/6, 40 flop iterations, net leaves) on hu480: **+37.3% [31.5; 43.1]**; against net −9.2 [−15.7; −2.7], against V (turn search with net) **−5.8 [−11.4; −0.3]**, against E −6.7 [−12.6; −0.8]. The flop search in this form is thus **significantly worse** than the turn search, although at 1.6 s per decision finally affordable. Likely cause: coarse abstraction (6 of 47 turn and 6 of 46 river cards, 40 iterations, 1323 nodes) and net error which sums over two streets. Consequence: flop remains with blueprint, `streets=turn,river` remains standard. A second attempt worthwhile only with more cards (k 12/12) and a turn net replacing the turn subtrees.
- **HandHQ extraction (H11, Jakob 20:50 “start now”), finished 22:57 after 2 h 21 min with two low-priority processes:** new module `humandata.py` (play hand with engine like `phh.replay`, dollar ×100, heads-up button = SB, only shown players produce rows: 49 features feat-2, action mask and action in 8-grid, metadata street/position/player count/pot/bet/stack/type/amount/hand class/player), CLI `data humandata`, tests `test_humandata.py` (3). **Result: 5.97 million hands, 1.47 million with shown cards, 1.21 million replayed, 7.35 million decisions** in 120 shards (`data/humans/actions/`, 245 MB); skipped 239,000 straddle hands, 15,700 order cases, 1,000 stack/blind cases. Distribution in sample: about 70% check/call per street, preflop raises mostly pot size (17%), postflop mostly half pot, third and min-raise; tables with 3 to 9 players, 6 and 8–9 most frequent, no heads-up. **No fold at all in data** (folders don’t show): model learns P(action | hand, continued play); fold rates must come from unbiased frequencies, flop and turn ranges underestimate given-up bluffs, river ranges almost unbiased. Next step: train human policy net on this (Kaggle, blueprint interface), validation by log-likelihood of shown cards on hold-out, then `ranges=human` in search.
- **Slumbot hus-5 finished (20:15–23:45, 3000 hands, 2 sessions):** cash configuration `streets=preflop,turn,river&ranges=eq,flop&vnet=kaggle-t2-big/vnet-river`: **raw −5.5 [−72; +61], all-in EV −10.4, adjusted +0.0 [−50; +50]** (6.7). Thus the search against Slumbot is for the first time on par with the net (+0.2 over 10,000 hands) instead of behind (hus-3 −23.7, hus-4 −39.0). The equilibrium ranges from the preflop solver fixed the river loss of hus-4, the net as leaf cost nothing. Interim at 1000 hands was +93 [+5; +181], at the end variance; the interval ±50 requires about 10,000 hands for a statement “better than the net.” Interpretation of both formats: hu480 wants the net as opponent model (pool bots play like our net), Slumbot wants equilibrium; the format dependent configuration is thus confirmed and should be chosen automatically in specification (tournament with blind increases → `turn,river` + `pre,flop`; deep cash → `preflop,turn,river` + `eq,flop`).
- **Value net on 1 million situations (Kaggle, 23:23–00:12, 2048×3, 60 epochs, 47 min T4):** 500,000 broad + 504,000 leaf situations (tranches 1–3). Hold-out 0.0192; synthetic distribution EV error 0.0035 (unchanged); **leaf test set EV error 0.0081 pot, 95% quantile 0.022, max 0.042** (previously 0.035 / 0.19 / 0.23). **Thus the acceptance goal for leaves (EV error under 0.02) is reached.** The sequence is 0.121 (broad only) → 0.035 (252k leaf) → 0.0081 (504k leaf): the second leaf tranche again reduced the error by factor 4, data from real search distribution is the lever. Checkpoint `data/valuenet/kaggle-t3-big/vnet-river.pt`, copy as standard name `data/valuenet/vnet-river-1.pt` (`vnet=vnet-river-1`). Total cost of three tranches approx. €1.70.
- **Human model human-1 (H11 step 2, Kaggle 00:10, 49 s):** policy net 49 → 512 → 512 → 8 on 7.2 M HandHQ decisions, hold-out every 50th hand: NLL 0.720 versus 0.95–1.06 frequency baseline, hit rate 78% preflop, 73–75% postflop. For comparison lynx-4@300 predicts the same human decisions with NLL 2.26 and 35.6% accuracy before (preflop 9%): Lynx plays completely unlike normal players. As bot (`nn?run=human-1@1`) it never folds (no folds in data), thus a calling station with raise instinct, and beats lynx-4 heads-up in a quick test (−64 / −76 bb/100 each over 300 hands, intervals huge): Lynx bluffs too much versus stations (V1 finding). **Measurement H (00:12–05:22):** search `auto=1&opp=human-1@1&vnet` (opponent actions evaluated with human model): hu480 +42.5 [36.8; 48.2], same as V and E; **mensch480 +95.1 [89.5; 100.7] versus net +115.1 → −20.0 [−25.5; −14.5], significantly worse.** Two reasons: no fold model so opponent ranges too broad, and mensch480 consists of our own style bots, trained against the net, not from HandHQ humans. Consequence: first a fold model (second extraction of all decisions without cards → P(fold | state), cards of folders as Bayesian residual), then measure `ranges=human` against the human bot itself and against GTO Wizard. `opp=human-1` is not standard. New additions: `auto=1` (format choice per hand) and `opp=<Lauf>@<Ckpt>` as specification parameter for search, `teacher.py` (search as teacher: collect and retrain, CLI `train teacher-collect` / `teacher-fit`, server script `cloud/run-teacher.sh`).
- **Slumbot hus-5 final (10,000 hands, 20:15–05:55, 4 sessions from 00:01):** raw −15.3 [−52; +22], all-in EV −7.4 [−41; +26], **adjusted −8.0 [−35; +19]** (6.7). After 3000 hands it was +0.0, after 1000 +93; the final is slightly below zero, the interval includes zero. Versus the net (+0.2 [−29; +30] over 10,000) the difference is not significant. **Answer to “do we beat Slumbot with the search?”: no, not proven; the search is at Slumbot about the net’s level, perhaps slightly below.** Progress versus hus-3 (−23.7) and hus-4 (−39.0) remains, but a plus against Slumbot requires more than equilibrium ranges: more iterations (now affordable), broader bet sizes, and above all the preflop solver which so far uses a postflop model instead of true postflop values.

- **Fold model human-fold-1 and first measurement against the human bot (31.10. 06:30–08:01, `bench_humanopp.py`, `data/bench/humanopp.txt`):** The human model human-1 has no folds (only shown hands in HandHQ). Therefore, a second, map-free extraction of all 55.5 million decisions (`data humanpublic`, `public-*.npz`, with folds) and from this `ai/humanfold.py`: f(s) = P(Fold | public state, 20 features) and g(c | s) = distribution of the shown 169 classes; continuation factor per combination = clip(g·(1−f)/P(c|s), 0, 1) (Bayes remainder), multiplied in the search as `oppfold=human-fold-1` onto the opponent's range before each non-fold opponent action. Plausible: BB vs UTG-raise 6-max folds 75%, stays in with AA 98%, 93o 2%. **Measurement of the search against `nn?run=human-1@1` HU 40/100 BB duplicate, each 480 hands:** 40 BB: Network −4, A Standard ranges −7, B `opp=human-1@1` −95, C B+`oppfold` **−127 [−191; −63]**; 100 BB: Network +142, A +392, B +271, C +385 [+203; +566]. Huge variance (blocks ±200 bb/100) because the opponent never folds: every hand goes big to showdown. **Interpretation:** Against a calling station who never folds, the fold model is wrong (it assumes 75% folds, opponent always calls) and unjustly narrows the opponent’s range; at 40 BB this costs significance. Thus, the measurement does not test the model, but a distorted opponent. Consequence: **human bot built with fold behavior**, `nn?run=human-1@1&fold=human-fold-1` (NNAgent.fold_model: with an open bet it folds its hand with 1 − continuation factor, otherwise network action without fold; AA 0.2%, KQs 1.3%, 93o 96.5%, 72o 97.1% fold against 3-BB raise). **Network lynx-4@300 against this human bot over 10,000 hands each: 40 BB +13.5 [−5; +32], 100 BB −21.1 [−43; +0.4]** (without fold: −10.8 and −13.3 with a wider interval). The blueprint network does NOT beat the replication of a 25NL normal player heads-up; at 100 BB it tends to lose. This is the testbed closest to Jakob’s goal (winning against humans); second measurement series of the search against this opponent started (`bench_humanopp2.py`, 6 blocks × 120 hands per cell, 5 workers, 08:08). Tests: `test_humanfold.py` (3), `test_humandata.py` (4).

- **Measurement 2 of the search against the human bot WITH folds (31.10. 08:08–08:54, `bench_humanopp2.py`, `data/bench/humanopp2.txt`, each 720 hands, 6 blocks):** 40 BB: Network +76 [−32; +183], A Standard +53, B `opp=human-1@1` **+70 [+9; +130]**, C B+`oppfold` +44; 100 BB: Network +59, A +26, B +38, C +27, all intervals ±70 to ±120. **No variant differs demonstrably;** the search is not better against the human bot than the network, B (opponent model without fold factor) is the most stable search variant (all six 40-BB blocks positive), the fold factor brings no measurable effect. With folds the search runs twice as fast (hands end earlier). Approximately 10,000 hands per cell are needed for ±25 bb/100, locally ~11 h, on Hetzner ~2 h; intended as server run after teacher collection (`bench_humanopp_srv.py`).
- **Teacher collection started on Hetzner (lehrer-1, cpx62, 09:00 local time, Jakob: “do everything”):** `cloud/run-teacher.sh 16 120`: 16 processes, each 4 opponents (lynx-4@300, human bot with folds, mensch-2, mensch-4) × 4 stacks (25/50/100/200 BB) × 240 hand duplicate = 61,440 hands, search `auto=1&iters=60&iters_river=150&threads=1&vnet=vnet-river-1`. Data upload via `cloud/upload-teacher-data.sh <IP>` (value network, lynx-4@300, human-1, fold model, human bots, league file), `teacher.resolve_opponent` resolves `mensch-N` via `mensch-25nl.json`. First start had load 27–50 on 16 cores (Torch threads per process), restarted 09:00 with `OMP_NUM_THREADS=1`. Expected ~3 h ≈ 0.75 €, then `teacher-fit lynx-4@300 → lynx-5t` and Gate.

- **Stage 2 prepared: Turn value network data (31.10. 09:10–09:40):** `valuedata` knows the mode **`turn-leaf`**: flop state with synthetic ranges, flop tree with 8 drawn turn and 4 river cards solved exactly (40 iterations), ranges at the turn starts (`Tree.turn_roots`, new in `build_tree`) read out under the average strategy, up to 12 of these per flop solved with the **river value network as leaf** (DeepStack recipe: the turn network learns from solutions whose leaves are provided by the river network). Shared helper function `_roots_rows` for river-leaf and turn-leaf; `--vnet` at the CLI; `solve_sample` also uses a network for turn/flop. Test: 2 flop seeds → 20 turn lines, 1.35 s per turn solution (100 iterations) locally; label check against exact turn solutions (150 iter., all rivers exact): EV error of labels on average 0.014 pot, max 0.054 (5 lines). The value network feature already encodes street and board length; a joint network for river+turn is possible. Search: new option **`leaf=4`** (flop subtrees end at the turn starts, all 47 turn cards, no drawing) for the use of the turn network. Tests: `test_valuedata.py` (5), `test_husearch.py` (+1 leaf). Full test suite 220 green (`data/tests-31-10.txt`).
- **Server chain on lehrer-1 (`cloud/run-after-teacher.sh`, started 09:12):** waiting for teacher collection, then (1) benchmark search vs human bot with folds with 16 processes (`cloud/bench_humanopp_srv.py`, 64 blocks = 7680 hands per cell, ~1.5 h), then (2) first turn tranche `run-vdata.sh turn-leaf 0 10 2000` (20,000 flop seeds → ~240,000 turn lines, estimated 4–5 h). Total lehrer-1 ≈ 8–9 h ≈ 2.1 €. Afterwards: pull, Kaggle training vnet-2 (river+turn mixed), search with `leaf=4` measured at flop.

- **Teacher dataset complete, lynx-5t trained (31 Oct, 10:20–10:45):** teacher-1 took 1 hr 22 min (€0.35) for 16 × 16 matches: **41,730 teacher lines** (only Turn/River, since the search only decides there; hardly any lines against style humans because their hands end early). `train teacher-fit --kl 0.5` → **`data/rl/lynx-5t/ckpt_000001.pt`**: Match of top action with search 29% → 64%, cross-entropy 2.61 → 0.98, KL to anchor 0.49 (hold-out 4173 lines). Variant `--kl 2.0` (lynx-5t-k2): 40%.
- **Discovery at the gate: sampling is massively costly in heads-up cash.** Control `nn?run=lynx-4@300&greedy=1` versus sampled lynx-4@300, 100 BB, 10,000 hands duplicate: **+97.7 bb/100 [+58; +137]**. The network mixes (entropy 0.79 nats per decision, search 0.48), and the scattered side actions lose against every opponent. Sampled lynx-5t loses against lynx-4 (−14/−55/−77 at 40/100/200 BB, entropy 1.06, teacher-fit broadens the distribution), greedy beats sampled lynx-4 (+16/+33/+39), greedy versus greedy is equal (−2.8 [−22; +17]). **Against the human bot with folds (10,000 hands per cell): greedy lynx-5t +64.0 [+50; +78] at 40 BB and +65.5 [+46; +85] at 100 BB, greedy lynx-4 +3.3 and −21.9 respectively.** The teacher-fit thus yields 60–85 bb/100 against the human replica, nothing against lynx-4 itself. Open questions: Greedy is deterministic and thus exploitable by humans (later temperature instead of full greedy), and whether greedy also wins in tournament format. Running: testbed hu480/mensch480/mix960 for lynx-5t-g, lynx-4-300-g, lynx-5t-s (`bench_lynx5t_sets.cmd`, `data/bench/lynx5t-sets.txt`) and Slumbot 3000 hands for greedy lynx-5t (`data/bench/slumbot-lynx-5t-g.txt`).

- **Testbed lynx-5t complete (31 Oct, 10:59, `data/bench/lynx5t-sets.txt`, tournament format hu480/mensch480/mix960):** lynx-4@300 sampled (reference) 46.5 / 115.1 / 59.3%; **lynx-4@300 greedy 55.8 / 128.2 / 79.8%** (new best on all three sets, mix960 +20 points); lynx-5t greedy 35.6 / 103.2 / 61.3%; lynx-5t sampled 28.5 / 81.7 / 35.5%. Interpretation: Greedy helps everywhere (scattered side actions cost even in tournament format), but the teacher-fit lynx-5t is worse than lynx-4 versus the bot pool—it has learned what the search does against human bots, which is not better against pool bots. Thus lynx-5t is a human exploiter (HU cash vs human+fold +64/+65 instead of +3/−22), not a general improvement.
- **Slumbot lynx-5t greedy, 3000 hands (`data/bench/slumbot-lynx-5t-g.txt`):** net +35.3 bb/100 [−6; +77] (raw +35.3, all-in EV +34.6, card luck −3). Not significant, but the best Slumbot figure so far (lynx-4@300 sampled +0.2 at 10,000 hands, lynx-3 −17).
- **Server benchmark Search vs human bot with folds complete (teacher-1, 16 processes, 64 blocks = 7680 hands per cell, `data/bench/humanopp_srv.txt`):**
40 BB: A-standard +19.7 [+1.8; +37.5], B-human +17.8 [−1.3; +36.8], **C-human+fold +30.4 [+13.3; +47.5]**, net lynx-4@300 sampled +2.9 [−20; +26];
100 BB: A +23.8 [−2.9; +50.4], **B +33.6 [+5.8; +61.4]**, C +29.3 [+3.7; +54.9], net **−40.3 [−68; −12]**.
The search beats the sampled net at 100 BB by about 65 bb/100 and is positive in all variants, with fold factor best at 40 BB—but all search variants (+20…+34) are clearly below greedy lynx-5t (+64/+65 at 10,000 hands). The teacher-student thus beats its teacher against this opponent; presumably because the search preflop (net sampled) and in its mixed strategies still mixes, unlike the greedy student.
- **Turn tranche running (teacher-1, from 11:28 local time, `run-vdata.sh turn-leaf 0 10 2000`, 16 processes × 1 thread, fully loaded):** 2.6 s per flop seed → ~87 min per shard (2000 seeds ≈ 20,000 turn lines), 10 shards ≈ 14.5 h ≈ €3.6 instead of estimated 4–5 h. Each finished shard is individually usable and retrieved.

- **Temperature instead of full greedy (31 Oct, 12:14–13:05, `nn?run=…&temp=T`, `data/bench/temp-hu.txt`, HU cash per 10,000 hands):** p ∝ p^(1/T), T=1 sampling, T=0 greedy. **lynx-4@300** vs human+fold shows almost no benefit from temperature (40 BB +6 / +12 / +11 / +8 / +7 at T=1 / 0.7 / 0.5 / 0.3 / 0; 100 BB −23 / −22 / −15 / −16 / −18), against sampled lynx-4 gain increases monotonically with sharpness: +24 / +43 / +66 / +87 (T 0.7 → 0). **lynx-5t** also monotonic: vs human+fold 40 BB +40 / +47 / +55 (T 0.7 / 0.5 / 0.3; greedy +64), 100 BB +52 / +59 / +71 (greedy +66); vs lynx-4 sampled −30 / −1 / +22 (greedy +33). Exploitability duels: lynx-4 T=0.5 vs lynx-4 greedy **−63** [−79; −47], T=0.3 vs greedy −43; lynx-5t greedy vs lynx-4 greedy +10 [−1; +22]; lynx-5t T=0.5 vs lynx-4 T=0.5 −13 [−25; −1]. **Conclusion: Against all existing (non-adaptive) opponents greedy is consistently best, any temperature > 0 costs; true exploitability of greedy can only be measured with a learning exploiter (`train exploit`, next step).** The net lynx-4 remains negative against the human bot at 100 BB at any temperature—the teacher-fit (lynx-5t) is the real lever there, not sharpness. Testbed T=0.5/0.3 running (`temp-pruefstand.txt`).
- **Turn value net, first shard (teacher-1, 12:53):** `turn-leaf-00000000.npz`, 22,136 lines from 2000 flop seeds (11 per flop), 0 errors, zero-sum remainder 0.021 pot, 3.3 s per solution per process; retrieved after `data/valuenet/hetzner-turn/` and created as private Kaggle dataset **`YOUR_KAGGLE_USER/lynx-vdata-turn`** (`cloud/kaggle-upload-turn.sh create|version`). Kaggle kernel **`cloud/kaggle/lynx-train-vnet2/`** (River + River-Leaf + Turn-Leaf mixed, turn shards doubled, each last river-leaf and turn-leaf shard as clean test per street in test.json, optional RESUME from vnet-river-1). **Baseline: vnet-river-1 on turn lines MAE 0.090 pot** (river 0.019)—without turn training `leaf=4` is unusable.

- **Testbed with temperature (13:05–13:20, `temp-pruefstand.txt`, hu480 / mensch480 / mix960):** lynx-4@300 sampled 46.5 / 115.1 / 59.3; **T=0.5 53.5 / 127.2 / 75.5; T=0.3 53.3 / 127.3 / 78.5; greedy 55.8 / 128.2 / 79.8**; lynx-5t T=0.5 35.0 / 98.4 / 57.2 (greedy 35.6 / 103.2 / 61.3). Also in tournament format monotonic: the sharper, the better, T=0.3 practically equal to greedy. The live advisor (`pc.cmd live`) plays greedy anyway (without `--mischen`), the league/testbed reference was previously sampled—**new reference for comparisons: `nn?run=lynx-4@300&greedy=1` (lynx-4-300-g).** Exploiter test (`train exploit`, starting lynx-4@300) running against greedy, sampled, T=0.3 and lynx-5t greedy (`exploit-greedy.txt`).

- **Exploiter Test Greedy vs Sampling (13:22–17:31, `exploit_greedy.cmd` → `data/bench/exploit-greedy.txt`; laptop was ~13:35–17:10 in sleep mode):** `train exploit <Prüfling> --init lynx-4@300` (40 iterations against 5 copies, ROI on 48 fresh boards, smaller = more robust): **lynx-4 greedy −15.0 % [−26.7; −3.3]**, lynx-4 sampled −3.8 % [−18.4; +10.9], lynx-4 T=0.3 +8.7 % [−3.2; +20.7], **lynx-5t greedy +24.6 % [+8.6; +40.5]**. Greedy lynx-4 is not more exploitable than sampling with the best available tool, rather more robust → **lynx-4@300 greedy is standard and reference.** lynx-5t (teacher fit on human opponents) is clearly exploitable: a human exploiter that allows itself to be exploited – use only against human opponents, not against learning/strong opponents.
- **Turn shards 0–3 collected (17:18): 88,252 lines, 0 errors** (`data/valuenet/hetzner-turn/`), Kaggle dataset `lynx-vdata-turn` version "Shards0-3", kernel `lynx-train-vnet2` started (test = shard 3). Server: 84 min per shard, shard 9 ending around 02:00.

- **First turn-capable value network vnet-2 (Kaggle T4, 17:33–18:35, 62 min, `data/valuenet/vnet-2.pt`, log `data/valuenet/kaggle-vnet2/`):** 2048×3, 60 epochs, 1,111,280 lines = 500k River + 19 river-leaf shards + 3 turn-leaf shards (66k lines, double weighted); hold-out MAE 0.0209 Pot. Clean test on held-out shards: river-leaf 0.0338, **turn-leaf 0.0544 Pot** (vnet-river-1 on turn lines 0.090). Local: turn-probe MAE 0.090 → 0.051, EV error 0.047 → 0.034 Pot; river oracle MAE 0.047 → 0.053 (slightly worse on river, EV error 0.041 → 0.029). First flop search with `leaf=4` (all 47 turns, turn leafs by vnet-2) running, but 7× slower than leaf=5 with 6×6 drawn cards (12.6 s instead of 1.6 s at 60 iterations) – for use leaf=4 turn sampling needed. Retraining with all 10 shards (~220k turn lines, server done ~02:00) (vnet-2b).

- **Flop search leaf=4 versus reference (18:50, `scratchpad/leaf4_vs_ref.py`, 6 random flop situations, 60 It., 4 threads):** Reference = leaf=5 with ALL 47 turns and 6 rivers (vnet-river-1, 4–21 s). Mean deviation to reference (EV in pot / range-weighted strategy distance at root, 0…1 / time): **previously leaf=5 6×6: 0.112 / 0.471 / 2.1 s; leaf=4 all turns (vnet-2): 0.144 / 0.233 / 12.6 s; leaf=4 k_turn=8: 0.124 / 0.369 / 2.3 s; leaf=4 k_turn=12: 0.083 / 0.388 / 3.5 s.** Two insights: (1) Drawing only 6 turn cards makes the root strategy of the previous flop search very noisy (distance 0.47 to same search with all turns). (2) With the turn net halfs leaf=4 this distance on all turns, and already with 8 drawn turns is closer to the reference at equal compute time than 6×6 – although vnet-2 has only seen 3 turn shards. Next step: allow `k_turn` also at leaf=4, then benchmark search `leaf=4` against net and human bot (on server, after tranche), and vnet-2b with all 10 shards.

- **Search: new options `bpgreedy=1` (blueprint net plays greedy where no search is done, i.e. preflop; the ranges remain the learned mixture), `greedy=1` (the search takes the top action of its mixed strategy), and `k_turn` at `leaf=4` (draw turncards instead of all 47); tests in test_husearch.py (19:10).** Measurement run `bench_humanopp3.py` (detached, 8 processes, `data/bench/humanopp3.txt`, 40 blocks × 120 hands per cell = 4800 hands) against human+fold at 40/100 BB: net-g, lynx5t-g, C (server base +30/+29), C-bpg, C-bpg-g, C-5t-bpg (blueprint lynx-5t), C-leaf4 (vnet-2, leaf=4, k_turn=8). Question: does the search with greedy preflop net and turn net beat the greedy student (+64/+66)?

### 6.9 Target Chart (`GOALS.md`, `pc.cmd bench ziele lynx-3-300`)

| # | Benchmark | Levels | lynx-3-300 status |
|---|---|---|---|
| 1 | Real PokerTH Tournaments | 50 tournaments ROI > 0 → 200 tournaments ROI > +20% and win rate > 1/6 | **6 tournaments (28/29.10., PokerTH bots "normal"): places 1, 3, 6, 6, 1, 1 → 3 wins, ROI +70%** (statistically still insignificant, see 8.6) |
| 2 | mensch480 | ROI ≥ +100% → ≥ +120% | +96.8% [91.3; 102.2]: just below Level 1 |
| 3 | Slumbot | > −15 → > 0 → lower 95% boundary > 0 (each ≥ 20,000 hands) | lynx-3: adjusted −17.2 [−38; +4] @10,000, Level 1 narrowly missed. **lynx-4-300: +0.2 [−29; +30] @10,000 (29.10.), Level 1 reached, Level 2 not secured** |
| 4 | Exploitability | exploiter ≤ +5% | +2.3%: **achieved** |
| 5 | Endgame HU 20 BB | nash240 ≥ 0 → kurz240 > +20% | +17.9% / +83.3%: **achieved** |

Deliberately no goal: matching humans (similarity is not a strength) and training on Slumbot.

---

## 7. Chronicle: what was tried, including failures

### Sat 25.10.2026: Basics

- Project found on the stick. The user clarified: **Visual capture is the experiment itself**, no shortcuts via log or DOM.
- **Collector built:** Layout, Windows OCR, parser, cards, analysis, stabilization, journal, reconstruction, live source, export-import, comparison, baseline advisor. Initially checked on just one preflop screenshot, 36 tests.
- **AI levels 1–3:** engine, bot pool, duplicate evaluation, tournament mode, push/fold Nash, league with rating, human vs bot mode.
- **First contest:**
  - Cash: tag +140 bb/100, station −185
  - Tournament: rock +57% ROI vs tag +39% (survival pays off with 3 paid places)
- **CEM style optimization** → opt-1: Gate vs tag +8.9% passed, benchmark SNG best, league rating below tag. Indication of **overfitting or non-transitivity**.

### Sun 26.10.: learning bot, speed, first real recordings

- **League Training 1** (start day): Gate +5.2 on 120 schemas, confirmation on 300 schemas −5.3 → failed.
- **League Training 2** → opt-2: Gate +8.5, confirmation +1.9 [−2.2; 6.1] → removed from the league.
  - Found: **All gates shared seed 777** (worn out). Now each run has its own seed.
  - Conclusion: Style parameter tuning is exhausted.
- **Network plus PPO:**
  - **nn-1** (no leash) learned to exploit the league: Pool ROI +84%, Gate vs rock −8.5%, Pluribus agreement 63 → 13%.
  - Lesson: Without anchor or leash, exploitation arises, not good poker.
- **PHH/Pluribus** loaded. The engine replayed all 10,000 hands identically. BC → pros-1/plu-1 with 84% agreement, weak in tournament (Pluribus doesn't know short stack play).
- **Testbench, numba acceleration (~85×), MCCFR, exploiter test built.** User aims for "better than Pluribus".
- **pros-2** (large batches with 512 tournaments/iteration) passes **Gate vs rock with +19.8%**, exploiter only +3.8%. **Breakthrough:** Large batches were the key.
- **cfr-1** (table-based CFR): weak and exploitable (+69%).
- **Random opponents, exploiter in training, ranges, feat-2, search level 1** built → pros-3, pros-r1.
- **First real PokerTH recordings** (21:56–23:12, 6- and 4-player table, with log export):
  - First evaluation: actions 18 % / 5 %
  - After corrections same evening (seat memory, glyph ranks, timing): **88 % / 89 %, board 100 %, amounts 99 %**
  - Insight: PokerTH standard is 50 BB, blinds every 9 hands
- **Memory issues:** Deep CFR plus post-evaluation simultaneously → both terminated. From then on: sequential.
- **Deep CFR** dcfr-1: iteration 10 +5.3%, iteration 20 +5.7%, iteration 30 −16.1% (typical Deep CFR crash).
- **Multi-format training built** (2–10 players, 20–200 BB, turbo to slow) plus format testbench.

### Night 26/27 October: first autonomous night run

- **pros-r2** (multi-format from pros-r1@300):
  - Gates @300 and @600 failed against pros-ppo2
  - Testbench declining over several measurements → aborted at iteration ~690
- **pros-r3** (from pros-r2@350, learning rate 1.5e-4, leash 0.5): Gate @200 **+13.3% passed**, @400 and @600 failed.
- Format testbench in the morning: all candidates tied within noise.
- **Stick failure 07:10** (controller error). Deep CFR went to iteration 62, checkpoint @60, but was −31% → **Deep CFR abandoned**.

### Mon 27 Oct: precise testbench, opponent model, live, human bots, Lynx

- **Large testbench** (`praezise`, ±3 instead of ±12), `bench compare`, Slumbot integration (user authorized).
  - Result: **pros-r1@300 is best bot**. Gate winner ≠ best bot.
  - Search level 1 is harmful (−18.9) and discarded.
- **Opponent model** (opponents, feat-3), `widen_net`. Training **pros-o1** paired at @100/@200 −3.9/−4.4 against pros-r1@300 → aborted.
- **Live connection:** LiveBot with live reconstruction, hand history, opponent model, `live-replay`. Old bug fixed: only one suggestion per session.
- **Slumbot leak analysis** (pros-r1, ~11,000 hands): heads-up too tight (button fold 40%, BB fold 51%), about −31 bb/100 share.
  → **act-2** (min-raise, ⅓ pot), `--self-play-seats`, `--table-weights`, `--anchor-min-players`.
- **pros-h1@600 = new best** (confirmation +6.0 [1.4; 10.6]).
  - **Lesson:** Self-play seats, exploiter, many HU and 3-player tables and leash starting from 4 players together bring success.
  - Slumbot: button fold 40 → 13%.
- **HandHQ evaluated** (5.72 million hands), **human bots** built, testbench **mensch480**.
  - pros-h1@200 led there, confirmation against @600 with +4.0 [−0.6; 8.6] failed → **Lynx = pros-h1@600**.
- **Name "Lynx" chosen by user. Asked about poker AI competitions: The ACPC ran from 2006 to about 2018, no open competition currently known.
- **lynx-2** (40% human bots): mensch480 +17.7 against Lynx, both confirmations passed → **lynx-2@500 new best**.
  - **Lesson:** **Human bots as training opponents brought the biggest leap so far.**

### Night 27/28 October: lynx-3

- Night run up to 1500 iterations: only Gate @300 passed, then a **plateau** (Gates @600–1500 against lynx-3-300 all failed).
- Memory watchdog terminated parallel Slumbot run. Slumbot then ran only after training.
- **Stick failure 04:15** ("No Media"). Training was already finished at 03:58, nothing lost. Reconnected only at 10:00.
- Predefined confirmations **both passed** → **lynx-3-300 live standard** (10:07).

### Tue 28 Oct: Search, goals, toolbar, live fixes, honest Slumbot numbers

- **Heads-up search (husearch)** built. The user wanted "search at runtime" as the biggest leverage.
  - hus-1 (from Turn): Slumbot −12.6 @3,000, huge interval
  - **hus-2: temporarily −440 bb/100**, aborted after 458 hands (raw −396, all-in EV −382)
  - **Cause:** Re-solving from the current node with heuristic range did not fit the situation. Many all-ins with weak hands were lost.
  - **Fix:** Solve **from street start** with the actual path.
- **HU preflop solver** built and integrated → hus-3.
- **Goals defined** (`GOALS.md`, `ai/ziele.py`), test bench sets nash/short.
- **Lynx bar** built (invisible for recording, sound), accepted by the user.
- **Live fixes:** Pot semantics (`info.total`), missing `pot.total`, OCR outliers, minimum raise, greedy mode.
- **Findings on mini-bets:**
  - Lynx often bets 1 BB postflop in big pots.
  - The suspicion "human bots fold unrealistically to mini-bets" is **not** correct: The style bots almost always call mini-bets (Equity ≥ pot odds − tolerance).
  - The behavior is thus rather an artifact or a weakness of the network and is not pursued further.
- **Memory watchdog** stopped hus-3 (at 1,833 hands) and the PokerTH comparison. Restarted later as a chain.
- **Stick failed on standby** → USB power saving disabled via powercfg, keep-alive script.
- **Error in the chain:** A stopped monitor kept running, causing **everything to run twice**: Slumbot with 8 instead of 4 sessions, a total of 8,167 instead of 5,000 hands, and the PokerTH comparison twice. This caused the RAM shortage. The duplicate was terminated.
- **Slumbot baseline clarified** → cleaned measure as main measure. The search is **not better** against Slumbot; its advantage was card luck (+29).
- **Automatic tournament detection and entry** built. The user wants results to be recorded automatically. 171 tests green.
- **Evening:** everything stopped, `pc.cmd live --leiste` started, the first real live test with Lynx advice against PokerTH bots is running.

### What did not work (overview)

| Approach | Result | Why |
|---|---|---|
| Style parameter tuning (CEM) | exhausted after opt-1/opt-2 | 10 sliders not enough, otherwise only noise is found |
| PPO without leash (nn-1) | learns bot exploitation | opponent pool too narrow, no anchoring on good play |
| Pluribus only imitation | weak in tournament | Pluribus does not know short-stack tournament play |
| Tabular CFR | weak, exploitable | coarse abstraction, too little compute time |
| Deep CFR | unstable, collapse after iteration 30 | strategy net trained anew each time. Would need a server. |
| Rollout search stage 1 | −18.9 | assumption everyone plays like our net |
| Multi-format training alone (pros-r2/r3) | no measurable gain | diluted over 6-player sets. Successful later with table weights (pros-h1). |
| Opponent model training (pros-o1) | worse than pros-r1 | too early, without other ingredients |
| lynx-3 beyond 300 iterations | plateau | recipe exhausted, new ingredients needed |
| husearch from current node (hus-2) | −440 bb/100 | ranges did not fit tree |
| husearch vs Slumbot (hus-3) | cleaned −23.7, not better than the net | postflop abstraction coarse (few sizes), uncertain re-solving without guarantee |

---

## 8. Current status, assessment, weaknesses, roadmap

### 8.1 Best version

**lynx-3-300 = `nn?run=lynx-3@300`**: network feat-3 / act-2, 57 features, 8 actions, MLP 128×128. Live standard, greedy.

| Strength (measured) | Value |
|---|---|
| Simulated human tables (PokerTH format) | **+96.8 % ROI** |
| vs predecessor lynx-2 (fresh tables) | +9.2 %, secured |
| Exploitability | Exploiter +2.3 %, no gross leaks |
| Endgame HU 20 BB | +17.9 % vs Nash, +83 % vs human bots |
| Slumbot | **cleaned −17.2 bb/100** |

### 8.2 Level assessment (estimation, not measurement)

- **Against casual players or typical PokerTH field:** probably clearly winning. Lynx plays disciplined, is hardly exploitable, and knows no tilt.
- **Against strong bots or pros:** clearly inferior. −17 bb/100 vs Slumbot (top HU bot from around 2018) means that noticeable errors remain against equilibrium, especially postflop.
- **Rough classification:** solid amateur or micro-stakes regular. Better than average on play-money platforms, not on pro or solver level.
- **Caveat:** The human bots are replicas. Real PokerTH tournaments (goal 1) are still missing. Only 10–20 real tournaments allow better classification, 100–200 a reliable one.

### 8.3 Known weaknesses

1. **No ICM:** Optimized chip-EV, not tournament payout.
2. **Postflop weaknesses against strong opponents** (Slumbot), including **mini-bets** (1 BB in big pots).
3. **No real adaptation to opponents in-game:** The opponent model is included as a feature but no search against opponent range.
4. **Search only heads-up** and not better against Slumbot. Whether it helps in PokerTH formats is **open**, comparison was never finished.
5. **Live collection:**
   - Checks sometimes at wrong seats
   - Pot and starting stack OCR outliers
   - only foreground capture
   - table sizes other than 4/6 untested live
   - diamonds and clubs not systematically checked
6. **Simulated opponents:** Human bots from 25NL online data from 2009, no PokerTH bots or humans. Postflop values (WTSD, C-Bet) partly poorly matched.
7. **Infrastructure:** USB stick unreliable, 16 GB RAM limits parallelism, no GPU.

### 8.4 Open points (concrete)

- [x] **Evaluate live test** (Oct 28/29): done, see 8.6
- [ ] **PokerTH comparison search vs net** (hu480): running night Oct 28/29 after training (`night_lynx4.sh`). Only with paired win will the search become live standard.
- [ ] Collect real tournaments (goal 1: 50, then 200); switch to “hard” after 10 tournaments and keep separately
- [ ] Update league report (`league run`), it is outdated
- [ ] `compare`: assign derived hands (without read hand number) to log by order and cards
- [ ] Incorporate code review findings of night Oct 28/29 (`scratchpad/review-live.md`, `review-ki.md`)

### 8.5 Roadmap (ideas, by expected benefit)

1. **PokerTH-specific opponent models:** Derive PokerTH-specific human and bot profiles from real PokerTH sessions (Collector) for training and testing. This is closest to Goal 1.
2. **Improve human-bots:** More accurately capture postflop metrics (WTSD, C-Bet, fold to bet) to make training more realistic.
3. **ICM** in reward or search for tournament decisions near the payout positions.
4. **Search with opponent model ranges** instead of pure equilibrium (exploitative, more profit against weak opponents). Finer postflop bet sizes and more iterations for the Slumbot path.
5. **New training ingredients against the plateau:** larger network, learning rate schedule, ICM reward, more exploitative opponents, search as teacher (Expert Iteration).
6. **Collector:** Assign checks, start stack timing, all table sizes, all suits systematically, later Windows.Graphics.Capture (resistant to occlusion).
7. **Server** (Hetzner or dedicated cores) for long runs (Deep CFR, larger networks), freeing up the laptop.

### 8.6 Addendum: first live evening 28/29.10.2026 and the subsequent night

**Six real tournaments** (6-player tables, PokerTH bots, difficulty "normal", advisor lynx-3-300 greedy, Jakob clicking):

| Game | Place | Hands | Remark |
|---|---|---|---|
| 1 | **1** | 35 | Export available (`sessions/20261028-222209/pokerth-log.txt`) |
| 2 | 3 | 20 | no export; place simulated from recording |
| 3 | 6 | 10 | Q7o Jam was a phantom suggestion (hand number stuck) |
| 4 | 6 | ~7 | KK against Ace on A-Q-4-4, two calls |
| 5 | **1** | 25 | Export available (`sessions/20261028-234434/pokerth-log.txt`) |
| 6 | **1** | 31 | Heads-up against Falcon Fay |

Target table: 3 wins out of 6, ROI +70%. Random would be 1 out of 6 wins. With 6 tournaments, the 95% confidence interval is approximately −60% to +200%.

**What the live chain learned** (all fixes the same evening, each re-simulated on all recordings and tested):

| Problem | Cause | Fix |
|---|---|---|
| Suggestions 10–20 s too late | Analysis queue (3 images) was always full, analysis ~270 ms/image; plus idle time and confirmation | `pipeline.py`: Queue only holds the newest image, older images discarded; status shows "image age". Then suggestion 0.7–1.8 s after recognition. |
| Phantom suggestions ("Raise 0", "Raise 6000" after hand end, after own all-in, after opponent fold) | Buttons/markers stuck briefly | `live.py`: `playable()` (table present, own stack > 0), no suggestion without own cards or if all opponents folded, `sane()` caps raise to stack, converts "Raise ≤ max bet" to call/check |
| Flickering (Raise 45 → 40 → 41 → 65) | each OCR correction generated a new suggestion | SETTLE_S 0.7 s; `same_as_shown()`: same street, type, and amount ±25% trigger no new suggestion; cards used as key |
| "Wrong cards" (user impression) | **Hand number OCR stuck for 10–20 s**; new cards processed under old hand with its history and pot | `reconstruct.py`: new hand also on board → 0 despite old number and dealer change (MIN_HAND_S 4 s after hand start), delayed number adopted (ADOPT_S 30 s). Against log of game 1: actions 78/80% → **88/88%**, dealer/SB/BB 74% → **100%**, amounts 94 → 97%, start stacks 89 → 93%. Session from 26.10. did not worsen (dealer 92 → 100%). |
| Stack "51000" instead of "1000" | "$" read as "5" | `fix_dollar_misreads()` for live observation (OCR itself still open) |
| A plausibility filter (stacks + pot ≤ tournament chips) | blocked **real** decisions (bets double counted, OCR outliers) | removed again: prefer phantom over missing decision |
| Tournament end not detected (games 1, 4, 5, 6 each differently) | All-in without readable stacks; end screen before pot credits; table disappears 1 s after out; PokerTH locally counts every game as "Game 1" | `TournamentWatch`: all chips in one stack → place 1/2; own stack 20 s at 0 (also unreadable) without new hand → bust, opponents = union of "still seated", last stacks and survivors of last hand; heads-up all-in with larger stack → win; win confirmed after 20 s with no new hand; restart at hand number rollback. Re-simulated all 6 games: 1, 3, 6, 6, 1, 1 (correct). |

Open issues with the Collector: `compare` assigns only via hand number (game 5: 14 of 25 hands assigned despite correct reconstruction); checks at wrong seat; "$" reading error in the OCR itself.

**ICM (night 28/29.10):** `ai/icm.py` (Malmuth-Harville, prize from payout structure). `RLConfig.icm` mixes the reward: (1 − icm)·Chips + icm·ΔEquity, bust counts actual payout of place. CLI `train rl --icm 1.0`. Tests `test_icm.py` (6, incl. rollout). Testsuite 29.10 02:00: 185 tests green.

**Night run lynx-4** (`night_lynx4.sh`): lynx-3@300 continues with `--icm 1.0`, learning rate 2e-4, exploiter every 50 iterations, table weights 2:3, 3:3, 4:2, 5:2, 6:4, stages 300/600/900/1200 with gate (600 schemas) against lynx-3-300, test bench every 100 iterations against lynx-3@300. Afterwards search vs network on hu480 (`bench_hus_nacht.py`). Results: `data/rl/lynx-4/night.txt`, `data/rl/lynx-4-run.txt`, `data/bench/hus-vs-netz-pokerth.txt`.

**Result stage 300 (29.10, 03:40): Gate passed.** `nn?run=lynx-4@300` against lynx-3-300 on 600 fresh schemas: ROI 44.5% vs 34.5%, difference **+10.0% [+5.4; +14.6]** → in the league as **lynx-4-300**. Test set on same schemas as lynx-3@300 (paired difference, from `per_scheme` in `data/bench/results.jsonl`):

| Set | lynx-3@300 | lynx-4@100 | lynx-4@200 | lynx-4@300 | paired @300 − lynx-3 |
|---|---|---|---|---|---|
| mensch480 | 96.8 | 115.8 | 108.2 | 115.1 | **+18.3 [+13.1; +23.5]** |
| mix960 | 50.6 | 68.9 | 59.5 | 59.3 | **+8.7 [+4.9; +12.5]** |
| pokerth480 | 35.2 | 55.9 | 45.0 | 47.5 | **+12.3 [+7.5; +17.1]** |
| 10max240 | 73.6 | 100.2 | 84.7 | 87.0 | **+13.5 [+4.6; +22.4]** |
| hu480 | 49.6 | 51.2 | 50.6 | 46.5 | −3.1 [−8.2; +2.0] |
| Pluribus top-1 | 0.798 | 0.804 | 0.805 | 0.814 | – |

Version: ICM reward plus exploiter yield noticeably something on full tables, nothing heads-up (rather slightly worse). **Noticeable: lynx-4@100 is even stronger on all multiplayer sets than @300** (mix960 +18.3 instead of +8.7 against lynx-3) – as already with pros-r1 the gate winner is not automatically the best state. Fresh test on 29.10. 12:50 (`train gate "nn?run=lynx-4@100" --champion lynx-4-300 --schemes 600 --seed 2910`): @100 against @300 **+1.6 [−3.0; +6.1]**, so no reliable difference – the lead from the test bench was noise on the hardwired schemata. lynx-4-300 stays. Exploiter against lynx-4: @50 +22.5, @100 +1.2, @150 +3.3, @200 −15.8, @250 +16.7, @300 +12.1 (all intervals include zero).

**Night Review-Fixes (Live path, all with tests, `tests/test_live_review.py`):** Pipeline catches errors in event evaluation (counter `event_errors`) instead of losing the analysis thread; `LiveBot` with lock (events from analysis thread vs `poll` of display), `playable()` before consumption of quiet time (brief unreadable stack no longer swallows decisions), agent only after cheap checks, `table.found` incorrect → not on it, `same_as_shown` amount-sensitive (Call 60 → Call 300 is a new decision); `session_ended()` reports ongoing elimination at session end and starts fresh; `TournamentWatch`: victory "all chips" only for exact amount or no opponent chips, open first place discarded if opponent shows chips again, elimination timer stops with opponent activity, hand number rollback only for hand ≤ 2 or equal start stacks, tournament chips only when start is certain; Replay: unreadable stack is not all-in, straight "showdown" from board; Capture/Journal/Analyzer/Reconstruct/OCR minor fixes (grab error → `source_ok` incorrect, lock in journal, empty buttons confidence 0.5, all-in reset for stack > 0, throttled OCR fallback); Search: `oop` = first seat left of button, dead money halved, sigma no longer materialized (memory), preflop cache quantizes stacks from 30 BB to 1 BB, from 60 BB to 2 BB; Slumbot seed crc32 (platform-fixed); goalboard `t95` and `remove_last_tournament` (`bench turnier --ersetzt`). Reports: `data/review-live.md`, `data/review-ki.md`. Not yet integrated (waiting for training end, because worker `rl.py` import): anchor KL unfolds the new actions to raise ½ pot, hint on differing call configuration on resume, ICM place on simultaneous elimination.

**Result of whole night (09:15): lynx-4-300 remains the winner.** Gates against lynx-4-300: @600 +3.1 [−1.2; +7.4], @900 +3.4 [−1.2; +8.0], @1200 +4.3 [−0.0; +8.6] – all failed, same plateau pattern as with lynx-3 (only first segment passes the gate). Paired against lynx-3@300 at @600 human480 +18.9, mix960 +12.3, pokerth480 +14.9, 10max240 +14.6, hu480 +1.9 [−3.6; +7.3]. **Since 29.10. 10:00 lynx-4-300 is the live standard** (`--agent` specification in `live`, `live-replay`, `bench ziele`, `bench turnier`). Test suite after all review fixes: 198 green.

**First tournaments with lynx-4-300 (29.10. mornings, PokerTH bots):** Game 7 place 2 (29 hands, export in `sessions/20261029-092058_2e5fa2b4/pokerth-log.txt`), Game 8 place 4 (24 hands). Both places were automatically correctly recognized and entered by `TournamentWatch`. Overall goalboard: 8 tournaments, places 1, 3, 6, 6, 1, 1, 2, 4. Comparison of recording vs log in game 7: 25 of 30 hands assigned, action precision 0.79 / recall 0.85, amounts 0.99, dealer/SB/BB 0.84–0.88, start stacks 0.82 – weaker than game 1 after fixes (0.88 / 1.0); unclear whether this is due to session (many partial hands, seat assignment) or the night changes.

**GTO-Wizard benchmark (29.10. afternoon, released by Jakob):** second external yardstick besides Slumbot. Opponent is GTO Wizard AI (formerly Ruse), HU 200 BB, evaluation with AIVAT (approx. three times smaller variance than raw winnings). `ai/gtow.py` according to pattern of `slumbot.py`: progression `bX`/`_` is translated into Slumbot notation and reconstructed in engine with `slumbot.replay`, countercheck of results per hand, results in `data/bench/gtow/<name>.jsonl`. CLI `pc.cmd bench gtow <spec> --hands N --workers 2 --server`. Access requested (key self-chosen, stored locally in `data/bench/gtow/api_key.txt`), approval by mail pending. Ranking on 29.10.: best bots lose about −3 bb/100, a pro with −3.9, GPT-6 with −5.4. Expectation for lynx-4-300: −20 to −40. Provider rule: 100,000 hands per month, only play and results, no solver functions. Only yardstick, no training goal.

**Goal clarification and milestone 3 (29.10. afternoon/evening):** Jakob: goal is maximally good poker against all opponents, especially humans, not against bots of a platform. From this `NEXT_STEPS.md` 7a (H8 bot reconstruction removed, H5 search as teacher remains core, H6 focused on humans) and `VALUE_NETWORK_MILESTONE.md`: search with value network in DeepStack order (river network first, then leaves in turn tree, then turn and flop networks), data on Hetzner CPX51 hourly, training on Kaggle (free, private), code remains private; runbook `cloud/VALUE_NETWORK_CLOUD.md`. Built on 29.10.:

| Module | Status |
|---|---|
| hus-2: Flop in search tree | drawn Turn/River cards (`k_turn`/`k_river`, partial unbiased), presets `narrow`/`wide`, spec `streets=preflop,flop,turn,river` |
| Kernel layer-wise parallel | numba `prange` over BFS-level nodes, leaves without copies, `warmup()` on start; identical results, 2.5–3.3× faster under load |
| Live pace | Flop 2.1 s, Turn 1.3 s, River 0.4 s under full load (spec with `k_turn=4&k_river=4&k_river_turn=16&iters_flop=20&iters=40&iters_river=120&threads=12`) |
| hus-3: leaf nodes | `LEAF` nodes replace river subtrees, values from `valuenet.predict` per `leaf_every=10` iterations from current ranges; oracle test (river exactly solved as “network”) reproduces full turn tree (`test_husearch_leaf.py`) |
| `ai/valuedata.py` | situations at street start (pot 2–80 BB, SPR 0.25–8), board-related synthetic ranges, exact solution, `.npz` shards; CLI `train valuedata`; river 0.5 s per situation |
| `ai/valuenet.py` | standalone (numpy + torch), 2712 → 1024×3 → 2652, Huber + zero-sum penalty, exact zero-sum correction in prediction; CLI `train valuenet`; runs unchanged on Kaggle |
| GTO-Wizard integration | `ai/gtow.py`, access requested |

Tests for these: `test_husearch.py` (12), `test_bpranges.py` (5, blueprint ranges 30.10.), `test_husearch_leaf.py` (3), `test_valuedata.py` (3), `test_valuenet.py` (3), `test_gtow.py` (6).

**Night failure:** `bench_hus_nacht.py` crashed with `BrokenProcessPool` because the script lacked `if __name__ == "__main__"` protection; under Windows (spawn), each worker re-executed the main script and thus called `run_bench` again. Fixed, rule applied for all scripts with process pool.

**Plan for the next level:** `NEXT_STEPS.md` (29.10.), including a savings variant (€0 for phases 0–1 with ThinkPad, existing VPS, and Kaggle; phase 2 hourly cloud ≈ €10–30 per batch).

**Evening 29.10. (9–11 pm):**
- **Checked cloud accesses:** Hetzner token (project "lynx") and Kaggle access token (account YOUR_KAGGLE_USER) are stored in `data/cloud/` (not in backup), SSH key `lynx_hetzner` registered at Hetzner. `cloud/hetzner.py` (API without `hcloud`: types/list/create/push/ssh/pull/delete), `cloud/server-setup.sh`, `cloud/run-vdata.sh`. Price finding: **cx53** (16 cores, €0.056/h = 0.35 cents per core-hour) instead of cpx51 (0.85 cents). Kaggle end-to-end: private dataset `lynx-vdata` + script kernel `lynx-train-river` (T4, 3000 situations × 20 epochs in 10 s, holdout MAE 0.20). No server started.
- **Slumbot lynx-4-300 completed** (10,000 hands): cleaned +0.2 [−29; +30], see 6.7.
- **hus-1 on hu480 completed: −29.4 against the network; night diagnosis Phase A: preflop solver alone costs −25.2** (6.8). hus-2 canceled overnight, instead Phases B and C (`bench_diag_nacht.py`).
- **Live error found (two evening tournaments, session 20261029-202109):** On the final screen of the first tournament, the winner stack "$13408" was read as the **bet from seat 5**. The value remained in the table state because seat 5 in the second tournament did not place a bet for a long time to overwrite it. Since the pot is formed from "total" + bets, the entire second tournament showed a **pot of 13438 instead of 30** in every decision; the network saw a huge pot with a tiny call and advised accordingly (T9s preflop All-in 97%). Two corrections in `ai/live.py`: `fix_dollar_misreads` removes bets that together with the stack exceed all tournament chips; **`drop_stale_bets`** removes bets in the image for which the reconstructed hand shows no action from the seat (blinds without events remain). Replay of the session: pot back to 30, 19 of 155 suggestions changed. Tests `test_live.py` (+2). Open issue: the chip total of the tournament (`TournamentWatch.chips`) was itself distorted (68,000 vs. 17,408), so the two tournament seats were not recognized and for tournament 1 "seat 1" was incorrectly marked (never reported).

**Morning 30.10. (09:00–09:30), night diagnosis completed, search rebuilt, Hetzner pipeline passed:**
- **Night diagnosis complete** (6.8): Phase C undecided (−0.6 bb/100 [−62; +61]), verification deterministic. Overall interpretation: Preflop solver is the main leak (−25), postflop search −8.5, no detection in home format. Consequence implemented: **hus standard `streets=turn,river` and `ranges=pre`** (blueprint ranges, 4.9, new module `bpranges.py`). Measurement D/E running (`bench_hus1bp.py`).
- **Hetzner 1000-test passed (3rd attempt, ~5 ct):** cpx62 (the cx series is sold out everywhere), setup 37 s, 1000 river situations in 19 s = 0.28 s per situation and core (laptop 0.43) → **Batch 500k ≈ 2.4 h ≈ 0.60 €.** File `data/valuenet/hetzner-test/valuenet/river-00000000.npz` locally checked (format and statistics like local sample, zero sum 1.7e-5). Three errors on the way, all fixed in `hetzner.py`: ssh without console hung (BatchMode), Git-Bash mangled server path `/opt/lynx/...` and first run lost because server deleted before check (`remote_path`, `pull` aborts on empty result, order pull → check → delete), reassigned IP with old host key blocked SSH (`ssh-keygen -R`). API change: servers carry `location` instead of `datacenter`. **Batch 1 (Go 09:40) ran 09:44–12:18 on cpx62: 20 shards of 25,000 river situations each (7.6 min each, 116 MB), total 2.2 GB in `data/valuenet/hetzner-1/valuenet/`, locally checked (0 errors, zero sum 2.2e-5), server deleted 12:30, cost ≈ 0.69 €.** For training on Kaggle, `valuenet.train()` was made memory-efficient (inputs/targets float16, mask once as bool, ranges from inputs instead of separate: around 6 instead of 27 GB at 500k). `train_river.py` now training 1024×3, batch 1024, 30 epochs; `SHARDS=n` limited for the learning curve.
- Test suite: 223 green, `test_hupreflop` switched to explicit `streets=preflop,…` (224).
- **First river value network (Kaggle T4, 13:07–13:16):** 500,000 situations, 1024×3, batch 1024, 30 epochs OneCycle in 390 s (13 s per epoch). **Hold-out MAE 0.0264 pot** (10,000 situations), zero sum violation 0.0079, training loss 0.0067 (Huber). Target 0.015 not reached; curve flattens in last epochs (0.0269 → 0.0264), gap between training and hold-out error shows more data and capacity should help. Checkpoint `data/valuenet/kaggle-t1/vnet-river.pt`. Two follow-up runs started: `lynx-train-river-curve` (only 8 shards = 200k, learning curve point) and `lynx-train-river-big` (2048×3, 60 epochs). Also local oracle test with 500 fresh situations (seed 999001000; old sample with seed 1000 overlaps with batch seeds and unsuitable as hold-out). **Learning curve and capacity (13:35–13:46):** 200k situations → hold-out 0.0380; 500k → 0.0264; 500k with 2048×3 and 60 epochs → 0.0189 (26 min T4, training loss 0.0024, so clear overfitting regime). **Decisive finding:** On 240 river situations as at leaves of real turn searches (new `valuedata` mode `river-leaf`, locally solved exactly, `data/valuenet/river-leaf-oracle.npz`), expected value error of both nets is 0.12 to 0.13 pot (95% quantile ~0.5), on own artificial distribution 0.004 to 0.005. The leaf distribution differs: stack/pot median 0.44 instead of 1.4, thin and board-shaped ranges (up to 8 effective combos). More capacity does not help there (2048×3 even worse), more broad data barely (error ~ n^-0.4). Used as leaf in turn tree, net is 4.4× faster (2.0 s instead of 8.8 s under load), but root strategy deviates by 16 to 27 %, while already 60 vs 200 exact iterations show 10 % deviation (mixed strategies are not unique, TV is a coarse measure). Consequence: batch 2 must provide `river-leaf` data (one turn search per seed, up to 24 river openings drawn by range mass, ~1 s per line and core), training mixed with batch 1, acceptance on leaf oracle (EV error < 0.02 pot) and playing strength. Waiting for Jakob's Go. **Batch 2 and mixed training (15:02–18:05):** 252,000 leaf situations (`river-leaf`, 10 shards, 1.3 GB, 0 errors, effective combos 4 to 1081, stack/pot median 0.92) in 2 h on cpx62 (≈ 0.50 €), second private Kaggle dataset `lynx-vdata-leaf`. Training on all 752,000 situations: 1024×3/30 epochs → hold-out 0.0285, leaf test set EV error **0.038** (previously 0.121); 2048×3/60 epochs (42 min T4) → hold-out 0.0199, artificial distribution EV 0.0035, leaf test set EV **0.035** (95% quantile 0.19). Leaf data thus brings factor 3.4 improvement, more capacity at leaves barely helps; target 0.02 pending (lever: more or stronger weighted leaf data). Checkpoints `data/valuenet/kaggle-t2/` and `kaggle-t2-big/`. **Game test V** (`bench_hus1v.py`): Search like E, but with `vnet=kaggle-t2-big/vnet-river` as leaf in turn tree, on hu480 vs E (+44.0) and net (+46.5), started 18:10. Note Kaggle-CLI 2.2.5: for `datasets version` folder `%TEMP%\.kaggle-uploads\<relativer Pfad>` must exist, otherwise upload fails silently at first file.

---


**Morning 31.10. (06:00–08:00), fold model, human bot with folds, first measurement against it:**
- `ai/humanfold.py` + `data/humans/human-fold-1.npz` (BCE 0.417, class NLL 4.62 instead of 5.13 uniform), training 37 s on 18.9 million lines; `oppfold=` in search, `&fold=` on net bot (6.8).
- First measurement of search vs human-1 without folds: not evaluable (variance ±200, opponent never folding, fold model not appropriate there). Against human-1 WITH folds the net lynx-4@300 loses at 100 BB −21 [−43; +0], at 40 BB +13 [−5; +32] over 10,000 hands each. Second measurement series of search (A Standard / B opp / C opp+fold) vs this opponent running since 08:08.
- `ai/teacher.py` (H5, search as teacher: TeacherRecorder/collect/fit with KL rope, CLI `train teacher-collect/teacher-fit`), sample 26 lines; Hetzner dataset `cloud/run-teacher.sh` prepared, waiting for Go (~0.75 €).
- Measurement 2 (search vs human bot with folds, 720 hands each): no detectable difference, search not better than net, fold factor without measurable benefit (6.8). Teacher dataset on Hetzner lehrer-1 since 09:00 (6.8).
- Stage 2 (turn net) prepared: valuedata `turn-leaf`, search `leaf=4`; server chain benchmark + turn batch after teacher dataset (6.8).
- Open: teacher fit lynx-5t + gate, GTO wizard access (Gmail), full test suite + backup after new modules.

### 8.7 Addendum 31.10. evening to 3.11.2026: Final night and release prepared

**Final Night 31.10./1.11.**
- **Spec parser error** (31.10. 19:29): `make_agent` split the display name at the **first** colon, `hus?bp=run:lynx-5t@1&...:kand` broke down, measurement aborted. Now the last colon is counted, and only if the name contains none of the characters `=&?@/`; test `test_make_agent_name_hinter_run_doppelpunkt`.
- **Search against the human bot with folds** (`bench_humanopp3.py`, HU Cash duplicate, 4,800 hands per cell, finished 1.11. 05:00, `data/bench/humanopp3.txt`):

| Variant | 40 BB | 100 BB |
| --- | --- | --- |
| lynx-5t greedy | **+77.8 [64.6; 90.9]** | **+73.0 [55.9; 90.1]** |
| Search with lynx-5t as blueprint | +55.0 [33.3; 76.8] | +57.1 [24.3; 89.9] |
| Search greedy, blueprint greedy | +48.4 | +60.8 |
| Flop search with turn net (leaf=4) | +40.7 | +60.7 |
| Search, blueprint greedy | +46.2 | +55.7 |
| Search (base C) | +31.5 | +37.4 |
| Network lynx-4 greedy | +13.0 [−8.6; +34.7] | −14.9 [−40.6; +10.7] |

Each search variant beats the network, none reach lynx-5t; greedy in the search adds about +15.
- **Turn tranche complete** (1.11. 02:55): 10 shards `turn-leaf`, 220,688 lines, 0 defective; server lehrer-1 deleted (ran 31.10. 09:00 to 1.11. 02:54, about €4.5).
- **vnet-2b** (Kaggle, 1.11. 06:25): The first attempt with around 1.37 million lines failed due to lack of memory; with 977,288 lines (12 River-, 19 River-Leaf-, 9 Turn-Leaf shards) hold-out 0.0260, test River-Leaf 0.0336 (vnet-2: 0.0338), Turn-Leaf 0.0510 (vnet-2: 0.0544). Three times as much turn data results in only −6 % improvement: plateau around 0.05 pot.

**Publication prepared (2./3.11.)**
- `make_release.py` builds a clean tree from the project for a public repository (`<Laufwerk>\Lynx-Release\lynx-poker`): whitelist, replacement of private data, secret scan also in `.pt`/`.npz`. Templates in `release/`: README (English and German), MIT license, `.gitignore`, `docs/` with case study, technical documentation, API and CLI reference (generated from the code), data and licenses. Starter package in the repo: league file and ten checkpoints (2.5 MB).
- **Bar with mask instead of camouflage:** The bar no longer hides via `WDA_EXCLUDEFROMCAPTURE`; it is visible in every recording, and `WindowSource` crops its area out of the images of the collector (`capture.apply_masks`, filled with ambient color, note `masked` in sidecar). Practical test: in a normal mss recording 93 % of bar area in action color, after the mask 0 %.
- Further changes: start scripts use an installed `tools\` without `uv`; `test_humanfold.py` finds its data relatively instead of fixed stick path; the bar releases its Tk objects in its own thread (previously exit code 3 due to "Tcl_AsyncDelete" on exit); new tests `test_capture_mask.py`.
- Tests: 249 passed in the project; 247 passed in the exported tree, 2 skipped (require raw data or a value network not included in the repo).

## 9. Appendix: Terms, Files, Specifications

### 9.1 Terms

| Term | Meaning |
|---|---|
| bb/100 | Big blinds won per 100 hands (cash) |
| ROI | Return on investment per tournament in buy-ins (test bench: average net payout) |
| Duplicate / paired | same cards for all bots in all seat rotations; difference per schema |
| Schema | a fixed card set (seed) plus a table |
| Gate / entrance test | candidate vs. title defender on fresh schemas; passed with CI > 0 |
| Leash / anchor (piKL) | KL penalty against a reference bot, keeps learning at “reasonable” play |
| PSRO / exploiter in training | the new opponent is regularly trained against the current exploiter state |
| CFR / CFR+ | Counterfactual Regret Minimization, approaches an equilibrium |
| Blueprint | base strategy (in our case: the network), refined by search |
| Exploitability | how much a perfect counterstrategy wins (0 = equilibrium) |
| All-in EV | equity at all-in before the river instead of card outcome |
| Control variable (adjusted) | result minus β·(card luck) with E[card luck] = 0, less variance |
| VPIP / PFR / 3-Bet / Agg / FtB / C-Bet / WTSD | HUD metrics: voluntarily invested / preflop raise / re-raise / aggression / fold to bet / continuation bet / went to showdown |

### 9.2 Bot specifications

| Spec | Meaning |
|---|---|
| `rock`, `tag`, `tag?push_bb=15&bluff=0.15` | style bot with parameters |
| `nn?run=lynx-3@300` | network from `data/rl/lynx-3/ckpt_000300.pt` |
| `lynx-3-300`, `lynx-2`, `pros-h1`, `lynx` | league names (resolved via `data/league/players.json`) |
| `hus?bp=lynx-3-300&iters=120&iters_river=300&streets=preflop,turn,river` | heads-up search with network as blueprint |
| `search?bp=pros-2@300,worlds=16` | old rollout search (discarded) |
| `cfr?run=cfr-1` | tabular CFR strategy |
| `mensch-1` … `mensch-6` | human bots (specs in `data/humans/mensch-25nl.json`) |

### 9.3 Training runs (`data/rl/`)

| Run | Start | Feature | Result |
|---|---|---|---|
| nn-1 | BC rock | PPO without leash | Exploitation, discarded |
| plu-1 / pros-1 | BC Pluribus | Leash | Base |
| pros-2 | pros-1@0 | 512 tournaments/iteration | Gate vs rock +19.8 % (league pros-ppo2) |
| pros-3 | pros-2@300 | random opponent + exploiter | mix96 up to +24 |
| pros-r1 | – | feat-2 (ranges) | best long @300 |
| pros-r2 / pros-r3 | pros-r1@300 / pros-r2@350 | multi-format | pros-r3-200 passed gate |
| pros-o1 | – | feat-3 opponent model | aborted |
| pros-h1 | – | feat-3 + act-2, self-play seats, HU weights | @600 = Lynx |
| lynx-2 | Lynx | 40 % human bots | best @500 (27.10.) |
| lynx-3 | lynx-2@500 | same recipe, overnight run | **best @300 (since 28.10.)** |
| cfr-1, dcfr-1 | – | CFR, deep CFR | discarded |

### 9.4 Important data files

| File | Content |
|---|---|
| `data/bench/results.jsonl` | all test bench results (140 entries) |
| `data/bench/report.md` | table of all test bench results |
| `data/bench/slumbot/<name>.jsonl` | each Slumbot hand (cards, history, winnings, baseline, allin_ev) |
| `data/rl/OVERNIGHT_LOG.md` | log of both night runs |
| `data/rl/<lauf>/best.json`, `gate_<It>.json`, `eval.jsonl`, `log.jsonl` | training progress |
| `data/rl/lynx-3-bestaetigung-mensch.json`, `lynx-2-bestaetigung*.{json,txt}` | verification tests |
| `data/humans/mensch-25nl.json` | human bots with target and actual statistics |
| `data/ziele/pokerth.jsonl` | real tournaments (goal 1) |
| `data/sessions/*/compare.md` | comparison of collector against PokerTH log |

### 9.5 Gaps in this documentation

- For the 4-player table (`230753`, `231440`) no compare.md is available, there are no formal accuracy figures.
- The exact values of the early league ratings are outdated (report dated 26.10.).
- The live session from the evening of 28.10. (`20261028-222209` and following) has not yet been evaluated at the time of writing.
- The information on the bet size of the mini-bets and on leak analysis comes from ad-hoc evaluations (scratchpad scripts), not from versioned project files.
