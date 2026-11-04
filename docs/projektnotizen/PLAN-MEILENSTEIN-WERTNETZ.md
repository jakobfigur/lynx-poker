# Meilenstein 3: Suche mit Wertnetz (Stufe 1b) – Plan vom 29.10.2026

Ziel des Meilensteins: Lynx spielt heads-up eine **vollständige Echtzeit-Suche** (Flop, Turn, River) mit einem
Wertnetz am Blattrand statt Ausspielen bis zum Showdown. Messbar an drei Maßbändern:

| Maßband | heute (lynx-4-300) | Ziel Meilenstein 3 |
|---|---|---|
| Slumbot, bereinigt | läuft (29.10. abends, Zwischenstand +34 bb/100 nach 3200 Händen) | > 0 gesichert, Richtung +10 |
| GTO Wizard AI, AIVAT | noch kein Zugang (beantragt) | −10 bb/100 |
| hu480 gegen Netz, gepaart | hus-1 läuft, hus-2 über Nacht | Suche signifikant vor dem Netz |

Rahmen (Entscheidung Jakob 29.10.): **Daten auf Hetzner Cloud (CPU, stundenweise), Wertnetz auf Kaggle (gratis),
alles privat.** Nach draußen gehen nur gelöste Kunst-Teilspiele, das Trainingsskript für das Wertnetz und (auf
Hetzner) der Code auf einem Server, der nach dem Lauf gelöscht wird. Keine Aufnahmen, keine Hände von Jakob.
Ziel bleibt starkes Poker gegen Menschen, nicht gegen die Bots einer Plattform.

---

## 0. Voraussetzungen (vor dem Start, je ein Satz von Jakob)

- [ ] Kaggle-Konto (gratis, keine Kreditkarte); Notebooks und Datasets bleiben privat (Standard).
- [ ] Hetzner-Cloud-Zugang: API-Token des bestehenden Projekts oder ein neues Cloud-Projekt. Server werden nur für
      den jeweiligen Lauf erzeugt und danach gelöscht (CPX51, 16 vCPU, ≈ 0,13 €/h; zwei parallel für 32 Kerne).
- [ ] Ergebnis Stufe 1a liegt vor (hus-2 gegen Netz und gegen hus-1 auf hu480). Entscheidet über die Baumform.

## 1. Was gebaut wird, in Reihenfolge

### 1.1 Blattwerte definieren (1 Tag)
Blatt = Ende der Flop-Setzrunde (Beginn Turn) bzw. Ende der Turn-Setzrunde (Beginn River), beide noch mit Chips.
Eingabe des Wertnetzes: öffentlicher Zustand (Board als Karten-Embedding oder 52-Bit, Pot, effektiver Stack, wer
handelt zuerst) plus **beide Ranges** (je 1326 Gewichte, normiert). Ausgabe: Wert je Kombination für Spieler 0
(1326 Werte, in Pot-Einheiten); Spieler 1 folgt aus der Nullsumme. Das ist die ReBeL-/DeepStack-Form („public
belief state → counterfactual values“). Datei: `ai/valuenet.py` (Netzdefinition + Laden), `ai/valuedata.py`
(Erzeugung).

**Korrektur 29.10. abends (nach erster Messung):** eine exakte Turn-Lösung mit allen Rivercards kostet 10–40 s,
eine River-Lösung 0,4–1 s. 500 000 Turn-Situationen exakt wären Hunderte Kerntage. Deshalb **Reihenfolge wie
DeepStack**: (1) River-Daten exakt → River-Netz, (2) Blattknoten in der Suche, (3) Turn-Daten mit River-Netz an
den Blättern (dann ≈ 1 s je Situation) → Turn-Netz, (4) Flop-Daten mit Turn-Netz → Flop-Netz. Jede Stufe für
sich messbar. Erster Datensatz: 300 000–500 000 River-Situationen ≈ 70 Kernstunden ≈ 2–3 h auf zwei CPX51.
Gebaut 29.10.: `ai/valuedata.py` (Situationen, synthetische Ranges, Lösen, .npz-Scherben), CLI
`pc.cmd train valuedata river --n 1000 --workers 4`, Tests `test_valuedata.py`. Probelauf: 12 River-Situationen,
0,95 s je Situation unter Volllast, Nullsumme je Situation < 0,001 Pot.

### 1.2 Datenerzeugung (3–4 Tage Bau, dann Rechenzeit)
- Zufällige Situationen ziehen: Board (Flop oder Turn), Pot/Stack-Verhältnis aus der Verteilung echter Hände
  (aus unseren Turnier- und Cash-Formaten), **Ranges** aus zwei Quellen gemischt: (a) Ranges, die unsere eigene
  Suche/`ranges.py` in gespielten Händen erzeugt, (b) zufällig verformte Ranges (Dirichlet-Rauschen, Teilmengen),
  damit das Netz auch Ranges außerhalb des Gleichgewichts bewertet (Robustheit gegen Modellfehler).
- Jede Situation mit der bestehenden CFR+-Suche **exakt** lösen (Turn: alle Rivercards; Flop-Blätter: Turn-Baum
  mit allen Rivercards, 200–400 Iterationen) → Zielwerte je Kombination = kontrafaktische Werte an der Wurzel.
- Umfang: 300 000–500 000 Situationen. Kosten je Situation auf dem Laptop ≈ 2–6 s (Kernel parallel), auf 32
  Hetzner-Kernen ≈ 0,2 s → 20–30 Stunden auf zwei CPX51 ≈ 6–8 €.
- Format: `data/valuenet/<satz>.npz` (Board-Ids, Zustand, Ranges float16, Zielwerte float16), je Datei ≤ 2 GB.
- Prüfung: 1 % Hold-out, Vergleich Netz gegen exakte Lösung (mittlerer absoluter Fehler in Pot-Anteilen; Ziel
  < 1,5 % des Pots).

### 1.3 Wertnetz trainieren (Kaggle, 1–2 Tage inkl. Warten)
- Netz: MLP mit 3–4 Schichten à 1024 (ReBeL-Größenordnung), Eingabe ≈ 2 700 Werte, Ausgabe 1326, Huber-Verlust
  in Pot-Einheiten, Nullsummen-Zwang als Nebenbedingung. ≈ 6–8 Mio. Parameter.
- Kaggle: T4/P100, 30 GPU-Stunden je Woche, Sitzung ≤ 9–12 h → Training in 2–3 Sitzungen à 4–6 h mit
  Checkpoints im privaten Dataset. Skript `kaggle/train_valuenet.py` (eigenständig, nur numpy/torch).
- Ergebnis zurück auf den Laptop: `data/valuenet/vnet-1.pt` (≈ 30 MB), läuft auf der CPU in < 2 ms je Blatt
  (gebündelt alle Blätter eines Baums in einem Aufruf).

### 1.4 In die Suche einbauen (2–3 Tage)
- `husearch.py`: neuer Knotentyp `LEAF` am Ende der Flop- bzw. Turn-Setzrunde; `_solve` erhält je Blatt die
  Wertvektoren aus dem Netz (werden vor den Iterationen einmal berechnet; die Ranges am Blatt ändern sich mit
  den Iterationen → alle 10 Iterationen neu bewerten, wie in ReBeL).
- Dann wird der Flop-Baum klein (keine gezogenen Karten mehr nötig) und der Turn-Baum exakt und schnell:
  Ziel < 0,5 s je Entscheidung live bei 100+ Iterationen.
- Sicherheit: Gegner-Range am Blatt nie unter einen kleinen Boden fallen lassen (Schutz gegen Modellfehler),
  Mischung mit dem bisherigen Ausspielen als Rückfall, wenn das Netz eine Situation nicht kennt.

### 1.5 Messen (laufend)
Reihenfolge der Maßbänder je Version: (1) hu480 gepaart gegen Netz und gegen die Vorgängersuche, (2) Slumbot
bereinigt 5 000–10 000 Hände, (3) GTO Wizard 5 000 Hände AIVAT. Live-Standard wechselt nur bei signifikantem
Sieg auf (1) und nicht schlechter auf (2).

### 1.6 Danach: Destillation ins Netz (Expert Iteration, Meilenstein 4)
Die Suchentscheidungen werden zu Trainingszielen für lynx-5 (Behavior Cloning + PPO-Feinschliff), damit die
Stärke auch 6-handig und in der Leiste ohne Suche ankommt. Dazu Gegnermodell-Ausbeutung (H6) in der Suche.

## 2. Kosten und Zeit

| Posten | Hardware | Dauer | Kosten |
|---|---|---|---|
| Bau 1.1–1.2 | Laptop | 4–5 Arbeitstage | 0 € |
| Daten rechnen | 2 × Hetzner CPX51 | 20–30 h | 6–8 € |
| Wertnetz | Kaggle T4/P100 | 12–18 GPU-h | 0 € |
| Einbau + Messen | Laptop, Slumbot, GTO Wizard | 3–4 Tage | 0 € |
| **gesamt** | | **≈ 2–3 Wochen** | **< 15 €** |

## 3. Risiken und Gegenmittel
- Netz bewertet Ranges außerhalb der Trainingsverteilung falsch → Rauschranges in den Daten (1.2 b), Boden
  für die Gegner-Range, Rückfall auf Ausspielen.
- Suche gewinnt heads-up, aber 6-handig ändert sich nichts → Meilenstein 4 (Destillation), parallel ICM-Training.
- Kaggle-Quote reicht nicht → zweites Konto ist nicht erlaubt; stattdessen Training auf dem Hetzner-Server (CPU,
  2–3 Tage, ≈ 10 €) oder RunPod Community 4090 (0,34 $/h, ≈ 5 $).
- Speicher-Wächter/Sperrbildschirm auf dem Laptop → lange Läufe nur noch losgelöst (Start-Process) oder auf dem Server.

## 3a. Nachtrag aus der Konkurrenzanalyse (29.10., `ANALYSE-KONKURRENZ-GTO.md`)
- **Trainingsverteilung:** ReBeL zeigt, dass ein Wertnetz auf rein zufälligen Ranges nichts Brauchbares lernt.
  Deshalb mindestens 50 % der Situationen aus echtem Suchspiel (Blatt-Ranges während Prüfstand/Selbstspiel
  protokollieren), 50 % strukturiert-zufällig. Beide Tranchen so zusammensetzen, Lernkurve je Quelle messen.
- **Blueprint-Warmstart** der Suche aus lynx-4 (statt gleichverteilter Startstrategie) vor dem Ausbau der
  Iterationen; DecisionHoldem braucht 6 000–10 000 Iterationen ohne, ReBeL wenige hundert mit Warmstart.
- **Suchraum** nach dem River-Netz auf `wide` plus dritte Raise-Größe.
- **Maßbänder:** GTO Wizard AIVAT ist das Hauptmaß; Slumbot nur noch als Vorstufe (> 0 gesichert reicht).

## 4. Nächste konkrete Schritte
1. 30.10. früh: Ergebnisse hus-1, hus-2 (Flop), Slumbot lynx-4-300 auswerten; Baumform für 1.1 festlegen.
2. 30.10.: `ai/valuenet.py` + `ai/valuedata.py` bauen, 1 000 Situationen auf dem Laptop lösen (Probelauf,
   Formatprüfung, Laufzeit je Situation).
3. 31.10.: Hetzner-Lauf vorbereiten (`pc.sh`, Startskript, Rücktransport), Kaggle-Skript bauen, auf 1 000
   Situationen testen.
4. Wochenende: Daten rechnen (Hetzner), Netz trainieren (Kaggle), Einbau 1.4.
5. Danach Messreihe 1.5.
