# Lynx: Plan für das nächste Level

Stand: 29.10.2026, 01:30 Uhr. Grundlage: `DOKUMENTATION.md` (Stand 28.10.), `ZIELE.md`, alle Prüfstand- und Slumbot-Daten, die fünf echten Turniere vom 28./29.10. und eine Recherche zu Verfahren, Rechenleistung und Kosten (Quellen am Ende).

Dieses Dokument beantwortet drei Fragen: **Wo stehen wir wirklich? Was bringt uns um ein Vielfaches weiter? Was kostet das und wie lange dauert es?**

---

## 1. Ehrliche Bestandsaufnahme

### 1.1 Was Lynx heute kann

| Maß | Wert | Einordnung |
|---|---|---|
| Echte PokerTH-Turniere (6er, gegen PokerTH-Bots) | **5 Turniere: Plätze 1, 3, 6, 6, 1 → 2 Siege, ROI +44 %** | Zufall wäre 1 Sieg aus 6. Statistisch noch wertlos (95 %: etwa −80 bis +170 %). |
| Simulierte Mensch-Tische `mensch480` | +96,8 % ROI | knapp unter Stufe 1 (+100 %) |
| Slumbot (HU, 200 BB), bereinigt | **−17,2 bb/100** [−38; +4] | verliert klar gegen ein Gleichgewicht |
| Ausnutzbarkeit | Ausbeuter +2,3 % | keine groben Lecks |
| Endspiel HU 20 BB | +17,9 % gegen Nash, +83 % gegen Mensch-Bots | gut |

**Einschätzung:** solider Amateur bzw. Micro-Stakes-Regular. Gegen Freizeitspieler und die PokerTH-Bots gewinnend, gegen starke Gegner klar unterlegen.

### 1.2 Was uns die fünf echten Turniere gezeigt haben

- **Die Live-Kette war der eigentliche Gegner, nicht die Bots.** Vier von fünf Spielen liefen mit Fehlern, die heute Nacht behoben wurden: Vorschläge 10–20 s zu spät (Analyse-Warteschlange), Phantom-Vorschläge nach Handende, Handnummer hing 10–20 s nach (der Verlauf der Vorhand steckte in der Observation), Stacks als „51000“ statt „1000“ gelesen. Die Verluste in Spiel 3 und 4 fielen mit solchen Fehlern zusammen.
- **Nach den Fixes:** Vorschlag im Schnitt 0,7 s nach Erkennung, Aktionen gegen das Log 88 % (vorher 78 %), Dealer/Blinds 100 % (vorher 74 %), alle 5 Plätze werden automatisch richtig erkannt.
- **Das PokerTH-Feld ist schlagbar.** Lynx' Stil (viele Raises preflop, Druck auf passive Bots) passt. Die beiden Siege kamen über Aggression, die beiden letzten Plätze über große Pots mit Overpair gegen Ass bzw. einen Phantom-Jam.

### 1.3 Wo Lynx wirklich verliert (aus den Daten)

1. **Postflop gegen starke Gegner.** Preflop ist durch den HU-Preflop-Löser repariert (Preflop-Anteil gegen Slumbot +0,7 statt −18,7 bb/100). Das Netz verliert danach: zu grobe Einsatzgrößen (8 Aktionen), Mini-Bets in große Pots, kein echtes Rechnen mit Ranges.
2. **Kein ICM.** Belohnung ist Chip-EV. In einem 6er-SNG mit 50/30/20 ist das in der Bubble-Phase messbar falsch (zu viele Coinflips bei 3–4 Spielern).
3. **Kein Anpassen an den Gegner.** Das Gegnermodell ist nur ein Eingangsmerkmal. Gegen statische Bots (PokerTH) ist Ausbeuten der größte Hebel, und den nutzen wir nicht.
4. **Rechenleistung.** Das Trainingsrezept ist auf dem Laptop ausgereizt (Plateau lynx-3 ab 300 Iterationen). Mehr Netz, mehr Gegnervielfalt, längere Läufe und Deep CFR scheiterten alle am selben Engpass: 16 GB, 10 Kerne, USB-Stick.

### 1.4 Was die Spitze heute macht (und was davon realistisch ist)

| Verfahren | Ergebnis gegen Slumbot | Rechenaufwand | Übertragbar? |
|---|---|---|---|
| **DecisionHoldem** (2022, Code offen): Linear-CFR-Blueprint + sichere tiefenbegrenzte Suche | **+73 bb/100** | Blueprint: 48 Kerne, 3–4 Tage ≈ 4.000 Kernstunden | Ja, heads-up. Genau unsere Architektur (Blueprint + Suche), nur viel mehr Rechenzeit und eine „sichere“ Suche. |
| **AlphaHoldem** (AAAI 2022): End-to-end-RL, Self-Play gegen eigene Historie | schlägt Slumbot und DeepStack | „ein PC, 3 Tage“ | Ja, ist im Kern unser PPO-Weg, aber mit großem Netz auf rohen Karten statt 57 Merkmalen. |
| **GTO Wizard AI** (2026, geschlossen) | +19,4 ± 4,1 bb/100 | unbekannt | Als Maßstab: ein echter Solver-Bot liegt „nur“ +19 über Slumbot. |
| **SpinGPT** (2025, LLM + RL) | +13,4 ± 12,9 bb/100 | GPU-Training | Nein, zu teuer, HU-only. |
| **Pluribus** (6-max, 2019) | – | Blueprint 8 Tage auf 64 Kernen, Suche live 28 Kerne | Teilweise: Prinzipien ja, Maßstab nein. |

**Schlussfolgerung:** Der Weg von „−17“ auf „deutlich über 0“ gegen Slumbot ist keine Frage neuer Ideen, sondern von **Rechenzeit (Tausende Kernstunden) plus einer sicheren Suche**. 4.000 Kernstunden sind auf einem gemieteten 16-Kern-Server etwa **11 Tage**. Das ist bezahlbar.

Für **PokerTH-Turniere** (6er-SNG, 50 BB, schnelle Blinds) ist Slumbot aber nur das Maßband für die Heads-up-Phase. Dort zählen ICM, Kurzstack und die Ausnutzung schwacher Gegner mehr. Beides zusammen ergibt den Plan.

---

## 2. Die Hebel, nach erwartetem Nutzen je Aufwand

| # | Hebel | Erwarteter Effekt | Aufwand | Kosten | Sicherheit der Erwartung |
|---|---|---|---|---|---|
| H1 | **Live-Kette hart machen** (Collector) | Ziel 1 überhaupt messbar; jeder Erfassungsfehler kostet direkt Turniere | 2–3 Tage | 0 € | hoch (Fehler sind bekannt und reproduzierbar) |
| H2 | **ICM in Belohnung und Endspiel** | +5 bis +15 % ROI in SNGs, vor allem Platz 3→2→1 | 2–3 Tage | 0 € | hoch (Standardwissen, direkt auf Prüfstand messbar) |
| H3 | **Server für Training und Prüfstand** | Grundvoraussetzung für H4–H6; 3–4× Durchsatz, kein RAM-Limit, kein Stick, läuft 24/7 | 1 Tag Einrichtung | ≈ 116 €/Monat + 88 € einmalig | hoch |
| H4 | **lynx-4: neues Trainingsrezept auf dem Server** (größeres Netz, mehr Gegnervielfalt, PokerTH-Formatgewichte, ICM-Belohnung, 5.000–10.000 Iterationen, Ausbeuter alle 50 It) | mensch480 +100 → +115…125 %; Slumbot −17 → −10 | 1 Woche Lauf + 2 Tage Bau | im Server enthalten | mittel (das Plateau kann wiederkommen; H5 ist der eigentliche Sprung) |
| H5 | **Suche als Lehrer (Expert Iteration)**: die HU-Suche (und eine 3-Spieler-Variante) erzeugt Zielpolitiken, das Netz lernt sie; dazu sichere tiefenbegrenzte Suche mit Wertnetz (DecisionHoldem/ReBeL-Prinzip) | der größte Sprung: Slumbot −10 → ±0 bis +10; Endspiel HU deutlich stärker | 2–3 Wochen Bau, 1–2 Wochen Rechnen | Server + optional 20–40 GPU-Stunden (≈ 20–40 €) | mittel (Konzept erprobt, unsere Umsetzung neu; hus-2 hat gezeigt, wie leicht Suche schadet) |
| H6 | **Ausbeuterische Suche gegen das Gegnermodell** (Ranges aus beobachtetem Verhalten statt Gleichgewicht) | gegen PokerTH-Bots und Freizeitspieler sehr groß (+20–50 % ROI denkbar) | 1–2 Wochen | 0 € | mittel bis hoch für Bots, offen für Menschen |
| H7 | **PokerTH-spezifische Gegnerprofile** aus eigenen Aufnahmen (Collector-Daten, nicht das Log) | Training und Prüfstand treffen das echte Feld | 1 Woche + laufend | 0 € | hoch, aber braucht 50+ aufgezeichnete Turniere |
| H8 | **Nachbau der PokerTH-Trainingsbots** aus dem offenen Quellcode des Web-Clients (AGPL, GitHub `narmod/pokerth-web-client`) | perfekte Sparringspartner für Ziel 1 (Bot-Phase) | 3–5 Tage | 0 € | hoch, **braucht deine Entscheidung** (Abschnitt 5) |
| H9 | **Zweites externes Maßband**: GTO Wizard Benchmark (öffentliche HUNL-API mit AIVAT-Varianzreduktion) | belastbarere Zahlen mit 10× weniger Händen | 1–2 Tage | unbekannt (vermutlich frei) | **braucht deine Freigabe** (externer Dienst) |
| H10 | **Menschen auf pokerth.net** (Ranking-Spiele) | das eigentliche Ziel 1 | nur Spielzeit | 0 € | – |

Nicht im Plan, weil Aufwand und Nutzen nicht passen: LLM-basierte Bots (SpinGPT-Weg), Deep CFR auf dem Laptop, weiteres Stil-Parameter-Tuning, Rollout-Suche Stufe 1.

---

## 3. Phasenplan

### Phase 0: diese Woche (29.10.–2.11.), 0 €

Ziel: Messbarkeit und die billigen, sicheren Gewinne.

1. **Collector härten (H1)**
   - Handnummer-OCR: die neue Handwechsel-Erkennung (Board leer, Dealer wandert) ist drin; dazu Zuordnung zum Export über Reihenfolge und Karten, damit `compare` auch abgeleitete Hände prüft.
   - Checks beim falschen Sitz, Startstack-Zeitpunkt, „$“ als „5“ in der OCR selbst (nicht nur im Live-Filter).
   - Alle vier Kartenfarben und Tischgrößen 2–10 systematisch gegen Bilder prüfen.
   - Überdeckungsfeste Aufnahme (Windows.Graphics.Capture) nur, wenn es dich beim Spielen stört.
   - Messgröße: Aktionen ≥ 95 %, Hände zugeordnet ≥ 95 % gegen jedes neue Log.
2. **PokerTH-Vergleich Suche gegen Netz** (hu480, mensch480) endlich zu Ende rechnen, wenn du nicht spielst. Entscheidet, ob `hus` Live-Standard wird.
3. **ICM (H2)**: Malmuth-Harville-ICM in `tournament.py`, Belohnung wahlweise ΔICM statt ΔChips, Push/Fold-Tabellen mit ICM, Prüfstand-Set `icm240` (Bubble-Situationen). Erwartung messbar auf mensch480.
4. **Echte Turniere sammeln**: jeden Abend 3–5 Spiele, konsequent den Vorschlägen folgen. Ziel 20 bis Ende der Woche. Jede Aufnahme fließt in H7.
5. **Doku und Tests** nachziehen, Liga-Report aktualisieren.

Ergebnis Phase 0: Live-Kette stabil, ICM drin, 20 echte Turniere, Entscheidung zur Suche.

### Phase 1: Server und lynx-4 (Woche 2–3), ≈ 200 €

1. **Hetzner AX102 mieten** (Ryzen 9 7950X3D, 16 Kerne/32 Threads, 128 GB ECC, 2× 1,92 TB NVMe): etwa 104 € netto / 116 € brutto im Monat plus 79 €/88 € Einrichtung. Günstiger: AX42 (8 Kerne, 64 GB, etwa 68–97 €), aber für H5 zu klein. `pc.sh` existiert schon für Linux.
   - Projekt per rsync/git auf den Server, Laptop und Stick bleiben nur für Live.
   - Nächte und Tage: Training, Prüfstand, Slumbot laufen dort parallel, ohne Speicher-Wächter.
2. **lynx-4 (H4)** mit dem bewährten Rezept plus neuen Zutaten:
   - Netz 256×256 (oder 3 Schichten), `widen` aus lynx-3-300
   - Belohnung ΔICM in Turnieren, Chip-EV in Cash
   - Gegnerpool: Mensch-Bots 40 %, Self-Play 30 %, Ausbeuter alle 50 It, Zufalls-Stilbots 10 %, ab Phase 2 PokerTH-Profile
   - Tischgewichte am PokerTH-Format (6er 50 BB, Blinds alle 9 Hände) plus HU/3er für das Endspiel
   - 5.000–10.000 Iterationen (Laptop: 7 s/It → Server ≈ 2–3 s/It bei 32 Threads, also 1–2 Tage je 5.000 It)
   - Gates wie bisher (eigene Seeds, einmalige Bestätigung)
3. **Slumbot 20.000 Hände** für lynx-4 (bereinigt), damit Stufe 1 von Ziel 3 sauber gemessen ist.
4. Optional **GTO Wizard Benchmark (H9)** anbinden, wenn freigegeben.

Ergebnis Phase 1: lynx-4 als neuer Standard oder der Beleg, dass das Rezept wirklich ausgereizt ist (dann H5 umso wichtiger).

### Phase 2: Suche als Kern (Woche 3–6), ≈ 120 €/Monat Server + ≈ 30 € GPU

1. **Sichere tiefenbegrenzte Suche heads-up** (H5):
   - Wertnetz statt Ausspielen bis zum Showdown (Eingabe: öffentlicher Zustand + beide Ranges; Ausgabe: Wert je Kombination). Trainingsdaten erzeugt die bestehende CFR+-Suche auf dem Server (Millionen gelöster Teilspiele).
   - Mehr Einsatzgrößen (Flop 0,33/0,5/0,75/1,25, Turn/River 0,33/0,66/1,0/1,5/2,0 + All-in), 1.000+ Iterationen je Entscheidung auf dem Server bzw. 300 live.
   - Flop in die Suche (jetzt nur Preflop, Turn, River).
   - Der Kern ist schon da (`husearch.py`, numba, exakte Blocker). Neu sind Wertnetz, Flop-Baum und die Sicherheitsbedingung (Gegner-Range nicht unterschätzen, Stichwort „safe subgame solving“ aus DecisionHoldem).
2. **3-Spieler-Suche**: CFR über 3 Ranges ist noch rechenbar (1326³ zu groß → 169-Klassen-Abstraktion preflop, 1326 nur für die zwei aktiven Spieler postflop). Deckt Bubble und Endphase ab, wo SNGs entschieden werden.
3. **Expert Iteration**: Netz lernt die Suchpolitik (Behavior Cloning auf Suchentscheidungen) und spielt dann so, auch 6-handig, wo die Suche nicht hinkommt. Das ist der Weg, mit dem AlphaZero-artige Systeme aus Suche dauerhafte Stärke machen.
4. GPU nur für das Wertnetz-Training (RTX 4090 gemietet, ≈ 0,35–0,70 $/h, 20–40 Stunden).

Ergebnis Phase 2: Slumbot-Ziel Stufe 2 (> 0) realistisch, Endspiel deutlich stärker, Netz lernt mit.

### Phase 3: PokerTH-Spezialisierung (Woche 6–10), Serverkosten laufen weiter

1. **Gegnerprofile aus 50+ eigenen Aufnahmen (H7)**: je PokerTH-Bot-Name ein Profil (VPIP, PFR, C-Bet, Fold auf Einsatz je Straße, Showdown-Neigung), aus den Collector-Daten. Daraus Trainingsgegner und ein Prüfstand-Set `pokerth-bots480`.
2. **Ausbeuterische Suche (H6)**: Die Suche rechnet mit der Range, die das Gegnermodell vorhersagt, statt mit dem Gleichgewicht. Gegen statische Bots ist das der größte Hebel. Sicherung: Mischung aus Gleichgewicht und Ausbeutung je nach Vertrauen (Hände beobachtet).
3. **Nachbau der Trainingsbots (H8)**, falls freigegeben: aus dem offenen Quellcode exakte Kopien als Trainingsgegner. Dann lässt sich der erwartete ROI gegen das PokerTH-Bot-Feld im Simulator direkt messen, mit Tausenden Turnieren statt fünf.
4. **Menschen (H10)**: Ranking-Spiele auf pokerth.net mit der Leiste, jedes Turnier eingetragen. Ab hier zählt Ziel 1 wirklich.

Ergebnis Phase 3: Ziel 1 Stufe 1 (50 Turniere, ROI > 0) erreichbar, Stufe 2 (200 Turniere, ROI > +20 %) in Reichweite.

---

## 4. Kosten und Dauer auf einen Blick

| Posten | Betrag | Anmerkung |
|---|---|---|
| Hetzner AX102, 3 Monate | ≈ 350 € brutto | 116 €/Monat, monatlich kündbar |
| Einrichtung | ≈ 88 € einmalig | je nach Länderseite 44–88 € |
| GPU-Stunden (Wertnetz) | ≈ 20–40 € | nur Phase 2, Vast.ai/RunPod, RTX 4090 |
| **Summe für 3 Monate** | **≈ 450–500 €** | |
| Nullkosten-Variante | 0 € | alles auf dem Laptop: Phase 1–2 dauern 3–4× länger (Nächte), H5 praktisch nicht machbar, Deep-Varianten entfallen |

**Sparvariante (Entscheidung 29.10., gewünscht: Maximum bei minimalem Budget).** Der Plan braucht Kernstunden in Schüben, keinen Dauerserver:

| Stufe | Was | Kosten | Reicht für |
|---|---|---|---|
| 0 | Laptop nachts, neues ThinkPad (4 Kerne, 16 GB), bestehender Hetzner-VPS (4 vCPU, 8 GB), Kaggle (30 GPU-h/Woche gratis) für das Wertnetz | 0 € | Phase 0, Phase 1 etwa 2× langsamer, Wertnetz-Training |
| 1 | Stundenweise Cloud (Hetzner CCX/CPX, Vast.ai-CPU) nur für Rechenschübe | ≈ 10–30 € je Schub | Phase 2: 4.000 Kernstunden ≈ 15–40 € |
| 2 | Hetzner Serverbörse (gebrauchter Dedicated, 64 GB, meist ohne Einrichtung) | ≈ 35–65 €/Monat | alles 24/7, nur falls Stufe 0 nicht reicht |
| 3 | AX102 | 116 €/Monat + 88 € | nur für dauerhaft paralleles Training + Prüfstand + Slumbot |

Gewählter Weg: Phase 0 und 1 auf Stufe 0, Phase 2 auf Stufe 1, Stufe 2 nur bei Bedarf. **Budget: 0 € für 2–3 Wochen, danach etwa 30–60 € insgesamt.** Nötig: Zugang zu ThinkPad und VPS, ein Kaggle-Konto. Hetzner hat 2026 zweimal erhöht und die CX-Reihe ist zeitweise nicht bestellbar, Preise vor dem Bestellen prüfen.
| Alternative Kauf | 1.500–2.500 € | gebrauchte Workstation (16 Kerne, 64–128 GB, RTX 3090/4090). Rechnet sich gegenüber Miete erst nach 15–20 Monaten. |

**Deine Zeit (der echte Engpass für Ziel 1):** ein 6er-SNG dauert 10–20 Minuten. 50 Turniere ≈ 12–15 Stunden, 200 Turniere ≈ 50–60 Stunden Spielzeit. Ohne diese Zeit gibt es kein belastbares Ziel 1, egal wie stark Lynx wird.

**Meine Zeit:** Phase 0 ≈ 5 Arbeitstage, Phase 1 ≈ 3 Tage Bau + Rechenzeit, Phase 2 ≈ 15 Tage, Phase 3 ≈ 10 Tage. Insgesamt etwa 10 Wochen bis zum Ende von Phase 3, wenn nichts dazwischenkommt.

---

## 5. Entscheidungen, die ich von dir brauche

1. **Server ja/nein?** Empfehlung: ja, AX102, ab Phase 1. Ohne Server bleibt der Plan bei Phase 0 plus langsamem lynx-4 stehen.
2. **Nachbau der PokerTH-Trainingsbots aus dem offenen Quellcode (H8)?** Das ist kein DOM-, Netzwerk- oder Log-Zugriff, sondern öffentlicher AGPL-Code. Es verstößt gegen keine unserer Regeln, aber du hast Slumbot bewusst als reines Maßband definiert, und Lynx soll allgemein stark werden. Mein Vorschlag: Nachbau als **ein** Gegnertyp im Pool (wie die Mensch-Bots), nicht als alleiniges Trainingsziel, und als eigenes Prüfstand-Set.
3. **GTO Wizard Benchmark (H9)?** Externer Dienst, HU-only, AIVAT-Varianzreduktion. Nur als zweites Maßband neben Slumbot. Deine Freigabe nötig.
4. **Ranking-Spiele gegen Menschen (H10)** ab wann? Vorschlag: sobald 20 Bot-Turniere mit stabiler Live-Kette durch sind.

---

## 6. Erwartung in Zahlen (ehrlich, nicht versprochen)

| Maß | heute | nach Phase 1 | nach Phase 2 | nach Phase 3 |
|---|---|---|---|---|
| mensch480 (ROI) | +97 % | +110–120 % | +120–130 % | +130 % (gegen PokerTH-Profile deutlich höher) |
| Slumbot bereinigt (bb/100) | −17 | −10 ± 5 | **0 bis +10** | unverändert (nicht Ziel) |
| Endspiel nash240 | +18 % | +20 % | +30 % | +30 % |
| Echte Turniere ROI | +44 % @5 | 20 Turniere gemessen | 50 Turniere, ROI > 0 (Stufe 1) | 100+ Turniere, Richtung +20 % |
| Vorschlag-Latenz live | 0,7–1 s | 0,7 s | 1–2 s mit Suche (Server-Suche nicht nötig, numba reicht) | gleich |

„Um ein Vielfaches besser“ heißt in Poker-Maßstäben: Der Abstand zu einem Gleichgewichtsspieler (Slumbot) soll von −17 auf über 0 drehen, und der ROI gegen das PokerTH-Feld soll sich sichtbar und gesichert erhöhen. Das ist mit diesem Plan realistisch. Ein Sprung auf das Niveau von Pluribus oder GTO Wizard AI (6-max-Gleichgewicht, Tausende Kernstunden pro Blueprint und 28 Kerne live) ist mit einem Server möglich, aber ein Projekt für Monate, nicht Wochen.

---

## 7. Risiken

| Risiko | Gegenmittel |
|---|---|
| Plateau trotz neuer Zutaten (wie lynx-3) | Gates mit eigenen Seeds, früh abbrechen, Reihenfolge der Zutaten einzeln messen (Ablation) |
| Suche schadet statt zu helfen (wie hus-2, Rollout-Suche) | nie Live-Standard ohne gepaarten Sieg auf dem Prüfstand; Sicherheitsbedingung in der Suche; Mischung mit dem Netz |
| Mensch-Bots und PokerTH-Bots verhalten sich anders als echte Menschen | Ranking-Spiele früh beginnen, Profile aus echten Aufnahmen |
| Erfassungsfehler kosten Turniere | H1 zuerst; jede Sitzung gegen das Log prüfen, Kennzahlen pro Abend |
| Server-Kosten laufen, Nutzen bleibt aus | monatlich kündbar; nach Phase 1 Zwischenbilanz |
| Laptop und Stick (Standby, RAM) | nur noch Live auf dem Laptop; alles Schwere auf den Server |

---

## 7a. Zielklärung 29.10. (Jakob): Menschen, nicht Plattform-Bots

Lynx soll insgesamt richtig gutes Poker spielen, gegen alle möglichen Gegner und vor allem gegen Menschen. Die PokerTH-Bots sind Übungsfeld und Messpunkt, kein Ziel. Daraus folgt für den Plan:

- **Zurückgestellt:** H8 (Nachbau der PokerTH-Bots) und die Bot-Spezialisierung aus Phase 3. Sie würden Lynx auf ein Feld optimieren, das am Ende nicht zählt.
- **Kern bleibt H5, Suche als Lehrer:** Gleichgewichtsnähe ist die Grundlage, mit der man gegen unbekannte, gute Gegner nicht verliert. Reihenfolge: Wertnetz für die HU-Suche, Flop in den Baum, mehr Einsatzgrößen, 3-Spieler-Suche, dann Expert Iteration (Netz lernt die Suchentscheidungen und überträgt sie auf 6-handig).
- **H6 neu ausgerichtet auf Menschen:** Gegnermodell aus menschlichen Handhistorien (HandHQ/PHH sind erlaubt) statt aus Bot-Verhalten; die Mensch-Bots des Prüfstands (mensch480) werden feiner (Typen, Stack- und Positionsabhängigkeit); die Suche mischt Gleichgewicht und Ausbeutung je nach Vertrauen in das Modell. Gegen Freizeitspieler ist das der Hebel, gegen starke Spieler der Schutz.
- **Maßbänder statt Bot-Siege:** Slumbot (bereinigt), Pluribus-Übereinstimmung, GTO-Wizard-Benchmark (H9, braucht Freigabe), und echte Spiele gegen Menschen (H10, pokerth.net Ranking) als Zieltafel. PokerTH-Bot-Turniere bleiben als billiger Vorab-Test, zählen aber nicht als Erfolg.
- **Trainingsgegner:** mehr Mensch-Bots und Self-Play, weniger Stilbots; Tischgewichte weiter breit (2 bis 10 Spieler), nicht auf das PokerTH-Format verengt.

## 7b. Eingeplant 30.10. (Jakob): H11 Menschen-Range-Modell aus HandHQ-Showdowns

**Warum:** Die Suche steht und fällt mit dem Gegnermodell. Heute hat sie drei Priors: Heuristik, „Gegner spielt wie unser Netz“ (gut gegen PokerTH-Bots, hu480 −2,5) und Heads-up-Gleichgewicht (für Slumbot). Für Menschen fehlt der vierte: **wie spielen echte Normalspieler mit welchen Karten**. Genau das steht in HandHQ, aber nur in den Händen, die bis zum Showdown gingen: dort sind beide Blätter und alle Aktionen bekannt. Die Rohdaten liegen lokal (`data/external/phh-dataset/data/handhq`, 5,0 GB, 5.989 `.phhs`-Dateien, 5,72 Mio. Hände 25NL, PokerStars und Party 2009). Erlaubte Quelle (PHH/HandHQ), keine eigenen Aufnahmen, keine Personen (obfuskierte Spielernamen).

**Was gebaut wird (2–3 Tage, 0 €, nur Laptop-Rechenzeit):**

1. **Extraktion `humans.py` → `human_actions`:** je Showdown-Hand und je gezeigtem Spieler alle seine Entscheidungen als Zeilen (öffentlicher Zustand: Straße, Position, Spielerzahl, Pot, to_call, Stack/Pot, Raises bisher, Boardtextur; Aktion samt Größe; Lochkarten als Klasse und Kombination). Vorstudie 30.10. (Stichprobe 40 von 5.989 Dateien, 39.891 Hände): 21,7 % der Hände haben gezeigte Karten, 1,5 gezeigte Spieler je solcher Hand, 6 Entscheidungen je gezeigtem Spieler → hochgerechnet **1,24 Mio. Showdown-Hände und 7,5 Mio. Entscheidungen mit bekannten Karten** (preflop 2,2 Mio., Flop 2,1, Turn 1,8, River 1,5). Das ist 80-mal der Pluribus-Datensatz. Dazu die bekannten Datenfallen (fehlende Winnings, „????“, Antes) aus 4.4.
2. **Verzerrung offenlegen und abfangen** (Befund aus der ersten Extraktion 30.10.: in den Daten gibt es **keinen einzigen Fold**, denn wer gefoldet hat, zeigt keine Karten; das Modell liefert also P(Aktion | Hand, weitergespielt), die Fold-Raten müssen aus den unverzerrten Häufigkeiten kommen, und Flop- und Turn-Ranges unterschätzen aufgegebene Bluffs, River-Ranges sind fast unverzerrt): Showdown-Hände sind nicht alle Hände (wer früh foldet, zeigt nicht). Preflop-Ranges kommen deshalb weiter aus den unverzerrten Statistiken aller Hände (VPIP, PFR, 3-Bet je Position, schon in `handhq-25nl.json`), aus den Showdowns nur die **bedingten** Postflop-Ranges: „mit welchen Händen bettet, callt, raist ein Normalspieler auf dieser Straße in dieser Lage“. Das ist genau, was die Suche ab Flop braucht.
3. **Modell:** ein kleines Menschen-Politiknetz P(Aktion | Zustand, Handklasse) mit derselben Schnittstelle wie das Blueprint (Merkmale `features.py`, Aktionsraster `from_action`). Dann steckt es ohne weiteren Umbau in `bpranges.py` als Modus **`ranges=human`** (Gegner aus dem Menschenmodell, eigene Range aus Blueprint oder Gleichgewicht). Zusätzlich als Spielertypen (Nit, Station, Maniac …) getrennt trainierbar, weil `handhq-25nl.json` jeden Spieler einem Typ zuordnet; der OpponentTracker (feat-3) wählt live den Typ.
4. **Abnahme in drei Stufen:** (a) Vorhersagegüte auf zurückgehaltenen Showdowns (Log-Likelihood der gezeigten Karten unter der vorhergesagten Range, gegen Heuristik und Blueprint als Vergleich); (b) hu480 und mensch480 mit `ranges=human` gegen `pre,flop`; (c) GTO Wizard und pokerth.net gegen Menschen.
5. **Nebenprodukte:** ein echter **Menschen-Bot** (das Politiknetz spielt selbst) als Prüfstands- und Trainingsgegner statt der handgebauten Stilbots; und ein Datensatz, mit dem sich prüfen lässt, ob Lynx' Mini-Bets gegen Menschen wirklich funktionieren (V1-Frage).

**Reihenfolge:** nach den laufenden Messungen (F, Tranche 3, Slumbot hus-5) und vor der nächsten Wertnetz-Stufe (Turn). Begründung: Das Wertnetz macht die Suche schneller, das Menschenmodell macht sie gegen das eigentliche Ziel besser.

## 8. Nächste konkrete Schritte (Reihenfolge)

1. Heute Nacht: komplette Testsuite, Doku um den Abend ergänzen, Backup.
2. Morgen: Collector-Fixes H1 (Export-Zuordnung, Checks, OCR), danach PokerTH-Vergleich Suche gegen Netz zu Ende rechnen.
3. Übermorgen: ICM bauen und messen.
4. Abends: Turniere sammeln, 3–5 pro Abend.
5. Nach deiner Entscheidung zu 5.1: Server bestellen, Projekt migrieren, lynx-4 starten.
6. **(eingeplant 30.10.)** H11 Menschen-Range-Modell aus HandHQ-Showdowns (7b), danach Turn-Daten und Turn-Netz.

---

## Quellen

- Hetzner AX102: https://www.hetzner.com/dedicated-rootserver/ax102 (104 € netto/116 € brutto monatlich, Einrichtung 79/88 €, Stand der Seite; Preiserhöhungen 2026 laut https://www.deskmodder.de/blog/?p=210160)
- GPU-Preise 2026: https://www.hostinger.com/tutorials/?p=158956, https://www.spheron.network/blog/gpu-cloud-pricing-comparison-runpod-vs-vastai-2026/
- DecisionHoldem (Code offen, +730 mbb/h gegen Slumbot, 4.000 Kernstunden): https://arxiv.org/abs/2201.11580, https://github.com/AI-Decision/DecisionHoldem
- AlphaHoldem (ein PC, drei Tage): https://pi.cs.tsinghua.edu.cn/lab/people/jlxing/zh/publication/featured02-aaai-2022/
- GTO Wizard Benchmark (öffentliche HUNL-API, AIVAT, +19,4 gegen Slumbot): https://arxiv.org/abs/2603.23660
- SpinGPT (+13,4 ± 12,9 gegen Slumbot): https://arxiv.org/pdf/2509.22387v2
- PokerTH Web-Client (AGPL, Trainingsmodus, Ranking-Spiele): https://webclient.pokerth.net/how-to-play, https://awesome.ecosyste.ms/projects/github.com%2Fnarmod%2Fpokerth-web-client
