# Nachtprotokoll 26./27.10.2026

Ziel: Bot maximal verbessern, autonom. Stündliche Kontrolle (Cron :23).

## 00:55 Start
- Deep CFR (dcfr-1) bei It 37 angehalten (Einbruch bei It 30: mix96 -16 %, fest48 -18 %); Stand It 30 gespeichert.
- Nachtlauf `night.sh`: pros-r2 = Start pros-r1@300 (feat-2, Ranges), Anker pros-r1@0 (Pluribus-Nachahmer), Leine 0.3,
  512 Turniere/Iteration, **zufällige Formate** (2-10 Spieler, 20-200 BB, Blind-Tempo 5-20 Hände), 30 % Zufalls-Stilbots,
  Ausbeuter alle 50 It, Prüfstand alle 50 It. Abschnitte bis 300/600/900/1200/1500, jeder mit Aufnahmeprüfung
  gegen den aktuellen Champion (pros-ppo2, bzw. pros-r2 sobald einer besteht).
- Ausgangslage (mix96 Δ rock / fest48 Δ rock): pros-2@300 +22,8 / +12,9; pros-r1@300 +23,0 / +25,0.

## 01:35 Kontrolle 1
- Läuft: pros-r2 It 199/300, ~7 s/It, keine Fehler, RAM frei 3,4 GB.
- Prüfstand Δ rock (mix96 / fest48): It 50 +16,7 / +8,5 · It 100 +17,3 / +8,7 · It 150 +10,4 / +14,4 · It 200 +15,7 / +14,4.
  Etwas unter pros-r1@300 (+23 / +25) – erwartbar, da das Training jetzt auf alle Formate verteilt ist; die 6er-Testsets
  messen nur einen Teil. Aussagekräftig wird der Format-Prüfstand. Ausbeuter: +22,5 / +1,2 / +7,9 % (24 Schemata, unscharf).
- Entscheidung: weiterlaufen lassen, keine Änderung.

## Kontrolle 2 – 27.10. 02:35
- Abschnitt bis 300 beendet (Exit 0), Gate pros-r2@300 gegen pros-ppo2 nicht bestanden (kein Wiederholen). Abschnitt bis 600 läuft, It 450, keine Tracebacks, RAM frei 3,0 GB.
- Prüfstand mix96/fest48 (Δ rock): @250 +17,4/+17,7 · @300 +16,6/+18,1 · @350 +20,3/+19,4 · @400 +16,7/+16,2 · @450 +14,8/+9,8. Pluribus stabil 81 %.
- Entscheidung: kein klares Plateau/Abwärtstrend über mehrere Prüfstände (Schwankung im Rauschen, CI ±12). Weiterlaufen lassen; bei weiterem Abfall bis It 550 Lernrate senken erwägen.

## 02:41 – Hinweis
- Claude Code hat die night.sh-Hülle (Task bhzr6skj8) wegen Speicherdruck beendet (RAM frei ~2,7 GB). Der Trainingsprozess selbst läuft weiter (It 473, schreibt Fortschritt) und endet regulär bei 600 inkl. Gate.
- Folgeabschnitte 900+ starten dadurch nicht automatisch; Neustart von night.sh (setzt am Stand fort) erst bei der nächsten Kontrolle, wenn der aktuelle Prozess beendet ist und genug RAM frei ist.

## Kontrolle 3 – 27.10. 03:35–03:50
- night.sh lief doch weiter (Hülle nicht betroffen). Abschnitt 600 fertig, Gate pros-r2@600 gegen pros-ppo2: −5,8 % [−15,9; +4,3] → nicht bestanden.
- Prüfstand mix96/fest48 Δ rock: @350 +20,3/+19,4 · @450 +14,8/+9,8 · @500 +15,1/+16,9 · @550 +16,5/+9,0 · @600 +12,0/+12,3 · @650 +9,5/+11,2 → über 4+ Prüfstände klar fallend.
- Entscheidung: pros-r2 bei It ~690 abgebrochen (Stand bleibt erhalten). Neuer Lauf **pros-r3** ab pros-r2@350 (bester Prüfstand), Lernrate 3e-4 → 1,5e-4, Leine 0,3 → 0,5 (Anker pros-r1:0), sonst gleich. Abschnitte 200/400/600 mit Gate (night2.sh).
- Code: neue Option `train rl --lr` (gilt auch beim Fortsetzen; Optimierer-Lernrate wird nach dem Laden überschrieben). Tests 132 grün.

## 04:36 – Zwischenkontrolle (Task-Hinweis Speicherdruck)
- Claude Code meldete die night2.sh-Hülle als beendet (Speicherdruck, RAM frei 2,5 GB); Prozesse laufen aber weiter (night2.sh + Training aktiv, It 249).
- **Gate pros-r3@200 gegen pros-ppo2 BESTANDEN: +13,3 % [+3,0; +23,6]** → Liga 'pros-r3-200', neuer Titelverteidiger für Abschnitt 400.
- Prüfstand mix96/fest48 Δ rock: @50 +17,3/+13,5 · @100 +19,2/+12,5 · @150 +16,7/+8,5 · @200 +12,3/+4,0 · @250 +18,0/+1,5. Widerspruch: direkter Vergleich klar besser, Δ rock (6er-Sets, rock-lastig) uneinheitlich, fest48 sehr verrauscht (CI ±17). Weiterlaufen lassen, Format-Prüfstand am Ende entscheidet.

## 04:37 – Kontrolle 4
- pros-r3 läuft (night2.sh aktiv, It ~250, Prüfstand @250 läuft), keine Tracebacks, RAM frei 2,6 GB. Stand wie 04:36, keine Änderung.

## 05:37 – Kontrolle 5
- pros-r3 It 499, Abschnitt bis 600 läuft (Titelverteidiger pros-r3-200), keine Tracebacks, RAM frei 2,4 GB.
- Gate pros-r3@400 gegen pros-r3-200: +1,9 % [−6,1; +9,9] → nicht bestanden.
- Prüfstand mix96/fest48 Δ rock: @300 +8,9/−0,8 · @350 +15,7/+1,5 · @400 +17,8/+10,4 · @450 +19,8/+10,4 · @500 +13,6/+11,2 → Plateau im Rauschen, kein Trend. Kein Eingriff mehr: Lauf endet regulär bei 600, danach Format-Prüfstand + Deep CFR.

## 06:37 – Kontrolle 6: Nachtlauf fertig
- pros-r3 fertig um 06:03 (It 600). Gate pros-r3@600 gegen pros-r3-200: −4,9 % [−12,0; +2,2] → nicht bestanden. Liga-Bester bleibt **pros-r3-200** (einziger bestandener Kandidat der Nacht).
- Prüfstand @550 +14,2/+7,1 · @600 +15,9/+14,2 (mix96/fest48 Δ rock).
- Gestartet: morning.sh – Format-Prüfstand (formate,fest48,mix96) für rock, pros-2@300, pros-r1@300, pros-r2@350, pros-r3@200 (Gate-Sieger), pros-r3@450 (bester mix96 der Reihe); danach Deep CFR dcfr-1 fortsetzen. Log: data/rl/morning.txt.

## 06:48 – Format-Prüfstand fertig (Δ rock, gepaart)
| Bot | hu48 | 3max48 | 10max48 | turbo48 | deep48 | pokerth48 | Ø Formate | mix96 | fest48 |
|---|---|---|---|---|---|---|---|---|---|
| pros-r2@350 | +50,0 | +17,1 | +30,7 | +4,1 | +24,2 | +9,4 | **+22,6** | +20,3 | +19,4 |
| pros-r3@200 (Liga pros-r3-200) | +50,0 | +13,6 | +19,3 | −1,2 | +26,9 | +19,4 | +21,3 | +12,3 | +4,0 |
| pros-r1@300 | +41,7 | +13,1 | +13,4 | +12,1 | +23,5 | **+20,4** | +20,7 | **+23,0** | **+25,0** |
| pros-2@300 | +54,2 | +29,2 | +12,4 | −7,9 | +29,6 | +3,8 | +20,2 | +22,8 | +12,9 |
| pros-r3@450 | +41,7 | +16,1 | +10,4 | +8,1 | +18,3 | +8,5 | +17,2 | +19,8 | +10,4 |
- Fazit: alle Kandidaten im Rauschen gleichauf (CI je Format ±15–20). Das Multi-Format-Training der Nacht brachte keinen messbaren Gewinn gegen rock; im direkten Duell schlägt pros-r3-200 aber pros-ppo2 klar (+13,3 %). Für PokerTH (pokerth48) liegen pros-r1@300 und pros-r3@200 vorn.
- Deep CFR dcfr-1 läuft seit 06:44 weiter (It 43, Verlust 2,38). (Claude-Code-Meldung „wegen Speicher beendet“ betraf nur die Hülle, Prozesse laufen.)

## 07:37–09:40 – Stick-Ausfall
- 07:10:35 Windows-Ereignis „disk 11: Controllerfehler auf Harddisk1“ → Stick (Intenso cMobile Line) fiel während des Laufs aus, nicht abgezogen. Erst nach Umstecken an anderen Port (~09:40) wieder erkannt, Volume „Healthy“.
- Deep CFR dcfr-1 kam bis It 62, letzter Checkpoint ckpt_000060 (07:06). Liga-Datei players.json intakt (12 Spieler), Protokoll und Logs lesbar.
- Stündliche Kontrolle um 08:37 gelöscht.

# Nacht 27./28.10.2026 – lynx-3
- 20:55 Start train_lynx3.sh: lynx-3 ab lynx-2@500 (Lynx 2), 40 % Mensch-Bots, Abschnitte 300/600/900/1200/1500, Gate 600 frische Turniere gegen Liga-Besten, Prüfstand mensch480+praezise gepaart gegen lynx-2@500.
- Parallel: Slumbot lynx-2@500, 20000 Hände, 4 Sitzungen. Stündliche Kontrolle (Cron 75da942c) startet bei Abbruch neu.
- 21:30 Speicher-Wächter beendete Slumbot (bei 3000 Händen: −22,2 bb/100 [−60; +16]); Training läuft weiter (It 142). Slumbot wird erst nach dem Training fortgesetzt (Cron neu: 21:27).

## 22:33 Kontrolle
- Training lynx-3 läuft (It 399, Abschnitt bis 600), keine Fehler. Freier RAM 1,9 GB → bench compare ausgelassen, um das Training nicht zu gefährden.
- Gate @300 gegen lynx-2: +4,5 % [+0,3; +8,6] **bestanden** → lynx-3-300 in der Liga. best.json: @200 vs lynx-2@500 Mittel +0,74 (mensch480 +3,7 [−1,2; 8,6]).
- Slumbot: wartet auf NACHTLAUF FERTIG (3000/20000 Hände).

## 23:33 Kontrolle
- Training lynx-3 hat It 600 erreicht, Aufnahmeprüfung @600 gegen lynx-3-300 läuft gerade (600 Schemata). Kein Traceback. Freier RAM 3,3 GB; bench compare ausgelassen (Gate läuft).
- best.json jetzt @500 vs lynx-2@500, Mittel +1,76.
- Slumbot: wartet (3000/20000).
- best@500 im Detail: mensch480 +9,6 [4,8; 14,4], mix960 +0,9, pokerth480 +0,8, hu480 −1,5, 10max240 −1,0.

## 00:33 Kontrolle
- Gate @600 gegen lynx-3-300: −3,7 % [−8,2; +0,9] nicht bestanden (Titelverteidiger bleibt lynx-3-300).
- Training läuft, It 827 im Abschnitt bis 900, kein Traceback. Freier RAM 1,3 GB → compare ausgelassen.
- best.json unverändert @500 (Mittel +1,76 vs lynx-2@500). Slumbot wartet (3000/20000).

## 00:45 Plan für den Rest der Nacht (vorab festgelegt)
- train_lynx3.sh läuft weiter bis 1500 (Gates bei 900/1200/1500).
- Danach morgen_lynx3.sh: Kandidat = letzter lynx-3-Stand mit bestandener Aufnahmeprüfung.
  1. Mensch-Tische vs lynx-2@500, 600 frische Schemata, Seed "lynx3-28-10" (einmalig).
  2. Liga-Gate vs lynx-2, 600 Schemata, Seed 2810 (einmalig).
  3. Slumbot lynx-2@500 bis 20000 Hände, dann Kandidat 10000 Hände (6 Worker, nacheinander).
- Live-Standard wird nur umgestellt, wenn beide Bestätigungen bestanden sind.

## 01:35 Kontrolle
- Gate @900 gegen lynx-3-300: +0,1 % [−4,4; +4,6] nicht bestanden.
- Training läuft, It 1032 (Abschnitt bis 1200), kein Traceback. RAM frei 1,5 GB.
- best.json jetzt @1000, Mittel +2,22 vs lynx-2@500: mensch480 +9,6 [4,5; 14,6], mix960 −0,6, pokerth480 +2,9, hu480 −2,7, 10max240 +1,9.

## 02:35 Kontrolle
- Gate @1200 gegen lynx-3-300: −2,5 % [−7,0; +2,0] nicht bestanden.
- Training läuft, It 1229 (letzter Abschnitt bis 1500), kein Traceback. RAM frei 1,4 GB.
- best.json unverändert @1000 (Mittel +2,22 vs lynx-2@500).

## 03:35 Kontrolle
- Training läuft, It 1446/1500, kein Traceback. RAM frei 1,3 GB. best.json @1000 (+2,22).
- Gate @1500 steht noch aus; danach startet morgen_lynx3.sh (Kandidat derzeit lynx-3@300).
## 04:35 Kontrolle (Notiz auf C:, weil D: weg ist)
- USB-Stick POKER um 04:15:26 ausgefallen: "disk 11 Controllerfehler auf Harddisk1", Datenträger meldet "No Media". D:\ nicht lesbar.
- Training lynx-3 war bei It ~1446/1500 (03:35), letzter Checkpoint vermutlich ckpt_001440; Prozess ist beendet.
- Ohne Umstecken nicht behebbar (pnputil ohne Adminrechte verweigert). Nach Umstecken: ./train_lynx3.sh setzt am letzten Checkpoint fort, danach morgen_lynx3.sh.
- 05:35: D: weiterhin weg (No Media), warte auf Umstecken.
- 06:35: D: weiterhin weg (No Media).
- 07:35: D: weiterhin weg (No Media).
- 08:35: D: weiterhin weg (No Media).
- 09:35: D: weiterhin weg (No Media).
- 10:00: Stick wieder da. Nachtlauf war schon 03:58 fertig (vor dem Ausfall). Gate @1500 vs lynx-3-300: +2,8 % [−1,7; +7,2] nicht bestanden. morgen_lynx3.sh gestartet, Kandidat lynx-3@300.
- 10:07: Bestätigungen lynx-3@300 (vorab festgelegt, einmalig): Mensch-Tische vs lynx-2@500 +9,2 [4,8; 13,6] bestanden; Liga-Gate vs lynx-2 (Seed 2810) +6,7 [2,3; 11,0] bestanden. Live-Standard in cli.py auf lynx-3-300 umgestellt. Slumbot läuft.
- 10:35: Slumbot lynx-2@500 bei 7500/20000 Händen: roh −31,5 bb/100 [−56; −8], All-in-EV −33,4 [−56; −11].
- 11:38: Slumbot lynx-2@500 bei 15200/20000: All-in-EV −23,0 bb/100 [−41; −5]. Parallel Slumbot hus-1 (Suche, 3000 Hände). morgen_lynx3.sh läuft.
- 13:35: Slumbot lynx-3@300 8284/10000; hus-3 (Suche neu) 800 Hände +2,2 bb/100 [−108; +112]. Zieltafel lynx-3-300: mensch480 +96,8 %, Ausbeuter +2,3 %, nash240 +17,9 %, kurz240 +83,3 %. Läuft: PokerTH-Vergleich Suche vs Netz (hu480 Netz +49,6 %).

## 13:59 Ergebnisbericht Nachtlauf lynx-3 (MORGEN FERTIG)
- Gates: @300 vs lynx-2 +4,5 [+0,3; +8,6] bestanden; @600 −3,7, @900 +0,1, @1200 −2,5, @1500 +2,8 (jeweils vs lynx-3-300, nicht bestanden).
- Vorab festgelegte Bestätigungen lynx-3@300: Mensch-Tische +9,2 [4,8; 13,6] bestanden, Liga-Gate +6,7 [2,3; 11,0] bestanden → Live-Standard lynx-3-300 (umgestellt 10:07).
- Slumbot (All-in-EV): lynx-2@500 20000 Hände −26,3 [−42; −11]; lynx-3@300 10000 Hände −23,0 [−45; −1].
- Kontroll-Cron gelöscht.
