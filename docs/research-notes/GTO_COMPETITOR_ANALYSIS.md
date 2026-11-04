# Analysis: Who is strong against GTO Wizard AI, how did they do it, and what does that mean for Lynx

As of 10/29/2026, 9:00 PM. Sources at the end. Numbers from papers and the public leaderboard; none of these have been independently verified unless otherwise noted.

## 1. The leaderboard today (HUNL 200 BB, AIVAT in bb/100, sorted by lower bound of the interval)

| Bot | Who | Hands | AIVAT | What is known |
|---|---|---|---|---|
| Competitor | Individual | 200,002 | −2.96 ± 0.46 | nothing public |
| MikkaMakka | “Independent Research Team” | 179,028 | −3.18 ± 0.53 | nothing public |
| Bitcrumbs | Individual | 52,005 | −3.08 ± 0.91 | nothing public |
| Trainer / Roman_SL | SL / Individual | 297k / 238k | −4.90 / −5.15 | presumably the same team, two versions |
| Marvel | MIT | 124,029 | −4.57 ± 0.79 | at the start of the leaderboard (April), −14.0 ± 4.7 after 5,090 hands; **+9.4 bb/100 in six months** |
| No Mercy v2 / No Mercy | Individual | 50k / 25k | −5.11 / −4.89 | two versions, no measurable improvement |
| Kevin Rabichow | Human (High-Stakes HU Pro) | 2,958 | −3.91 ± 3.17 | only human; interval ±6 |
| GPT-6 (Low Reasoning) | OpenAI | 10,000 | −5.40 ± 2.41 | pure language model, better than the XHigh variant (−8.8) |
| VDPAI.AG2, MagicMike (University of Warsaw), The Speckled Bluff, Edpoker, tangtang, evaBot … | | 45k–270k | −7.7 to −12.8 | the field |
| PokerSkill (Paper, not on the list) | University team | ? | −5.7 ± 2.1 | GPT-5.5 + handwritten expert rule library, no solver, no training |

No one is positive. The top is at −3, represented by three anonymous individuals or small teams, no large lab.
This means two things: the ceiling is reachable for individual projects, and no one has cracked GTO Wizard AI.

## 2. What the strong systems have done

| System (Year) | Core | Computational Effort | Result against Slumbot | Lesson |
|---|---|---|---|---|
| **Slumbot** (2017/18) | CFR on abstracted game, finished strategy as a table, no real-time computation | ≈ 250,000 core hours, 2 TB RAM | – (baseline) | strong but exploitable via action translation (off-tree sizes) |
| **DeepStack** (2017) | Counterfactual value networks + continuous re-solving (search to street end, network on showdown) | 10 million river, 1 million turn/flop situations; network inputs bucketed | Reimplementation **loses** to Slumbot (Supremus paper) | right idea, execution is critical |
| **Libratus** (2017) | Blueprint (abstracted CFR) + nested safe subgame solving + nightly self-improvement | > 3 million core hours | – | safe re-solving, incorporate off-tree actions into the tree |
| **Supremus** (2020) | DeepStack recipe with five improvements: faster converging CFR, GPU-CFR, more iterations, **larger search space (more bet sizes)**, **much more training data** | not specified (GPU) | “extremely large lead” | each of the five components measurably contributes individually |
| **ReBeL** (2020) | Value and policy networks on "public belief states" (board + both ranges), data from self-play with CFR-D, network as MLP with GELU/LayerNorm, Huber loss; 9 bet sizes | up to 128 machines × 8 GPUs for data generation | **+4.5 ± 0.5 bb/100**; versus top human Dong Kim +16.5 ± 6.9 | **Value network on random ranges “learns nothing valuable”**—the training distribution must come from real (self-)play; policy net as warm start saves iterations |
| **DecisionHoldem** (2022, open) | Libratus-like blueprint (169/50,000/5,000/1,000 buckets; F, C, ½P, P, 2P, 4P, All-in), linear CFR; real-time: **6,000 iterations preflop/flop, 10,000 turn/river**, safe depth-limited solving with multiple opponent strategies at leaves | ≈ 4,000 core hours (48 cores, 3–4 days) | **+73 raw / +56 adjusted bb/100** over 20,000 hands | with 4,000 core hours one clearly beats Slumbot; still not a top score against GTO Wizard (Slumbot is too easily exploitable) |
| **AlphaHoldem** (2022) | **Pure end-to-end RL** (PPO with Trinal Clip, pseudo-Siamese network, K-best self-play pool), no search | 3 days on 8 GPUs + 64 cores | **+11.2 bb/100**; 2.9 ms per decision | this is our current level (lynx-4); its ceiling is about +10 against Slumbot |
| **GTO Wizard AI / Ruse** (2022–) | Self-play RL over “hundreds of millions of hands,” learned expectations (“intuition”), **one street at a time**, arbitrary bet sizes, ≈ 3 s per street | not disclosed, Mila founder | **+19.4 ± 4.1 bb/100** over 150,000 hands | ReBeL principle, commercially fully exploited |
| **PokerSkill** (2026) | Language model selects from actions specified by a handwritten expert rule library | only API costs | better than Slumbot (indirectly); **−5.7 versus GTO Wizard** | without solver and training at −6: rule knowledge is valuable, but the ceiling is close |

## 3. The key insights for us

1. **Beating Slumbot is not the same as being good against GTO Wizard.** DecisionHoldem wins +73 against Slumbot and would still barely rank at the top of the leaderboard. Slumbot's weaknesses are off-tree sizes and a coarse abstraction; GTO Wizard has neither. About +10 against Slumbot, the number means little more. **Our benchmark will be AIVAT against GTO Wizard; Slumbot is only a preliminary step.**
2. **Everyone at the top computes in real time with learned values or enormous blueprints.** Pure end-to-end RL (AlphaHoldem, our lynx-4) hits its ceiling at +10 versus Slumbot. Our approach via search with value network (milestone 3) is the right one; lynx-4 remains blueprint and later distillation target.
3. **Training distribution of the value network is the most common mistake.** ReBeL: value network on randomly sampled ranges "learns nothing valuable"; DeepStack only succeeded with structured-random ranges and 10 million situations. Implication for `valuedata.py`: **at least half the situations must come from real search play** (ranges that our search actually reaches at leaves, logged from testbed and self-play runs), the other half structured-random for robustness. This is the most important change to the plan.
4. **Iterations and warm start.** DecisionHoldem runs 6,000–10,000 iterations per decision, ReBeL uses a few hundred because a policy net initializes the search. We are at 40–300 without warm start. **Blueprint warm start** (CFR start strategy from lynx-4 instead of uniform, linearly weighted) is cheap and saves iterations or improves accuracy.
5. **Search space.** Supremus cites “larger search space” as one of the five components; GTO Wizard allows any size; ReBeL 9 actions; DecisionHoldem 5 sizes plus all-in. We: 1–4. As soon as the value network keeps the trees small, `wide` will become standard and gain a third raise size.
6. **Off-tree actions belong in the tree** (Libratus, ReBeL, DecisionHoldem): we already do this (the actual bet size is inserted as a branch). Keep it.
7. **Safety.** ReBeL shows that safe search without additional constraints arises when playing the strategy of a random (late) iteration instead of the last; we use the weighted average strategy, which is practically equivalent. DecisionHoldem places multiple opponent strategies at leaves; the value network handles this implicitly via range input.
8. **Iteration pays off.** MIT Marvel improved from −14 to −4.6 in six months. The leaderboard is a learning tool, not a final verdict.

## 4. What we can do differently or better

- **Exact instead of bucketed.** DeepStack and Supremus provide the network with bucketed ranges; we calculate all 1,326 combinations with exact blockers, and our trees are small enough for that. This is an accuracy advantage precisely in situations where bots typically misvalue blockers.
- **Opponent adaptation.** None of the GTO systems exploit opponents; against humans, this accounts for half the winnings. Our opponent model and search are built for this (H6). Against GTO Wizard, it brings no benefit; against humans, it brings everything.
- **Multiplayer and tournament.** GTO Wizard measures only heads-up 200 BB. Our target is humans at full tables with tournament stacks; here ICM and 3-player search matter, which nobody needs on the leaderboard.
- **Measurement discipline from the start.** Paired benchmarks, control variables against Slumbot, AIVAT at GTO Wizard: we always know what a change brings. This is the actual lever that allowed Marvel to achieve 10 bb/100.
- **Budget.** ReBeL: 1,000 GPUs. DecisionHoldem: 4,000 core hours. We: a laptop, a few euros on Hetzner and Kaggle. Therefore DeepStack order (river first, small exact trees), no blueprint CFR with billions of iterations.

## 5. Changes to the plan (from 30.10.)

1. `valuedata.py`: Mode "from game": log hand situations (board, pot, stack, both ranges) during benchmark and self-play runs of the search (`data/valuenet/live-ranges-*.npz`) and solve exactly. Target mix 50% gameplay, 50% structured-random. Measure learning curve separately by source.
2. Blueprint warmstart in `husearch.solve`: starting strategy from lynx-4 probabilities per combination (network evaluated once per node) instead of uniform; measure iterations at equal exploitability.
3. After the river network: preset `wide` as default, third raise size, iterations up.
4. First GTO Wizard measurement immediately after release with 500 hands (remains in list noise), then 2,000–5,000 hands per version; only stable versions at 20,000+ hands.
5. Slumbot from now only as a preliminary stage (5,000 hands per version), goal there "> 0 secured", no more.
6. Goals: GTO Wizard −20 (Slumbot level) with river network, −10 with turn/flop network and warmstart, −5 with wider search space and self-play data.

## Sources

- GTO Wizard Benchmark (Provost, Ilenic, Solinas, Beardsell), arXiv 2603.23660; leaderboard https://benchmark.gtowizard.com (accessed 29.10.2026); blog "GTO Wizard AI Explained" (2023), "Crushing a Top HUNL Poker Bot"
- ReBeL: Brown, Bakhtin, Lerer, Gong, "Combining Deep Reinforcement Learning and Search", arXiv 2007.13544
- Supremus: Zarick, Pellegrino, Brown, Banister, "Unlocking the Potential of Deep Counterfactual Value Networks", arXiv 2007.10442
- DecisionHoldem: Zhou, Bai, Zhang, Duan, Huang, arXiv 2201.11580 (v2 2024), code github.com/AI-Decision/DecisionHoldem
- AlphaHoldem: Zhao, Yan, Li, Li, Xing, AAAI 2022
- DeepStack: Moravčík et al., Science 2017, arXiv 1701.01724; Depth-Limited Solving: Brown, Sandholm, Amos, arXiv 1805.08195
- PokerSkill, arXiv 2605.30094; SpinGPT, arXiv 2509.22387 (13.4 ± 12.9 bb/100 against Slumbot, LLM)
- PokerNews / PokerListings on leaderboard (April 2026): Marvel −14.0 ± 4.7 at start
