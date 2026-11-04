# Lynx: Plan for the Next Level

Status: 29.10.2026, 01:30 AM. Basis: `DEVELOPMENT_LOG.md` (as of 28.10.), `GOALS.md`, all test bench and Slumbot data, the five real tournaments from 28/29.10, and research on methods, computing power, and costs (sources at the end).

This document answers three questions: **Where do we really stand? What will advance us manifold? What does it cost and how long will it take?**

---

## 1. Honest Assessment

### 1.1 What Lynx Can Do Today

| Measure | Value | Assessment |
|---|---|---|
| Real PokerTH tournaments (6-player, against PokerTH bots) | **5 tournaments: places 1, 3, 6, 6, 1 → 2 wins, ROI +44 %** | Chance would be 1 win out of 6. Statistically still meaningless (95 % CI: about −80 to +170 %). |
| Simulated human tables `mensch480` | +96.8 % ROI | just under level 1 (+100 %) |
| Slumbot (HU, 200 BB), adjusted | **−17.2 bb/100** [−38; +4] | clearly loses against equilibrium |
| Exploitability | Exploiter +2.3 % | no major leaks |
| Endgame HU 20 BB | +17.9 % vs Nash, +83 % vs human bots | good |

**Assessment:** solid amateur or micro-stakes regular. Winning against recreational players and the PokerTH bots, clearly inferior vs strong opponents.

### 1.2 What the Five Real Tournaments Showed Us

- **The live processing pipeline was the real opponent, not the bots.** Four of five games ran with errors that were fixed last night: suggestions arrived 10–20 s late (analysis queue), phantom suggestions after hand end, hand number was delayed by 10–20 s (previous hand progress stuck in observation), stacks read as “51000” instead of “1000”. Losses in games 3 and 4 coincided with such errors.
- **After the fixes:** average suggestion delay 0.7 s after recognition, actions vs log 88 % (previously 78 %), dealer/blinds 100 % (previously 74 %), all 5 seats automatically recognized correctly.
- **The PokerTH field is beatable.** Lynx's style (many preflop raises, pressure on passive bots) fits well. Both wins came via aggression; the two last places through large pots with overpair vs ace or a phantom jam.

### 1.3 Where Lynx Really Loses (from the Data)

1. **Postflop vs strong opponents.** Preflop is repaired by the HU preflop solver (preflop factor vs Slumbot +0.7 instead of −18.7 bb/100). The network loses afterward: too crude bet sizes (8 actions), min-bets in large pots, no real range calculations.
2. **No ICM.** Reward is chip-EV. In a 6-player SNG with 50/30/20 payouts this is measurably wrong in the bubble phase (too many coinflips at 3–4 players).
3. **No opponent adaptation.** The opponent model is only an input feature. Against static bots (PokerTH) exploiting is the biggest lever, and we don't use it.
4. **Computing power.** The training recipe is maxed out on the laptop (lynx-3 plateau at 300 iterations). More network, more opponent variety, longer runs and Deep CFR all failed at the same bottleneck: 16 GB RAM, 10 cores, USB stick.

### 1.4 What the Top Does Today (and What Is Realistic)

| Method | Result vs Slumbot | Computing effort | Transferable? |
|---|---|---|---|
| **DecisionHoldem** (2022, code open): Linear-CFR blueprint + safe depth-limited search | **+73 bb/100** | Blueprint: 48 cores, 3–4 days ≈ 4,000 core hours | Yes, heads-up. Exactly our architecture (blueprint + search), but much more compute time and a "safe" search. |
| **AlphaHoldem** (AAAI 2022): end-to-end RL, self-play vs own history | beats Slumbot and DeepStack | "one PC, 3 days" | Yes, basically our PPO way, but with a large network on raw cards instead of 57 features. |
| **GTO Wizard AI** (2026, closed) | +19.4 ± 4.1 bb/100 | unknown | As a benchmark: a real solver-bot is only +19 over Slumbot. |
| **SpinGPT** (2025, LLM + RL) | +13.4 ± 12.9 bb/100 | GPU training | No, too expensive, HU-only. |
| **Pluribus** (6-max, 2019) | – | Blueprint 8 days on 64 cores, live search 28 cores | Partly: principles yes, scale no. |

**Conclusion:** The path from “−17” to “clearly above 0” vs Slumbot is not a matter of new ideas but **compute time (thousands of core hours) plus a safe search**. 4,000 core hours on a rented 16-core server is about **11 days**. That is affordable.

For **PokerTH tournaments** (6-player SNG, 50 BB, fast blinds), Slumbot is only the benchmark for the heads-up phase. ICM, short stack play, and exploiting weak opponents matter more. Both together form the plan.

---

## 2. The Levers, by Expected Benefit per Effort

| # | Lever | Expected Effect | Effort | Cost | Confidence in Expectation |
|---|---|---|---|---|---|
| H1 | **Harden live chain** (Collector) | Goal 1 measurable at all; every capture error costs tournaments directly | 2–3 days | €0 | high (errors known and reproducible) |
| H2 | **ICM in reward and endgame** | +5 to +15 % ROI in SNGs, especially places 3→2→1 | 2–3 days | €0 | high (standard knowledge, directly measurable on test bench) |
| H3 | **Server for training and test bench** | Prerequisite for H4–H6; 3–4× throughput, no RAM limit, no stick, runs 24/7 | 1 day setup | ≈ €116/month + €88 one-time | high |
| H4 | **lynx-4: new training recipe on server** (larger net, more opponent variety, PokerTH format weights, ICM reward, 5,000–10,000 iterations, exploiter every 50 iters) | mensch480 +100 → +115…125 %; Slumbot −17 → −10 | 1 week running + 2 days build | included in server | medium (plateau may reappear; H5 is the real jump) |
| H5 | **Search as teacher (Expert Iteration)**: the HU search (and a 3-player variant) generates target policies, the net learns them; plus safe depth-limited search with value net (DecisionHoldem/ReBeL principle) | biggest jump: Slumbot −10 → ±0 to +10; endgame HU much stronger | 2–3 weeks build, 1–2 weeks compute | server + optional 20–40 GPU hours (≈ €20–40) | medium (concept proven, our implementation new; hus-2 showed how search can easily hurt) |
| H6 | **Exploitive search against opponent model** (ranges from observed behavior instead of equilibrium) | very large vs PokerTH bots and recreational players (+20–50 % ROI conceivable) | 1–2 weeks | €0 | medium to high for bots, open for humans |
| H7 | **PokerTH-specific opponent profiles** from own recordings (Collector data, not the log) | training and test bench match real field | 1 week + ongoing | €0 | high, but requires 50+ recorded tournaments |
| H8 | **Rebuilding PokerTH training bots** from open source web client code (AGPL, GitHub `narmod/pokerth-web-client`) | perfect sparring partners for goal 1 (bot phase) | 3–5 days | €0 | high, **needs your decision** (section 5) |
| H9 | **Second external benchmark**: GTO Wizard benchmark (public HUNL API with AIVAT variance reduction) | more reliable numbers with 10× fewer hands | 1–2 days | unknown (probably free) | **needs your approval** (external service) |
| H10 | **Humans on pokerth.net** (ranking games) | the actual goal 1 | only playing time | €0 | – |

Not in the plan due to mismatch of effort and benefit: LLM-based bots (SpinGPT approach), Deep CFR on laptop, further style parameter tuning, rollout search level 1.

---

## 3. Phase Plan

### Phase 0: This Week (29.10.–2.11.), €0

Goal: measurability and cheap, sure gains.

1. **Harden Collector (H1)**
   - Hand number OCR: new hand change detection (board empty, dealer moves) included; plus assignment to export by order and cards, so `compare` also checks derived hands.
   - Checks for wrong seat, start stack timing, “$” read as “5” in OCR itself (not just in live filter).
   - Systematic checks of all four suits and table sizes 2–10 against images.
   - Overlay-resistant capture (Windows.Graphics.Capture) only if it disturbs playing.
   - Metrics: actions ≥ 95 %, hands assigned ≥ 95 % against every new log.
2. **PokerTH comparison search vs net** (hu480, mensch480) finally finish computing when not playing. Decides if `hus` becomes live standard.
3. **ICM (H2)**: Malmuth-Harville ICM in `tournament.py`, reward optionally ΔICM instead of ΔChips, push/fold tables with ICM, test bench set `icm240` (bubble situations). Expectation measurable on mensch480.
4. **Collect real tournaments:** every evening play 3–5 games, strictly follow suggestions. Target 20 by end of week. Every recording feeds into H7.
5. **Documentation and tests** catch up, update league report.

Result Phase 0: Live chain stable, ICM integrated, 20 real tournaments, decision on search.

### Phase 1: Server and lynx-4 (Week 2–3), ≈ 200 €

1. **Rent Hetzner AX102** (Ryzen 9 7950X3D, 16 cores/32 threads, 128 GB ECC, 2× 1.92 TB NVMe): about 104 € net / 116 € gross per month plus 79 €/88 € setup fee. Cheaper: AX42 (8 cores, 64 GB, about 68–97 €), but too small for H5. `pc.sh` already exists for Linux.
   - Project synced via rsync/git to server, laptop and USB stick only used for live sessions.
   - Nights and days: training, test bench, Slumbot run there in parallel, without memory watchdog.
2. **lynx-4 (H4)** with the proven recipe plus new ingredients:
   - Network 256×256 (or 3 layers), `widen` from lynx-3-300
   - Reward ΔICM in tournaments, chip-EV in cash games
   - Opponent pool: human-bots 40 %, self-play 30 %, exploiters every 50 iterations, random-style bots 10 %, from Phase 2 PokerTH profiles
   - Table weights in PokerTH format (6-player 50 BB, blinds every 9 hands) plus HU/3-player for endgame
   - 5,000–10,000 iterations (Laptop: 7 s/iteration → Server approx. 2–3 s/iteration with 32 threads, thus 1–2 days per 5,000 iterations)
   - Gates as before (own seeds, one-time confirmation)
3. **Slumbot 20,000 hands** for lynx-4 (cleaned), so that Stage 1 of Goal 3 is clearly measurable.
4. Optional **GTO Wizard Benchmark (H9)** integration if approved.

Result Phase 1: lynx-4 as new standard or proof that the recipe is really exhausted (then H5 all the more important).

### Phase 2: Search as core (Week 3–6), ≈ 120 €/month server + ≈ 30 € GPU

1. **Secure depth-limited heads-up search** (H5):
   - Value network instead of playing out to showdown (input: public state + both ranges; output: value per combination). Training data generated by existing CFR+ search on the server (millions of solved subgames).
   - More bet sizes (Flop 0.33/0.5/0.75/1.25, Turn/River 0.33/0.66/1.0/1.5/2.0 + All-in), 1,000+ iterations per decision on server or 300 live.
   - Flop included in the search (previously only Preflop, Turn, River).
   - The core is already there (`husearch.py`, numba, exact blockers). New are value network, flop tree, and the safety condition (not underestimating opponent range, keyword “safe subgame solving” from DecisionHoldem).
2. **3-player search**: CFR over 3 ranges is still computable (1326³ too large → 169-class abstraction preflop, 1326 only for two active players postflop). Covers bubble and end phase where SNGs are decided.
3. **Expert Iteration**: Network learns the search policy (behavior cloning on search decisions) and then plays accordingly, also 6-handed, where search falls short. This is the approach by which AlphaZero-like systems turn search into lasting strength.
4. GPU only for value network training (rented RTX 4090, ≈ $0.35–0.70/h, 20–40 hours).

Result Phase 2: Slumbot goal Stage 2 (> 0) realistic, endgame significantly stronger, network learns along.

### Phase 3: PokerTH specialization (Week 6–10), server costs ongoing

1. **Opponent profiles from 50+ own recordings (H7)**: one profile per PokerTH bot name (VPIP, PFR, C-Bet, fold to bet per street, showdown tendency) from collector data. From this, training opponents and a test set `pokerth-bots480`.
2. **Exploitative search (H6)**: search calculates with range predicted by opponent model instead of equilibrium. Against static bots this is the biggest leverage. Safety: mixture of equilibrium and exploitation depending on confidence (observed hands).
3. **Reconstruction of training bots (H8)** if approved: exact copies as training opponents from open source code. Then expected ROI against PokerTH bot field can be measured directly in simulator with thousands of tournaments instead of five.
4. **Humans (H10)**: ranking games on pokerth.net with leaderboard, every tournament recorded. From here Goal 1 really counts.

Result Phase 3: Goal 1 Stage 1 (50 tournaments, ROI > 0) achievable, Stage 2 (200 tournaments, ROI > +20 %) within reach.

---

## 4. Costs and duration at a glance

| Item | Amount | Note |
|---|---|---|
| Hetzner AX102, 3 months | ≈ 350 € gross | 116 €/month, cancellable monthly |
| Setup | ≈ 88 € one-time | varies by country site 44–88 € |
| GPU hours (value network) | ≈ 20–40 € | only Phase 2, Vast.ai/RunPod, RTX 4090 |
| **Total for 3 months** | **≈ 450–500 €** | |
| Zero cost variant | 0 € | all on laptop: Phase 1–2 take 3–4× longer (nights), H5 practically not feasible, deep variants omitted |

**Savings variant (decision 29.10., desired: maximum at minimal budget).** Plan needs core hours in bursts, no continuous server:

| Stage | What | Cost | Sufficient for |
|---|---|---|---|
| 0 | Laptop at night, new ThinkPad (4 cores, 16 GB), existing Hetzner VPS (4 vCPU, 8 GB), Kaggle (30 GPU-h/week free) for value network | 0 € | Phase 0, Phase 1 approx. 2× slower, value network training |
| 1 | Cloud by the hour (Hetzner CCX/CPX, Vast.ai-CPU) only for computing bursts | ≈ 10–30 € per burst | Phase 2: 4,000 core hours ≈ 15–40 € |
| 2 | Hetzner server marketplace (used dedicated, 64 GB, often no setup) | ≈ 35–65 €/month | everything 24/7, only if Stage 0 is insufficient |
| 3 | AX102 | 116 €/month + 88 € | only for permanent parallel training + test bench + Slumbot |

Chosen path: Phase 0 and 1 at Stage 0, Phase 2 at Stage 1, Stage 2 only if needed. **Budget: 0 € for 2–3 weeks, then about 30–60 € total.** Required: access to ThinkPad and VPS, a Kaggle account. Hetzner raised prices twice in 2026 and CX series sometimes unavailable; check prices before ordering.
| Alternative purchase | 1,500–2,500 € | used workstation (16 cores, 64–128 GB, RTX 3090/4090). Worth it compared to rental only after 15–20 months. |

**Your time (the real bottleneck for Goal 1):** a 6-player SNG takes 10–20 minutes. 50 tournaments ≈ 12–15 hours, 200 tournaments ≈ 50–60 hours playtime. Without this time there is no reliable Goal 1, no matter how strong Lynx becomes.

**My time:** Phase 0 ≈ 5 workdays, Phase 1 ≈ 3 days build + compute time, Phase 2 ≈ 15 days, Phase 3 ≈ 10 days. Total about 10 weeks until end of Phase 3, barring interruptions.

---

## 5. Decisions I need from you

1. **Server yes/no?** Recommendation: yes, AX102, from Phase 1. Without server plan stays at Phase 0 plus slow lynx-4.
2. **Rebuild PokerTH training bots from open source code (H8)?** This is not DOM, network, or log access, but public AGPL code. It does not violate any of our rules, but you defined Slumbot consciously as pure benchmark, and Lynx should become generally strong. My suggestion: rebuild as **one** opponent type in the pool (like human bots), not as sole training target, and as own test set.
3. **GTO Wizard Benchmark (H9)?** External service, HU-only, AIVAT variance reduction. Only as second benchmark besides Slumbot. Your approval needed.
4. **Ranking games against humans (H10)** from when? Suggestion: as soon as 20 bot tournaments with stable live chain are through.

---

## 6. Expectation in numbers (honest, not promised)

| Measure | today | after Phase 1 | after Phase 2 | after Phase 3 |
|---|---|---|---|---|
| human480 (ROI) | +97 % | +110–120 % | +120–130 % | +130 % (significantly higher against PokerTH profiles) |
| Slumbot clean (bb/100) | −17 | −10 ± 5 | **0 to +10** | unchanged (not a goal) |
| Endgame nash240 | +18 % | +20 % | +30 % | +30 % |
| Real tournaments ROI | +44 % @5 | 20 tournaments measured | 50 tournaments, ROI > 0 (Stage 1) | 100+ tournaments, toward +20 % |
| Suggested latency live | 0.7–1 s | 0.7 s | 1–2 s with search (server search not needed, numba suffices) | same |

"Many times better" in poker terms means: the gap to an equilibrium player (Slumbot) should shift from −17 to above 0, and the ROI against the PokerTH field should visibly and reliably increase. This is realistic with this plan. A jump to the level of Pluribus or GTO Wizard AI (6-max equilibrium, thousands of core hours per blueprint and 28 cores live) is possible with a server, but a project for months, not weeks.

---

## 7. Risks

| Risk | Countermeasure |
|---|---|
| Plateau despite new ingredients (like lynx-3) | Gates with own seeds, early termination, measure the order of ingredients individually (ablation) |
| Search hurts instead of helps (like hus-2, rollout search) | never test live standard without paired win; safety condition in the search; mix with the network |
| Human bots and PokerTH bots behave differently from real humans | start ranking games early, profiles from real recordings |
| Detection errors cost tournaments | H1 first; check each session against the log, key metrics per evening |
| Server costs run on, benefits do not materialize | cancellable monthly; interim balance after phase 1 |
| Laptop and stick (standby, RAM) | only live on the laptop now; everything heavy on the server |

---

## 7a. Clarification of goals 29.10. (Jakob): Humans, not platform bots

Lynx should play really good poker overall, against all possible opponents and especially against humans. The PokerTH bots are a practice field and a measurement point, not a goal. This implies for the plan:

- **Put on hold:** H8 (rebuild of the PokerTH bots) and bot specialization from phase 3. They would optimize Lynx for a field that ultimately does not matter.
- **Core remains H5, search as teacher:** Near-equilibrium is the basis with which one does not lose against unknown, good opponents. Sequence: value network for HU search, flop into the tree, more bet sizes, 3-player search, then expert iteration (network learns search decisions and transfers them to 6-handed).
- **H6 newly oriented towards humans:** Opponent model from human hand histories (HandHQ/PHH permitted) instead of from bot behavior; the human bots of the test platform (mensch480) become finer (types, stack and position dependencies); the search mixes equilibrium and exploitation depending on trust in the model. Against casual players, this is the lever; against strong players, protection.
- **Measures instead of bot wins:** Slumbot (adjusted), Pluribus alignment, GTO Wizard benchmark (H9, requires release), and real games against humans (H10, pokerth.net ranking) as target panels. PokerTH bot tournaments remain as cheap preliminary tests, but do not count as success.
- **Training opponents:** more human bots and self-play, fewer style bots; table weights still broad (2 to 10 players), not confined to the PokerTH format.

## 7b. Planned 30.10. (Jakob): H11 Human range model from HandHQ showdowns

**Why:** The search stands or falls with the opponent model. Today it has three priors: heuristic, "opponent plays like our network" (good against PokerTH bots, hu480 −2.5) and heads-up equilibrium (for Slumbot). For humans, the fourth is missing: **how do real average players play with which cards**. Exactly that is in HandHQ, but only in hands that went to showdown: there both hands and all actions are known. The raw data are local (`data/external/phh-dataset/data/handhq`, 5.0 GB, 5,989 `.phhs` files, 5.72 million hands 25NL, PokerStars and Party 2009). Permitted source (PHH/HandHQ), no own recordings, no persons (obfuscated player names).

**What is built (2–3 days, €0, laptop compute time only):**

1. **Extraction `humans.py` → `human_actions`:** for each showdown hand and each showing player all their decisions as rows (public state: street, position, number of players, pot, to_call, stack/pot, raises so far, board texture; action including size; hole cards as class and combination). Preliminary study 30.10. (sample 40 of 5,989 files, 39,891 hands): 21.7% of hands have shown cards, 1.5 shown players per such hand, 6 decisions per shown player → extrapolated **1.24 million showdown hands and 7.5 million decisions with known cards** (preflop 2.2 million, flop 2.1 million, turn 1.8 million, river 1.5 million). That is 80 times the Pluribus dataset. Added known data traps (missing winnings, "????", antes) from 4.4.
2. **Reveal and capture bias** (finding from the first extraction 30.10.: in the data there is **not a single fold**, because those who folded show no cards; the model thus provides P(action | hand, continued play), fold rates must come from unbiased frequencies, and flop and turn ranges underestimate given up bluffs, river ranges are almost unbiased): Showdown hands are not all hands (those who fold early do not show). Preflop ranges therefore come from unbiased statistics of all hands (VPIP, PFR, 3-bet by position, already in `handhq-25nl.json`), from showdowns only the **conditional** postflop ranges: "with which hands does an average player bet, call, raise on this street in this situation." This is exactly what the search needs from flop onward.
3. **Model:** a small human policy network P(action | state, hand class) with the same interface as the blueprint (features `features.py`, action grid `from_action`). It then fits without further modification in `bpranges.py` as mode **`ranges=human`** (opponent from the human model, own range from blueprint or equilibrium). Also trainable separately by player types (Nit, Station, Maniac …), because `handhq-25nl.json` assigns each player a type; the OpponentTracker (feat-3) selects the type live.
4. **Acceptance in three stages:** (a) prediction quality on held-out showdowns (log-likelihood of shown cards under the predicted range, compared to heuristic and blueprint as references); (b) hu480 and mensch480 with `ranges=human` against `pre,flop`; (c) GTO Wizard and pokerth.net against humans.
5. **Byproducts:** a genuine **human bot** (the policy network plays itself) as test platform and training opponent instead of handcrafted style bots; and a dataset to check whether Lynx's mini-bets against humans really work (V1 question).

**Sequence:** after the ongoing measurements (F, tranche 3, slumbot hus-5) and before the next value network stage (turn). Reasoning: the value network makes search faster, the human model makes it better against the actual target.

## 8. Next concrete steps (order)

1. Tonight: complete test suite, supplement documentation by evening, backup.
2. Tomorrow: Collector fixes H1 (export assignment, checks, OCR), then finish PokerTH search vs network comparison.
3. Day after tomorrow: build and measure ICM.
4. Evening: collect tournaments, 3–5 per evening.
5. After your decision on 5.1: order server, migrate project, start lynx-4.
6. **(planned 30.10.)** H11 human range model from HandHQ showdowns (7b), then turn data and turn network.

---

## Sources

- Hetzner AX102: https://www.hetzner.com/dedicated-rootserver/ax102 (€104 net/€116 gross monthly, setup €79/88, page status; price increases 2026 according to https://www.deskmodder.de/blog/?p=210160)
- GPU prices 2026: https://www.hostinger.com/tutorials/?p=158956, https://www.spheron.network/blog/gpu-cloud-pricing-comparison-runpod-vs-vastai-2026/
- DecisionHoldem (code open, +730 mbb/h vs Slumbot, 4000 core hours): https://arxiv.org/abs/2201.11580, https://github.com/AI-Decision/DecisionHoldem
- AlphaHoldem (one PC, three days): https://pi.cs.tsinghua.edu.cn/lab/people/jlxing/zh/publication/featured02-aaai-2022/
- GTO Wizard benchmark (public HUNL API, AIVAT, +19.4 vs Slumbot): https://arxiv.org/abs/2603.23660
- SpinGPT (+13.4 ± 12.9 vs Slumbot): https://arxiv.org/pdf/2509.22387v2
- PokerTH web client (AGPL, training mode, ranking games): https://webclient.pokerth.net/how-to-play, https://awesome.ecosyste.ms/projects/github.com%2Fnarmod%2Fpokerth-web-client
