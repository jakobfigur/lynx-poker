# Analyse: Wer ist gegen GTO Wizard AI stark, wie haben sie es gemacht, was heißt das für Lynx

Stand 29.10.2026, 21:00. Quellen am Ende. Zahlen aus Papern und der öffentlichen Rangliste; nichts davon
unabhängig geprüft, sofern nicht anders vermerkt.

## 1. Die Rangliste heute (HUNL 200 BB, AIVAT in bb/100, nach Untergrenze des Intervalls sortiert)

| Bot | Wer | Hände | AIVAT | Was man weiß |
|---|---|---|---|---|
| Competitor | Einzelperson | 200 002 | −2,96 ± 0,46 | nichts Öffentliches |
| MikkaMakka | „Independent Research Team“ | 179 028 | −3,18 ± 0,53 | nichts Öffentliches |
| Bitcrumbs | Einzelperson | 52 005 | −3,08 ± 0,91 | nichts Öffentliches |
| Trainer / Roman_SL | SL / Einzelperson | 297 k / 238 k | −4,90 / −5,15 | vermutlich dasselbe Team, zwei Versionen |
| Marvel | MIT | 124 029 | −4,57 ± 0,79 | war beim Start der Rangliste (April) bei −14,0 ± 4,7 nach 5 090 Händen; **+9,4 bb/100 in sechs Monaten** |
| No Mercy v2 / No Mercy | Einzelperson | 50 k / 25 k | −5,11 / −4,89 | zwei Versionen, keine messbare Verbesserung |
| Kevin Rabichow | Mensch (High-Stakes-HU-Profi) | 2 958 | −3,91 ± 3,17 | einziger Mensch; Intervall ±6 |
| GPT-6 (Low Reasoning) | OpenAI | 10 000 | −5,40 ± 2,41 | reines Sprachmodell, besser als die XHigh-Variante (−8,8) |
| VDPAI.AG2, MagicMike (Uni Warschau), The Speckled Bluff, Edpoker, tangtang, evaBot … | | 45 k–270 k | −7,7 bis −12,8 | das Feld |
| PokerSkill (Paper, nicht auf der Liste) | Uni-Team | ? | −5,7 ± 2,1 | GPT-5.5 + handgeschriebene Experten-Regelbibliothek, kein Solver, kein Training |

Niemand ist positiv. Die Spitze liegt bei −3, dort stehen drei anonyme Einzel- oder Kleinteams, kein großes Labor.
Das heißt zweierlei: Die Decke ist für Einzelprojekte erreichbar, und niemand hat GTO Wizard AI geknackt.

## 2. Was die starken Systeme gemacht haben

| System (Jahr) | Kern | Rechenaufwand | Ergebnis gegen Slumbot | Lehre |
|---|---|---|---|---|
| **Slumbot** (2017/18) | CFR auf abstrahiertem Spiel, fertige Strategie als Tabelle, keine Echtzeit-Rechnung | ≈ 250 000 Kernstunden, 2 TB RAM | – (ist das Maßband) | stark, aber über Aktionsübersetzung (Off-Tree-Größen) ausbeutbar |
| **DeepStack** (2017) | kontrafaktische Wertnetze + kontinuierliches Neulösen (Suche bis Straßenende, Netz am Blatt) | 10 Mio. River-, je 1 Mio. Turn-/Flop-Situationen; Netz-Eingaben gebucketet | Reimplementation **verliert** gegen Slumbot (Supremus-Paper) | Idee richtig, Ausführung entscheidend |
| **Libratus** (2017) | Blueprint (abstrahiertes CFR) + verschachteltes sicheres Teilspiel-Lösen + nächtliche Selbstverbesserung | > 3 Mio. Kernstunden | – | sicheres Neulösen, Off-Tree-Aktionen in den Baum aufnehmen |
| **Supremus** (2020) | DeepStack-Rezept mit fünf Verbesserungen: schneller konvergierendes CFR, GPU-CFR, mehr Iterationen, **größerer Suchraum (mehr Einsatzgrößen)**, **viel mehr Trainingsdaten** | nicht genannt (GPU) | „extrem großer Vorsprung“ | jede der fünf Zutaten zählt einzeln messbar |
| **ReBeL** (2020) | Wert- und Politiknetz auf „öffentlichen Glaubenszuständen“ (Board + beide Ranges), Daten aus Selbstspiel mit CFR-D, Netz als MLP mit GELU/LayerNorm, Huber-Verlust; 9 Einsatzgrößen | bis zu 128 Maschinen × 8 GPUs für die Datenerzeugung | **+4,5 ± 0,5 bb/100**; gegen Top-Mensch Dong Kim +16,5 ± 6,9 | **Wertnetz auf zufälligen Ranges „lernt nichts Wertvolles“** – die Trainingsverteilung muss aus echtem (Selbst-)Spiel kommen; Politiknetz als Warmstart spart Iterationen |
| **DecisionHoldem** (2022, offen) | Libratus-artiger Blueprint (169/50 000/5 000/1 000 Buckets; F, C, ½P, P, 2P, 4P, All-in), Linear CFR; Echtzeit: **6 000 Iterationen preflop/flop, 10 000 Turn/River**, sicheres tiefenbegrenztes Lösen mit mehreren Gegnerstrategien an den Blättern | ≈ 4 000 Kernstunden (48 Kerne, 3–4 Tage) | **+73 roh / +56 bereinigt bb/100** über 20 000 Hände | mit 4 000 Kernstunden schlägt man Slumbot deutlich; gegen GTO Wizard ist das trotzdem kein Spitzenwert (Slumbot ist zu leicht ausbeutbar) |
| **AlphaHoldem** (2022) | **reines End-zu-End-RL** (PPO mit Trinal-Clip, Pseudo-Siamese-Netz, K-Best-Selbstspiel-Pool), keine Suche | 3 Tage auf 8 GPUs + 64 Kernen | **+11,2 bb/100**; 2,9 ms je Entscheidung | das ist unsere heutige Klasse (lynx-4); ihre Decke liegt bei etwa +10 gegen Slumbot |
| **GTO Wizard AI / Ruse** (2022–) | Selbstspiel-RL über „hunderte Millionen Hände“, gelernte Erwartungswerte („Intuition“), **eine Straße auf einmal**, beliebige Einsatzgrößen, ≈ 3 s je Straße | nicht genannt, Mila-Gründer | **+19,4 ± 4,1 bb/100** über 150 000 Hände | ReBeL-Prinzip, kommerziell ausgereizt |
| **PokerSkill** (2026) | Sprachmodell wählt aus Aktionen, die eine handgeschriebene Experten-Regelbibliothek vorgibt | nur API-Kosten | besser als Slumbot (indirekt); **−5,7 gegen GTO Wizard** | ohne Solver und Training auf −6: Regelwissen ist viel wert, aber die Decke ist nah |

## 3. Die wichtigsten Erkenntnisse für uns

1. **Slumbot schlagen ist nicht dasselbe wie gut gegen GTO Wizard sein.** DecisionHoldem gewinnt +73 gegen Slumbot und wäre trotzdem kaum in der Spitze der Rangliste. Slumbots Schwäche sind Off-Tree-Größen und eine grobe Abstraktion; GTO Wizard hat beides nicht. Ab etwa +10 gegen Slumbot sagt die Zahl wenig mehr aus. **Unser Maßband wird AIVAT gegen GTO Wizard, Slumbot nur noch als Vorstufe.**
2. **Alle an der Spitze rechnen in Echtzeit mit gelernten Werten oder mit riesigen Blueprints.** Reines End-zu-End-RL (AlphaHoldem, unser lynx-4) hat gegen Slumbot bei +10 seine Decke. Unser Weg über die Suche mit Wertnetz (Meilenstein 3) ist der richtige; lynx-4 bleibt Blueprint und später Destillationsziel.
3. **Trainingsverteilung des Wertnetzes ist der häufigste Fehler.** ReBeL: Wertnetz auf zufällig gezogenen Ranges „lernt nichts Wertvolles“; DeepStack kam mit strukturiert-zufälligen Ranges nur mit 10 Mio. Situationen durch. Konsequenz für `valuedata.py`: **mindestens die Hälfte der Situationen aus echtem Suchspiel** (Ranges, die unsere Suche an Blättern tatsächlich erreicht, aus Prüfstand- und Selbstspiel-Läufen protokolliert), die andere Hälfte strukturiert-zufällig für Robustheit. Das ist die wichtigste Änderung am Plan.
4. **Iterationen und Warmstart.** DecisionHoldem rechnet 6 000–10 000 Iterationen je Entscheidung, ReBeL kommt mit wenigen hundert aus, weil ein Politiknetz die Suche startet. Wir liegen bei 40–300 ohne Warmstart. **Blueprint-Warmstart** (CFR-Startstrategie aus lynx-4 statt gleichverteilt, linear gewichtet) ist billig und spart Iterationen oder bringt Genauigkeit.
5. **Suchraum.** Supremus nennt „größerer Suchraum“ als eine der fünf Zutaten; GTO Wizard erlaubt jede Größe; ReBeL 9 Aktionen; DecisionHoldem 5 Größen plus All-in. Wir: 1–4. Sobald das Wertnetz die Bäume klein macht, wird `wide` Standard und bekommt eine dritte Raise-Größe.
6. **Off-Tree-Aktionen gehören in den Baum** (Libratus, ReBeL, DecisionHoldem): machen wir schon (tatsächliche Einsatzgröße wird als Ast eingefügt). Behalten.
7. **Sicherheit.** ReBeL zeigt, dass sichere Suche ohne Zusatzbedingungen entsteht, wenn man die Strategie einer zufälligen (späten) Iteration spielt statt der letzten; wir nutzen die gewichtete Durchschnittsstrategie, das ist in der Praxis gleichwertig. DecisionHoldem setzt mehrere Gegnerstrategien an die Blätter; das Wertnetz macht das implizit über die Range-Eingabe.
8. **Iteration zahlt sich aus.** MIT Marvel ging in sechs Monaten von −14 auf −4,6. Die Rangliste ist ein Lernwerkzeug, kein Endzeugnis.

## 4. Was wir anders oder besser machen können

- **Exakt statt gebucketet.** DeepStack und Supremus geben dem Netz gebucketete Ranges; wir rechnen mit allen 1 326 Kombinationen und exakten Blockern, und unsere Bäume sind klein genug dafür. Das ist ein Genauigkeitsvorteil in genau den Situationen, in denen Bots typischerweise Blocker falsch bewerten.
- **Gegneranpassung.** Keines der GTO-Systeme beutet Gegner aus; gegen Menschen ist das aber die Hälfte des Gewinns. Unser Gegnermodell und die Suche sind dafür gebaut (H6). Gegen GTO Wizard bringt es nichts, gegen Menschen alles.
- **Mehrspieler und Turnier.** GTO Wizard misst nur Heads-up 200 BB. Unser Ziel sind Menschen an vollen Tischen mit Turnierstacks; dort zählen ICM und 3-Spieler-Suche, die niemand auf der Rangliste braucht.
- **Messdisziplin von Anfang an.** Gepaarte Prüfstände, Kontrollvariablen gegen Slumbot, AIVAT bei GTO Wizard: wir wissen jederzeit, was eine Änderung bringt. Das ist der eigentliche Hebel, mit dem Marvel 10 bb/100 geholt hat.
- **Budget.** ReBeL: 1 000 GPUs. DecisionHoldem: 4 000 Kernstunden. Wir: ein Laptop, ein paar Euro Hetzner und Kaggle. Deshalb DeepStack-Reihenfolge (River zuerst, kleine exakte Bäume), kein Blueprint-CFR mit Milliarden Iterationen.

## 5. Änderungen am Plan (ab 30.10.)

1. `valuedata.py`: Modus „aus Spiel“: Blatt-Situationen (Board, Pot, Stack, beide Ranges) während Prüfstand- und Selbstspiel-Läufen der Suche protokollieren (`data/valuenet/live-ranges-*.npz`) und exakt lösen. Zielmischung 50 % Spiel, 50 % strukturiert-zufällig. Lernkurve getrennt nach Quelle messen.
2. Blueprint-Warmstart in `husearch.solve`: Startstrategie aus lynx-4-Wahrscheinlichkeiten je Kombination (Netz einmal je Knoten ausgewertet) statt gleichverteilt; Iterationen bei gleicher Ausnutzbarkeit messen.
3. Nach dem River-Netz: Preset `wide` als Standard, dritte Raise-Größe, Iterationen hoch.
4. Erste GTO-Wizard-Messung sofort nach Freigabe mit 500 Händen (bleibt im Rauschen der Liste), dann je Version 2 000–5 000 Hände; erst stabile Versionen auf 20 000+ Hände.
5. Slumbot ab jetzt nur noch als Vorstufe (5 000 Hände je Version), Ziel dort „> 0 gesichert“, nicht mehr.
6. Ziele: GTO Wizard −20 (Slumbot-Niveau) mit River-Netz, −10 mit Turn-/Flop-Netz und Warmstart, −5 mit breiterem Suchraum und Selbstspiel-Daten.

## Quellen

- GTO Wizard Benchmark (Provost, Ilenic, Solinas, Beardsell), arXiv 2603.23660; Rangliste https://benchmark.gtowizard.com (abgerufen 29.10.2026); Blog „GTO Wizard AI Explained“ (2023), „Crushing a Top HUNL Poker Bot“
- ReBeL: Brown, Bakhtin, Lerer, Gong, „Combining Deep Reinforcement Learning and Search“, arXiv 2007.13544
- Supremus: Zarick, Pellegrino, Brown, Banister, „Unlocking the Potential of Deep Counterfactual Value Networks“, arXiv 2007.10442
- DecisionHoldem: Zhou, Bai, Zhang, Duan, Huang, arXiv 2201.11580 (v2 2024), Code github.com/AI-Decision/DecisionHoldem
- AlphaHoldem: Zhao, Yan, Li, Li, Xing, AAAI 2022
- DeepStack: Moravčík u. a., Science 2017, arXiv 1701.01724; Depth-Limited Solving: Brown, Sandholm, Amos, arXiv 1805.08195
- PokerSkill, arXiv 2605.30094; SpinGPT, arXiv 2509.22387 (13,4 ± 12,9 bb/100 gegen Slumbot, LLM)
- PokerNews / PokerListings zur Rangliste (April 2026): Marvel −14,0 ± 4,7 beim Start
