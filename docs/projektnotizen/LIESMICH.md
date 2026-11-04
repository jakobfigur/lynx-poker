# Poker Collector – Stand 25.10.2026

Visuelle Erfassung von PokerTH-Web-Partien: Bildschirm → Erkennung → Journal mit Belegen →
Handrekonstruktion → unabhängiger Vergleich mit dem PokerTH-Export → Baseline-Empfehlung.
Plan und Prinzipien: `PROJEKTUEBERGABE.md`. Dieses Dokument beschreibt, was **gebaut** ist.

Alles läuft vom Stick: Python 3.12, alle Pakete und ein Offline-Paketcache liegen unter `tools\`.
Nichts wird auf dem Rechner installiert. Der Laufwerksbuchstabe ist egal.

## Schnellstart

Im Ordner des Sticks eine Eingabeaufforderung öffnen:

```
pc.cmd calibrate C:\Pfad\screenshot.png      Screenshot prüfen, Overlay-Bild mit allen Erkennungen
pc.cmd analyze C:\Pfad\aufnahme.mp4          Aufnahme (OBS/Game Bar) auswerten -> neue Sitzung
pc.cmd windows PokerTH                       Fenster auflisten
pc.cmd live --window "PokerTH Web"           Live mitlaufen: startet/stoppt Sitzungen automatisch
pc.cmd live --window "PokerTH Web" --advice  dazu Baseline-Empfehlung, wenn du dran bist
pc.cmd reconstruct last                      Hände der letzten Sitzung neu rekonstruieren
pc.cmd compare last C:\Pfad\export.pdb       Mit PokerTH-Export vergleichen (compare.md)
pc.cmd inspect-reference C:\Pfad\export.pdb  Schema einer Exportdatei anzeigen
pc.cmd advise C:\Pfad\screenshot.png         Baseline-Empfehlung für einen Screenshot
pc.cmd harvest-cards bild1.png bild2.png     Kartenvorlagen lernen (fragt nach dem richtigen Wert)
pc.cmd verify last                           Prüfsummen einer Sitzung kontrollieren
tests.cmd                                    alle automatischen Tests
```

Daten landen in `data\sessions\<Zeit>_<id>\`:
`observations.jsonl` (unveränderliches Ereignisjournal), `evidence\` (Bildausschnitt je Ereignis),
`video\` (Segmente + Zeitstempel je Frame, nur live), `hands.json`/`hands.md` (Rekonstruktion),
`index.sqlite`, `manifest.json` (SHA-256), `session.json` (Quelle, Versionen, Lücken, Fehler, Statistik).

Der Collector **liest nur**. Er klickt, tippt und steuert nichts fern und liest weder DOM, Netzwerk noch Speicher.

## Was gebaut ist

| Baustein | Datei | Stand |
|---|---|---|
| Tisch-/Layouterkennung (Filz, 10 Sitze, Board, Pot, Infozeile, Aktionsleiste, D/SB/BB) | `layout.py`, `profiles\pokerth_web_v1.json` | am echten Screenshot geprüft, auch bei 85 % und 125 % Fenstergröße |
| OCR (Windows-eigene Texterkennung, Cache für unveränderte Bereiche, Ersatzvarianten) | `ocr.py` | geprüft |
| Parser für Beträge, Blinds, Straße, Spiel/Hand, Aktionswörter inkl. typischer OCR-Verleser | `parse.py` | Unit-Tests |
| Kartenerkennung (offen / Rückseite / leer, Rang, Farbe, lernbare Vorlagen) | `cards.py` | 6♠ 9♥ erkannt; ♦ und ♣ **ungeprüft** |
| Frame-Analyse mit Konfidenz, Rohwert, Bildbereich, Methode je Feld | `analyzer.py` | am Screenshot: alle Felder richtig |
| Zeitliche Stabilisierung, kurzlebige Werte als „transient“ protokolliert | `stabilize.py` | Unit-Tests |
| Journal, Belegbilder, SQLite-Index, Manifest | `journal.py` | Ende-zu-Ende-Test |
| Handrekonstruktion (Blinds, Fold/Check/Call/Bet/Raise, Straßen, Gewinner, Lücken, Widersprüche, Stackbilanz) | `reconstruct.py` | synthetische Hände; **nicht** an echter Partie geprüft |
| Quellen: Video, Bildordner, Live-Fenster; segmentierte Aufnahme | `capture.py` | Recorder getestet; Live-Schleife Rauchtest |
| Automatische Sitzungen (Tisch erkannt → Aufnahme, weg → Ende), Analyse-Thread mit Rückstau | `pipeline.py` | **nicht** an echter Live-Partie getestet |
| Import PokerTH-Log (SQLite) | `reference.py` | nur gegen selbst gebaute Testdatei – **Schema/Kartencodierung ungeprüft** |
| Feldweiser Vergleich (Precision/Recall, Betragssemantik, Sichtbarkeit) | `compare.py` | Unit-Tests |
| Baseline-Empfehlung (Equity vs. zufällige Hände + Pot Odds, mit Annahmen) | `advisor.py`, `poker.py` | Unit-Tests |

Messwerte am Screenshot (1905×980): erste Analyse ca. 200 ms, unveränderte Frames ca. 40 ms.

## Ehrliche Grenzen

- **Nur ein Screenshot** (Preflop, Hand 1) war bisher Grundlage. Flop/Turn/River-Karten, Showdown, Aktionsbeschriftungen
  an den Plätzen, All-in, Side Pots, Sitzwechsel: Code ist da, aber am echten Bild **nicht gesehen**.
- **Board-Slot-Positionen** stammen aus den leeren Slots; wie offene Boardkarten genau aussehen, ist unbekannt.
- **Kartenfarben**: Karo/Kreuz über eine Formheuristik, ungetestet. Abhilfe: `harvest-cards` mit echten Screenshots.
- **Live-Aufnahme** nutzt einen Bildschirmausschnitt (mss). Liegt ein anderes Fenster über PokerTH, würde dessen
  Inhalt aufgenommen. Deshalb wird standardmäßig nur aufgenommen, wenn das Fenster im Vordergrund ist; sonst Lücke.
  Echte Fensteraufnahme unabhängig von Überdeckung: Windows.Graphics.Capture (C#, nächster Schritt).
- **Unter ca. 80 %** der Referenzgröße (Fenster schmaler als ca. 1500 px) wird die Erkennung unzuverlässig.
- **Videocodec**: `mp4v` (OpenCV). H.264 bräuchte eine zusätzliche Bibliothek.
- **Referenzexport**: Tabellen- und Spaltennamen sowie Kartencodierung (0–51, Farben d,h,s,c) stammen aus der
  PokerTH-Desktop-Quelle. Ob der Web-Client genau so exportiert, zeigt erst `inspect-reference` an einer echten Datei.
- **Baseline-Empfehlung** ist keine Strategie: Gegner als Zufallshände, keine Ranges, keine Zukunftseinsätze.

## Was als Nächstes gebraucht wird (Testdaten)

1. Eine **Bildschirmaufnahme** (Game Bar: Win+Alt+R oder OBS) von 10–20 Händen, PokerTH-Fenster maximiert,
   mit Fold, Check, Call, Bet, Raise, Flop/Turn/River und mindestens einem Showdown.
2. Den **Handverlauf-Export genau dieser Sitzung** (getrennt ablegen).
3. Ein paar **Screenshots** mit offenen Boardkarten aller vier Farben, für `harvest-cards`.
4. Danach: `pc.cmd analyze aufnahme.mp4`, dann `pc.cmd compare last export.pdb` → erste echte Messzahlen.
   Kalibrierungsaufnahmen und Testaufnahmen getrennt halten.

## KI-Teil: Simulator, Bots, Bewertung (Stufen 1–3)

Code: `collector\src\pokercollector\ai\`

```
pc.cmd sim agents                                   verfügbare Bots
pc.cmd sim match --hands 500                        Bots gegeneinander (Duplicate), Ergebnis in data\sim\
pc.cmd sim match --agents tag,tag:tag2,random --hands 1000 --show 3
pc.cmd sim hand --agents tag,station,maniac --seed 5   eine Hand mit Verlauf
pc.cmd sim review last --agent tag                  deine echten Entscheidungen einer Sitzung vs. Bot
pc.cmd sim tournament --tournaments 30              Sit&Go-Turniere wie PokerTH (Duplicate)
pc.cmd sim tournament --stack 3000 --blinds 10/20 --level-hands 8 --payouts 100
pc.cmd sim pushfold --stack 10 --behind 1           Nash-Push/Fold-Raster (13x13) fuer Pusher und Caller
pc.cmd sim pushfold --overview                      Push-% fuer alle Stacks (1-25 BB) und Positionen
pc.cmd live --window "PokerTH Web" --advice --agent equity
```

| Baustein | Datei | Stand |
|---|---|---|
| **Gemeinsame Schnittstelle** `Observation` → `Action` (nur Sichtbares, Raise = „auf“-Betrag) | `ai/observation.py` | Basis für alles |
| **Regel-Engine** No-Limit Hold'em 2–10 Spieler: Blinds, Heads-up-Reihenfolge, Mindest-Raise, kurzes All-in eröffnet nicht neu, Side Pots, ungerade Chips, nicht gecallte Chips zurück | `ai/engine.py` | 18 Regeltests inkl. 600 Zufallshände mit Chip-Erhaltung |
| **Preflop-Tabelle**: Equity aller 169 Starthände gegen 1–9 Gegner | `ai/tables.py`, `ai/preflop_equity.json` | Abweichung von bekannten Werten < 1 Prozentpunkt |
| **Bots**: random, caller, equity (Baseline), station, rock, tag, lag, maniac | `ai/agents.py` | liefern nur erlaubte Aktionen (Test), reproduzierbar |
| **Bewertung**: Duplicate-Matches, bb/100 mit 95-%-Intervall, VPIP/PFR/Aggression/WTSD/W$SD | `ai/evaluate.py` | Tests: identische Bots = exakt 0, Zufallsbot verliert belastbar |
| **Brücke zum Collector**: rekonstruierte Hand → Entscheidungspunkte; Live-Zustand → Observation | `ai/replay.py` | an synthetischer Hand getestet |
| **Turniermodus**: gleicher Startstack, Blinds verdoppeln alle N Hände (oder feste Liste), Ausscheiden, Platzierung (gleichzeitig Ausgeschiedene: größerer Stack besser, Gleichstand geteilt), Auszahlung, Duplicate-Turniere, ROI mit Intervall | `ai/tournament.py` | 9 Tests |
| **Turnierverhalten der Bots**: Push/Fold bei kurzem Stack (Schwelle je Stil), Turnierinfo im Spielerblick (Stufe, Spieler übrig, Durchschnittsstack) | `ai/agents.py` | getestet |
| **Equity-Matrix** aller 169×169 Starthand-Paarungen mit exakten Kartenblocker-Gewichten (4000 Stichproben je Paar) | `ai/pushfold.py`, `ai/hand_vs_hand.json` | AA–KK 82 %, 22–AKo ~52 %, AKo–AA ~7 % geprüft |
| **Nash-Push/Fold-Tabelle**: 1–25 BB, 1–8 Spieler dahinter, Push- und Call-Ranges je Position | `ai/pushfold.py`, `ai/pushfold_nash.json` | Heads-up exakt (Ausnutzbarkeit < 0,001 BB/Hand); 10 BB: SB pusht 58,3 %, BB callt 37,4 % |

Erstes Kräftemessen (3000 Hände, Seed 1): tag +140 bb/100 (belastbar), lag +51, rock +36, equity +20,
maniac −62, station −185 (belastbar). Die übrigen Unterschiede sind bei dieser Handzahl noch nicht belastbar.
Tempo: ca. 50–135 Hände/s je nach Bots (der Equity-Bot rechnet am meisten).

Erstes Turnier-Kräftemessen (180 Turniere, 3000 Chips, 10/20 verdoppelt alle 10 Hände, 50/30/20): rock +57 % ROI,
tag +39 %, lag +21 % (alle belastbar), maniac −14 %, station −25 %, random −78 %. Im Turnier gewinnt also der
enge Stil, im Cash-Game der eng-aggressive – Überleben zahlt sich bei 3 bezahlten Plätzen aus.

Push/Fold-Modell: chip EV (kein ICM). Heads-up ist das exakte Gleichgewicht. Bei mehreren Spielern dahinter ist es
das Gleichgewicht eines vereinfachten Modells (höchstens ein Caller, Caller unabhängig) – max. Ausnutzbarkeit im
Modell 0,013 BB. Die Bots nutzen die Tabelle; Stile verschieben sie (rock spielt "als hätte er 1,6× so viele BB").

Grenzen: PokerTHs genaue Blindstruktur (Verdopplung? alle wie viele Hände oder Minuten?) ist nicht geprüft;
die „↑8“-Anzeige wird live vorsichtig als „Hände bis zur Erhöhung“ gedeutet und als unsicher markiert. Push/Fold
nutzt jetzt die Nash-Tabelle (siehe oben). Die Bots sind Stil-Nachbildungen, **nicht** der echte PokerTH-Bot-Code;
ihr Abgleich mit echten PokerTH-Bots ist Stufe 4 (braucht deine Aufnahmen).

Nächste Stufen: 4 Gegnermodelle aus Aufnahmen und Nachbau der PokerTH-Bots; 5 lernender Agent (PPO-Self-Play,
später CFR); 6 Modell-Register mit Übernahme nur nach bestandener Bewertung.

## Du gegen die Bots

```
pc.cmd play                                         Sit&Go gegen tag, rock, lag, station, maniac (gewertet)
pc.cmd play --coach                                 dazu Push/Fold-Hinweise NACH deiner Entscheidung
pc.cmd play --mode cash --opponents tag             Heads-up-Cash gegen tag (Rebuy bei 0)
pc.cmd play --opponents tag,tag:tag2,maniac --stack 1500
pc.cmd play-stats                                   deine bb/100, Spielstil, Turnierplätze, Push/Fold-Fehler
```

Eingaben: `f` Fold · `c` Call/Check · `k` nur Check · `r 120` Raise auf 120 · `r` Mindest-Raise · `p` Pot ·
`a` All-in · `?` Hilfe · `q` Ende. Du siehst nur, was ein Spieler am Tisch sieht; fremde Karten nur im Showdown.
Jede Hand wird in `data\play\` gespeichert. Gewertete Turniere gehen mit Platzierung in die Liga (dein Rating).

## Liga, Rating, Benchmark

```
pc.cmd league show                                  Tabelle + Verlaufsgrafik data\league\report.html
pc.cmd league run --rounds 30                       Ligaspiele (Duplicate-Sit&Go) zwischen allen aktiven Bots
pc.cmd league add tag-v2 "tag?push_bb=15&bluff=0.15"   neue Bot-Version eintragen
pc.cmd league bench [name]                          Benchmark gegen feste Gegner (Cash + SNG)
pc.cmd league retire tag-v1                         aus automatischen Runden nehmen
```

Metriken:
- **Rating** (Weng-Lin/Plackett-Luce wie OpenSkill, Elo-ähnliche Skala, Start 1500 ± 400): Entwicklungskurve.
  „sicher“ = Rating − 3σ; danach wird sortiert.
- **Benchmark** gegen feste Gegner mit festem Seed: bb/100 (Cash) und ROI (SNG) mit 95-%-Intervall – über
  Versionen vergleichbar, driftet nicht.
- **Push/Fold-Verlust**: verschenkte BB je Kurzstack-Entscheidung (≤ 15 BB) gegenüber Nash, 0 = perfekt.
- Spielstil (VPIP/PFR/Aggression) im Benchmark.

Erste Liga (30 Spiele): rock > tag > lag > equity > maniac ≈ station > random. Push/Fold-Verlust zeigt eine
konkrete Schwäche: tag schaltet erst bei 12 BB auf Push/Fold (0,05 BB/Situation verloren), lag bei 15 BB (0,004).
Kandidat zum Ausprobieren: `league add tag-v2 "tag?push_bb=15"`.

## Selbstverbesserung (Stufe 5, Schritt 1)

```
pc.cmd train cem                                    Stil-Parameter optimieren + Aufnahmepruefung + ggf. Liga
pc.cmd train cem --generations 15 --start lag --champion tag
pc.cmd train cem --resume data\train\<ordner>       abgebrochenes Training fortsetzen
pc.cmd train gate "tag?push_bb=15" --champion tag   beliebige Variante pruefen
pc.cmd train cem --opponents fixed                  alter Modus: immer derselbe feste Pool
```

Ablauf: Cross-Entropy-Methode über 10 Stil-Parameter (VPIP, PFR, Value-/Raise-Schwellen, Call-Toleranz, Bluff,
Einsatzgrößen, Push/Fold-Schwelle und -Faktor). Jeder Kandidat spielt Duplicate-Sit&Gos; alle Kandidaten einer
Generation bekommen dieselben Karten und dieselben Gegnertische.

**Gegner (Standard `--opponents league`):** Für jedes Kartenschema wird ein eigener Tisch mit 5 Gegnern aus allen
aktiven Ligabots gezogen. Stärkere (höheres Rating) kommen öfter dran, schwache nie ganz selten (mind. Gewicht 0,1),
und in 20 % der Tische sitzt der aktuelle Trainingsstand selbst mit (Self-Play). Neue `opt-...`-Bots werden so
automatisch zu Trainingsgegnern der nächsten Generation (Liga-Training wie bei AlphaStar). Hintergrund: opt-1,
nur gegen den festen Pool trainiert, war dort im Turnier am besten, lag in der Liga aber unter tag
(Überanpassung). In der Aufnahmeprüfung sitzt der Titelverteidiger nicht als Gegner am Tisch. Danach
**Aufnahmeprüfung** auf 48 frischen Kartenschemata, gepaart gegen den Titelverteidiger: nur bei belastbarem
Vorsprung (95-%-Intervall der Differenz > 0) wird der Bot als `opt-...` in die Liga eingetragen.
Beispiel: `tag?push_bb=15` fiel durch (−4,6 % ROI, Intervall −12,8 … +3,7) – die Vermutung aus der
Push/Fold-Kennzahl hat sich nicht bestätigt.

**Regel für die Aufnahmeprüfung:** nicht so lange mit neuen Seeds wiederholen, bis sie zufällig besteht. Bei
knappem Ergebnis höchstens eine vorher festgelegte, größere Bestätigungsprüfung, und deren Ergebnis gilt.
(opt-1 kam nach einer zweiten Prüfung mit 120 Schemata in die Liga, die erste mit 48 war knapp durchgefallen.)

Verlauf:
- opt-1 (fester Pool, Start tag): Gate vs tag +8,9 % [1,1; 16,7] → Liga. Benchmark-SNG bester Bot, Liga-Rating aber
  unter tag → Überanpassung an den Pool.
- Liga-Training 1 (Start tag, 10 × 12 Kandidaten × 16 Schemata, 22 min): Gate vs rock auf 120 Schemata +5,2 %
  [−3,1; 13,4], Bestätigung auf 300 Schemata −5,3 % [−10,1; −0,5] → durchgefallen. Die Schwankung des ROI
  zwischen Generationen (+5 % … +47 %) war Kartenglück, die Tische waren gleich stark besetzt.
- Liga-Training 2 (Start rock, 24 Schemata/Generation, 36 min) → opt-2: Gate vs rock +8,5 % [1,0; 16,0], Liga
  danach nur Platz 4, Bestätigung auf 300 neuen Schemata +1,9 % [−2,2; 6,1] → wieder aus der Liga genommen
  (`league retire`). Dabei gefunden: alle Gates hatten denselben Prüfsatz (Seed 777) benutzt, der sich über
  mehrere Kandidaten abgenutzt hatte. Jetzt hat jeder Trainingslauf seinen eigenen (100000 + `--seed`).

Fazit: Mit den 10 Stil-Parametern ist das Ende der Fahnenstange etwa erreicht – rock, tag und opt-1 liegen
innerhalb weniger Prozent, weiteres Drehen an Reglern findet nur noch Rauschen. Mehr Spielstärke braucht einen
Bot, der seine Entscheidungen selbst lernt (nächster Schritt).

Lange Läufe halten den Rechner wach (Standby würde den USB-Stick trennen; ist einmal passiert). Abschalten mit
`pc.cmd --allow-sleep ...`. Das Training speichert nach jeder Generation seinen Zustand (`--resume`).

Grenze: Optimiert wird gegen Bots – ob es gegen Menschen trägt, zeigen erst Partien gegen dich und echte
PokerTH-Aufnahmen. Nächster Schritt: neuronaler Agent (Self-Play), der dieselbe Pipeline nutzt.

## Lernender Bot (neuronales Netz, Stufe 5 Schritt 2)

```
pc.cmd train bc --teacher rock --run nn-1             Lehrer-Bot nachahmen -> data\rl\nn-1\ckpt_000000.pt
pc.cmd train bc --dataset pluribus --run pros-1       aus echten Haenden nachahmen (alle Spieler)
pc.cmd train bc --dataset pluribus --players Pluribus --run plu-1    nur Pluribus selbst
pc.cmd train rl --run pros-1 --iterations 200 --anchor-coef 0.3      Selbstspiel (PPO) mit Leine
pc.cmd train rl --run nn-1 --iterations 300           fortsetzen bis Iteration 300
pc.cmd data pluribus                                  Pluribus-Haende einlesen -> data\datasets\pluribus.npz
pc.cmd data agree nn-1 --ckpt 0,100,200               Uebereinstimmung mit Pluribus messen
pc.cmd league add pros-bc "nn?run=pros-1@0"           Netz (Lauf@Checkpoint) in die Liga
```

**Was er sieht** (`ai/features.py`): 46 vorverdaute Zahlen statt roher Karten – Equity (Preflop-Tabelle bzw.
Monte-Carlo), Handtyp, Board-Textur, Pot Odds, Stack/Pot, effektiver Stack, Position, Raises/Aggressor,
Turnierlage. **Was er tun kann:** Fold, Check/Call, Raise ½ / 1 / 2 Pot, All-in. **Netz** (`ai/nn_agent.py`):
46 → 128 → 128 → 6 Aktionswahrscheinlichkeiten + 1 Wert. Gelernt wird mit PyTorch (CPU, liegt auf dem Stick),
gespielt mit einer numpy-Kopie (schnell, 12 Prozesse). Gespielt wird gemischt, Zufall aus der Situation abgeleitet
(Duplicate-fair).

**Wie er lernt** (`ai/rl.py`): (1) Nachahmung eines Lehrers oder eines Datensatzes → Checkpoint 0. (2) PPO: je
Iteration 96 Sit&Gos gegen Tische aus der Liga und frühere Versionen von sich (30 %), Belohnung = Chip-Änderung je
Hand. Optional **Leine** (`--anchor-coef`, piKL wie bei Metas Cicero): Strafe für Abweichung vom Anker (Standard:
eigener Checkpoint 0), nur bei Stacks ≥ 25 BB, weil der Pluribus-Anker nur dort Erfahrung hat.

**Ablage:** `data\rl\<lauf>\` – `config.json`, `bc.json`, `log.jsonl` (je Iteration), `eval.jsonl` (alle 10 It:
ROI gegen festen Pool + Pluribus-Übereinstimmung), `ckpt_<It>.pt` (je ~100 KB), `state.pt` (Fortsetzen),
`gate_<It>.json`. Gespielte Hände werden nicht gespeichert.

**Daten:** PHH-Datensatz der Univ. Toronto (MIT), github.com/uoftcprg/phh-dataset. Geholt ist nur der
Pluribus-Teil nach `data\external\phh-dataset` (10 000 Hände Pluribus gegen Profis, 6-max, 100 BB, **alle Karten
bekannt**). Alle 10 000 Hände laufen durch unsere Engine mit identischen Endstacks (±1 Chip bei geteilten Pots) –
ein unabhängiger Beleg, dass die Engine stimmt. 91 356 Entscheidungen, davon 15 169 von Pluribus.
HandHQ (21,6 Mio. echte Online-Hände 2009) zeigt Karten nur beim Showdown → nicht zum Nachahmen, aber für
Spielerprofile echter Gewinner (nächster Schritt).

Ergebnisse bisher:
- **nn-1** (rock nachgeahmt, PPO ohne Leine): gegen den festen Pool von +23 % auf +84 % ROI, aber Aufnahmeprüfung
  gegen rock nach 100 It −3,7 %, nach 300 It −8,5 % → nicht bestanden. Pluribus-Übereinstimmung fiel von 63 %
  auf 13 %: Er foldet kaum noch und erhöht fast immer – gelernt hat er, die Schwächen unserer Bots auszunutzen,
  nicht gutes Poker. Gegen den eigenen Startpunkt war die Verbesserung echt (+23 % ohne rock am Tisch).
- **plu-1 / pros-1** (Pluribus bzw. alle Spieler nachgeahmt): 84 % Übereinstimmung mit Pluribus; im Sit&Go
  gegen rock −9,2 % bzw. −3,8 % (nicht signifikant) – Pluribus kennt kein Kurzstack-Turnierspiel.

## Prüfstand, Tempo und CFR

```
pc.cmd bench run rock                                  Bot auf den Prüfstand (Liga-Name oder Spezifikation)
pc.cmd bench run "nn?run=pros-1@200" --name pros-1@200 --exploit     inkl. Ausbeuter-Test
pc.cmd bench show                                      Tabelle -> data\bench\report.md
pc.cmd train exploit "nn?run=pros-1@200"               nur Ausbeuter-Test
pc.cmd train cfr --run cfr-1 --rounds 400              Gleichgewicht per Monte-Carlo-CFR (Pluribus-Verfahren)
```

**Prüfstand** (`ai/bench.py`): feste Testsets, die sich nie ändern – `fest48` (48 Sit&Gos gegen den festen Pool),
`mix96` (96 Sit&Gos an gemischten, stärkeren Tischen inkl. opt-1 und Profi-Nachahmer), `cash` (300 Duplicate-Hände,
bb/100), `pluribus` (Übereinstimmung), optional `exploit`. In der Tabelle steht je Testset die **gepaarte
Differenz zu rock** auf denselben Karten. Ein Durchlauf dauert ca. 40 s. PPO-Läufe stellen sich alle 50
Iterationen selbst auf den Prüfstand, CFR-Läufe alle 25 Runden. Für die Aufnahme in die Liga gilt weiter die
Aufnahmeprüfung mit frischen Karten.

**Tempo:** Profil zeigte 95 % der Zeit in der Monte-Carlo-Equity (Python-Handbewertung ~70 µs). Neu:
`fastpoker.py` mit numba (Maschinencode), gleiche Rangfolge wie vorher (Test über 40 000 Vergleiche).
Ergebnis: ~37 → ~3100 Hände/s je Kern (**~85×**), PPO-Iteration 11 s → 1 s, Prüfstand 40 s.

**CFR** (`ai/cfr.py`): Selbstspiel, bei dem an jeder eigenen Entscheidung alle Aktionen durchgespielt werden
(Kopie des Spielstands); Aktionen, die besser gewesen wären, werden öfter gespielt. Der Durchschnitt nähert
sich einem Gleichgewicht – schwer auszunutzen, egal gegen wen. Wie Pluribus: External Sampling, Linear CFR,
Abstraktion (Straße, Handstärke-Klasse, Position, Spieler, Pot Odds, Stack, Raises, Aggressor). Hände mit
2–6 Spielern und 3–150 BB. Ablage `data\rl\<lauf>\cfr_state.npz` (Fortsetzen), `cfr_avg.npz` (Strategie).
Liga: `cfr?run=<lauf>`. **Nicht zwei Trainings gleichzeitig starten:** jedes nutzt alle Kerne mit eigenen
Prozessen; zusammen mit dem Prüfstand reichten 16 GB RAM nicht (Abbruch „Nicht genügend Systemressourcen“,
26.10.). Ursache war zusätzlich ein Ladefehler (komprimierte Arrays je Eintrag neu entpackt), behoben. Unterschied zu PPO: PPO beutet die aktuellen Gegner aus, CFR sucht Robustheit.

Erste Prüfstand-Tabelle (mix96, Δ zu rock): nn-1@100 +19 (aber Pluribus-Übereinstimmung 15 %, nach 300 It
−3 → Überanpassung), pros-1 mit Leine @0 −20 → @100 +3 → @200 +8 bei stabil 80 % Pluribus-Übereinstimmung.

## Robustheit, Ranges und Suche (Stand 26.10. abends)

```
pc.cmd train rl --run X --random-share 0.3 --exploit-every 50     Zufalls-Gegner + Ausbeuter im Training
pc.cmd bench run "search?bp=pros-2@300,worlds=16" --name such-2   Netz + Suche auf den Prüfstand
```

**Ausbeuter-Test** (gezielt gegen den Prüfling trainierter Bot, ROI gegen 5 Kopien; je kleiner, desto robuster):
pros-2 **+3,8 %** [−7; +15] – rock **+100 %** [+86; +115] – CFR-Tabelle (Runde 200) +69 % [+59; +78].
pros-2 ist also nicht nur stärker als rock, sondern kaum auszunutzen.

**Zufalls-Gegner** (`--random-share`): Plätze werden mit Stil-Bots mit gewürfelten Werten besetzt (Calling-Station
bis Dauerbluffer, `optimize.RANDOM_SPACE`). **Ausbeuter im Training** (`--exploit-every`): alle N Iterationen lernt
ein Ausbeuter gegen den aktuellen Stand und wird danach Gegner (PSRO/AlphaStar-Prinzip, Richtung Gleichgewicht);
Ausnutzbarkeit steht in `eval.jsonl`, Ausbeuter unter `<lauf>\expl-<It>\`.

**Ranges** (`ai/ranges.py`): je Gegner Gewichte über 1326 Startkombinationen, verschoben durch seine Aktionen
(Raise/3-Bet/Call preflop, Bet/Call/Check je Board-Stärke). Equity gegen diese Ranges per numba-Monte-Carlo.
Beispiel: QJ gegen Open + 3-Bet: 41 % gegen Zufallshände, 23 % gegen die Ranges. **Merkmale feat-2** = feat-1 + 3
Range-Merkmale; jedes Netz speichert seine Version und spielt mit ihr (alte Netze unverändert). Datensätze je
Version: `pluribus.npz` (feat-1), `pluribus-feat-2.npz`.

**Suche** (`ai/search.py`, Stufe 1): `world_from_obs` baut aus Beobachtung + gezogenen Gegnerkarten einen exakten
Spielstand (getestet gegen echte Stände). `SearchAgent`: je erlaubter Aktion in 16–24 „Welten“ (Gegnerkarten aus
den Ranges) die Hand mit dem Netz als Strategie für alle zu Ende spielen; gleiche Welten für alle Aktionen;
die Netz-Wahl wird nur bei klarem Vorteil (> 2 Standardfehler) überstimmt. ~0,2 s je Entscheidung.
Stufe 2 (wie Pluribus): Teilspiel per CFR lösen, Gegner dürfen am Horizont zwischen Fortsetzungen wählen.

## Training auf einem Linux-Server

```
# einmalig auf dem Server
curl -LsSf https://astral.sh/uv/install.sh | sh
# Projektordner OHNE tools/ und ohne collector/.venv kopieren, data/ nach Bedarf (rl/, datasets/, league/)
chmod +x pc.sh && ./pc.sh --help
nohup ./pc.sh train deepcfr --run dcfr-2 --iterations 300 > dcfr-2.log 2>&1 &
```

Tempo-Faustregel: Unsere Trainings nutzen alle Kerne voll. Ein VPS mit 4 *geteilten* vCPUs ist etwa ⅓ so schnell
wie der Laptop (10 Kerne) und wird bei Dauerlast gedrosselt – gut für lange, geduldige Läufe ohne Laptop,
nicht für Tempo. Für Tempo: dedizierte Kerne (Hetzner CCX/AX), stundenweise mieten. RAM: ca. 0,5 GB je
Prozess + Deep-CFR-Puffer ~1 GB; 8 GB reichen für 4–6 Prozesse.

## Architektur (Datenfluss)

```
Quelle (Video | Bilder | Fenster)
  -> analyzer.FrameAnalyzer: layout + OCR + Karten -> TableSnapshot (Feld -> Wert, Konfidenz, Rohwert, Rechteck)
  -> stabilize.Stabilizer: change / transient / unknown Ereignisse
  -> journal.Session: observations.jsonl (+ Belegbild), Video-Segmente
  -> reconstruct.reconstruct(journal) -> hands.json     (jederzeit neu berechenbar)
  -> compare.compare(hands, reference)  -> compare.json/.md (Export nur hier)
  -> advisor.advise(Zustand)            -> Empfehlung + Annahmen
```

Sitznummern: 0 = eigener Platz unten Mitte, dann im Uhrzeigersinn (= Aktionsreihenfolge) bis 9.

## Entwicklung

Code: `collector\src\pokercollector\`, Tests: `collector\tests\`, Testbild: `collector\testdata\`.
Neues Tischlayout: Profil-JSON kopieren, Anker/Regionen anpassen, mit `pc.cmd --profile mein.json calibrate bild.png` prüfen.
