# Night Log 26./27.10.2026

Goal: Maximize and autonomize the bot. Hourly checks (Cron :23).

## 00:55 Start
- Deep CFR (dcfr-1) stopped at iteration 37 (drop at iteration 30: mix96 -16%, fixed48 -18%); state saved at iteration 30.
- Night run `night.sh`: pros-r2 = Start pros-r1@300 (feat-2, ranges), anchor pros-r1@0 (Pluribus imitator), leash 0.3,
  512 tournaments/iteration, **random formats** (2-10 players, 20-200 BB, blind tempo 5-20 hands), 30% random style bots,
  exploiter every 50 iterations, test bench every 50 iterations. Sections up to 300/600/900/1200/1500, each with an entrance exam
  against the current champion (pros-ppo2, or pros-r2 as soon as one passes).
- Initial status (mix96 Δ rock / fixed48 Δ rock): pros-2@300 +22.8 / +12.9; pros-r1@300 +23.0 / +25.0.

## 01:35 Check 1
- Running: pros-r2 iteration 199/300, ~7 s/iteration, no errors, RAM free 3.4 GB.
- Test bench Δ rock (mix96 / fixed48): Iteration 50 +16.7 / +8.5 · Iteration 100 +17.3 / +8.7 · Iteration 150 +10.4 / +14.4 · Iteration 200 +15.7 / +14.4.
  Slightly below pros-r1@300 (+23 / +25) – expected, since training is now distributed across all formats; the 6-player test sets
  measure only part of this. The format test bench is more meaningful. Exploiter: +22.5 / +1.2 / +7.9 % (24 schemas, imprecise).
- Decision: continue running, no changes.

## Check 2 – 27.10. 02:35
- Section up to 300 completed (Exit 0), gate pros-r2@300 against pros-ppo2 not passed (no retry). Section up to 600 is running, iteration 450, no tracebacks, RAM free 3.0 GB.
- Test bench mix96/fixed48 (Δ rock): @250 +17.4/+17.7 · @300 +16.6/+18.1 · @350 +20.3/+19.4 · @400 +16.7/+16.2 · @450 +14.8/+9.8. Pluribus stable at 81%.
- Decision: no clear plateau or downward trend over multiple test benches (variation within noise, CI ±12). Continue running; if further decline by iteration 550, consider reducing learning rate.

## 02:41 – Note
- development tooling terminated the night.sh wrapper (Task bhzr6skj8) due to memory pressure (RAM free ~2.7 GB). The training process itself continues (iteration 473, writes progress) and will end normally at 600 including gate.
- Subsequent sections 900+ will not start automatically; night.sh restart (resuming from current state) will only occur at next check once process ends and sufficient RAM is free.

## Check 3 – 27.10. 03:35–03:50
- night.sh continued running after all (wrapper unaffected). Section 600 completed, gate pros-r2@600 against pros-ppo2: −5.8 % [−15.9; +4.3] → not passed.
- Test bench mix96/fixed48 Δ rock: @350 +20.3/+19.4 · @450 +14.8/+9.8 · @500 +15.1/+16.9 · @550 +16.5/+9.0 · @600 +12.0/+12.3 · @650 +9.5/+11.2 → clearly falling over 4+ test benches.
- Decision: pros-r2 aborted around iteration ~690 (state retained). New run **pros-r3** starting from pros-r2@350 (best test bench), learning rate 3e-4 → 1.5e-4, leash 0.3 → 0.5 (anchor pros-r1:0), otherwise unchanged. Sections 200/400/600 with gate (night2.sh).
- Code: new option `train rl --lr` (also applies when resuming; optimizer learning rate overwritten after loading). Tests 132 green.

## 04:36 – Intermediate Check (Task Note Memory pressure)
- development tooling reported night2.sh wrapper terminated (memory pressure, RAM free 2.5 GB); processes continue (night2.sh + training active, iteration 249).
- **Gate pros-r3@200 against pros-ppo2 PASSED: +13.3 % [+3.0; +23.6]** → League 'pros-r3-200', new title defender for section 400.
- Test bench mix96/fixed48 Δ rock: @50 +17.3/+13.5 · @100 +19.2/+12.5 · @150 +16.7/+8.5 · @200 +12.3/+4.0 · @250 +18.0/+1.5. Contradiction: direct comparison clearly better, Δ rock (6-set, rock-heavy) inconsistent, fixed48 very noisy (CI ±17). Continue running, format test bench at end decides.

## 04:37 – Check 4
- pros-r3 running (night2.sh active, iteration ~250, test bench @250 running), no tracebacks, RAM free 2.6 GB. State same as 04:36, no changes.

## 05:37 – Check 5
- pros-r3 iteration 499, section up to 600 running (title defender pros-r3-200), no tracebacks, RAM free 2.4 GB.
- Gate pros-r3@400 against pros-r3-200: +1.9 % [−6.1; +9.9] → not passed.
- Test bench mix96/fixed48 Δ rock: @300 +8.9/−0.8 · @350 +15.7/+1.5 · @400 +17.8/+10.4 · @450 +19.8/+10.4 · @500 +13.6/+11.2 → plateau within noise, no trend. No more intervention: run ends normally at 600, then format test bench + Deep CFR.

## 06:37 – Check 6: Night run finished
- pros-r3 finished at 06:03 (iteration 600). Gate pros-r3@600 against pros-r3-200: −4.9 % [−12.0; +2.2] → not passed. League leader remains **pros-r3-200** (only successful night candidate).
- Test bench @550 +14.2/+7.1 · @600 +15.9/+14.2 (mix96/fixed48 Δ rock).
- Started: morning.sh – format test bench (formats,fixed48,mix96) for rock, pros-2@300, pros-r1@300, pros-r2@350, pros-r3@200 (gate winner), pros-r3@450 (best mix96 of series); then continue Deep CFR dcfr-1. Log: data/rl/morning.txt.

## 06:48 – Format test bench finished (Δ rock, paired)
| Bot | hu48 | 3max48 | 10max48 | turbo48 | deep48 | pokerth48 | Ø Formats | mix96 | fixed48 |
|---|---|---|---|---|---|---|---|---|---|
| pros-r2@350 | +50.0 | +17.1 | +30.7 | +4.1 | +24.2 | +9.4 | **+22.6** | +20.3 | +19.4 |
| pros-r3@200 (League pros-r3-200) | +50.0 | +13.6 | +19.3 | −1.2 | +26.9 | +19.4 | +21.3 | +12.3 | +4.0 |
| pros-r1@300 | +41.7 | +13.1 | +13.4 | +12.1 | +23.5 | **+20.4** | +20.7 | **+23.0** | **+25.0** |
| pros-2@300 | +54.2 | +29.2 | +12.4 | −7.9 | +29.6 | +3.8 | +20.2 | +22.8 | +12.9 |
| pros-r3@450 | +41.7 | +16.1 | +10.4 | +8.1 | +18.3 | +8.5 | +17.2 | +19.8 | +10.4 |
- Summary: all candidates are tied within noise (CI per format ±15–20). The multi-format training overnight yielded no measurable gain against rock; in direct duel pros-r3-200 clearly beats pros-ppo2 (+13.3%). For PokerTH (pokerth48) pros-r1@300 and pros-r3@200 lead.
- Deep CFR dcfr-1 has been running since 06:44 (iteration 43, loss 2.38). (the operator code message "terminated due to memory" referred only to wrapper, processes running.)

## 07:37–09:40 – Stick failure
- 07:10:35 Windows event "disk 11: controller error on Harddisk1" → Stick (Intenso cMobile Line) failed during run, not unplugged. Only recognized again after switching to another port (~09:40), volume "Healthy".
- Deep CFR dcfr-1 reached iteration 62, last checkpoint ckpt_000060 (07:06). League file players.json intact (12 players), protocol and logs readable.
- Hourly check at 08:37 deleted.

# Night 27./28.10.2026 – lynx-3
- 20:55 Start train_lynx3.sh: lynx-3 from lynx-2@500 (Lynx 2), 40% human bots, sections 300/600/900/1200/1500, gate 600 fresh tournaments against league leader, test bench human480+precise paired against lynx-2@500.
- Parallel: Slumbot lynx-2@500, 20,000 hands, 4 sessions. Hourly check (Cron 75da942c) restarts upon failure.
- 21:30 Memory monitor terminated Slumbot (at 3,000 hands: −22.2 bb/100 [−60; +16]); training continues (iteration 142). Slumbot will resume after training completion (Cron new: 21:27).

## 22:33 Check
- Training lynx-3 running (iteration 399, section up to 600), no errors. Free RAM 1.9 GB → bench compare omitted to avoid compromising training.
- Gate @300 against lynx-2: +4.5 % [+0.3; +8.6] **passed** → lynx-3-300 in league. best.json: @200 vs lynx-2@500 average +0.74 (human480 +3.7 [−1.2; 8.6]).
- Slumbot: waiting for NIGHT RUN COMPLETE (3,000/20,000 hands).

## 23:33 Check
- Training lynx-3 reached iteration 600; entrance exam @600 against lynx-3-300 currently running (600 schemas). No tracebacks. Free RAM 3.3 GB; bench compare omitted (gate running).
- best.json now @500 vs lynx-2@500, average +1.76.
- Slumbot: waiting (3,000/20,000).
- best@500 details: human480 +9.6 [4.8; 14.4], mix960 +0.9, pokerth480 +0.8, hu480 −1.5, 10max240 −1.0.

## 00:33 Check
- Gate @600 against lynx-3-300: −3.7% [−8.2; +0.9] failed (title defender remains lynx-3-300).
- Training running, iteration 827 in section up to 900, no traceback. Free RAM 1.3 GB → compare skipped.
- best.json unchanged @500 (Mean +1.76 vs lynx-2@500). Slumbot waiting (3000/20000).

## 00:45 Plan for the rest of the night (predefined)
- train_lynx3.sh continues until 1500 (Gates at 900/1200/1500).
- Then morgen_lynx3.sh: Candidate = last lynx-3 version with passed entrance exam.
  1. Human tables vs lynx-2@500, 600 fresh schemas, seed "lynx3-28-10" (one-time).
  2. League gate vs lynx-2, 600 schemas, seed 2810 (one-time).
  3. Slumbot lynx-2@500 up to 20000 hands, then candidate 10000 hands (6 workers, sequential).
- Live standard will only be switched when both confirmations are passed.

## 01:35 Check
- Gate @900 against lynx-3-300: +0.1% [−4.4; +4.6] failed.
- Training running, iteration 1032 (section up to 1200), no traceback. Free RAM 1.5 GB.
- best.json now @1000, Mean +2.22 vs lynx-2@500: human480 +9.6 [4.5; 14.6], mix960 −0.6, pokerth480 +2.9, hu480 −2.7, 10max240 +1.9.

## 02:35 Check
- Gate @1200 against lynx-3-300: −2.5% [−7.0; +2.0] failed.
- Training running, iteration 1229 (last section up to 1500), no traceback. Free RAM 1.4 GB.
- best.json unchanged @1000 (Mean +2.22 vs lynx-2@500).

## 03:35 Check
- Training running, iteration 1446/1500, no traceback. Free RAM 1.3 GB. best.json @1000 (+2.22).
- Gate @1500 still pending; afterwards morgen_lynx3.sh starts (current candidate lynx-3@300).
## 04:35 Check (Note on C:, because D: is gone)
- USB stick POKER failed at 04:15:26: "disk 11 controller error on Harddisk1", disk reports "No Media". D:\ not readable.
- Training lynx-3 was at iteration ~1446/1500 (03:35), last checkpoint probably ckpt_001440; process ended.
- Not fixable without reconnecting (pnputil denied without admin rights). After reconnecting: ./train_lynx3.sh resumes from last checkpoint, then morgen_lynx3.sh.
- 05:35: D: still gone (No Media), waiting for reconnect.
- 06:35: D: still gone (No Media).
- 07:35: D: still gone (No Media).
- 08:35: D: still gone (No Media).
- 09:35: D: still gone (No Media).
- 10:00: Stick back. Night run was already finished at 03:58 (before failure). Gate @1500 vs lynx-3-300: +2.8% [−1.7; +7.2] failed. morgen_lynx3.sh started, candidate lynx-3@300.
- 10:07: Confirmations lynx-3@300 (predefined, one-time): Human tables vs lynx-2@500 +9.2 [4.8; 13.6] passed; league gate vs lynx-2 (seed 2810) +6.7 [2.3; 11.0] passed. Live standard switched in cli.py to lynx-3-300. Slumbot running.
- 10:35: Slumbot lynx-2@500 at 7500/20000 hands: raw −31.5 bb/100 [−56; −8], all-in EV −33.4 [−56; −11].
- 11:38: Slumbot lynx-2@500 at 15200/20000: all-in EV −23.0 bb/100 [−41; −5]. Parallel Slumbot hus-1 (search, 3000 hands). morgen_lynx3.sh running.
- 13:35: Slumbot lynx-3@300 8284/10000; hus-3 (new search) 800 hands +2.2 bb/100 [−108; +112]. Target table lynx-3-300: human480 +96.8%, exploiter +2.3%, nash240 +17.9%, short240 +83.3%. Running: PokerTH comparison search vs net (hu480 net +49.6%).

## 13:59 Night run result report lynx-3 (FINISHED TOMORROW)
- Gates: @300 vs lynx-2 +4.5 [+0.3; +8.6] passed; @600 −3.7, @900 +0.1, @1200 −2.5, @1500 +2.8 (each vs lynx-3-300, failed).
- Predefined confirmations lynx-3@300: human tables +9.2 [4.8; 13.6] passed, league gate +6.7 [2.3; 11.0] passed → live standard lynx-3-300 (switched 10:07).
- Slumbot (all-in EV): lynx-2@500 20000 hands −26.3 [−42; −11]; lynx-3@300 10000 hands −23.0 [−45; −1].
- Control cronjob deleted.
