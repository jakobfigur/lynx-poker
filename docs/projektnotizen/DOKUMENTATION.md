# Poker-Projekt „Lynx“: Gesamtdokumentation

Stand: **28.10.2026, ca. 23:30 Uhr**, Nachtrag 8.6 vom 29.10. 02:00. Verfasst aus Code, Daten und Protokollen auf dem Stick (`<Projektordner>`), den Arbeitsnotizen und dem Sitzungsverlauf seit dem 25.10.2026.

Diese Doku beschreibt den tatsächlichen Stand. Wo etwas nicht gemessen oder nicht geprüft ist, steht das ausdrücklich dabei. Ältere Dokumente:
- `PROJEKTUEBERGABE.md`: ursprünglicher Plan und Regeln (25.10.)
- `LIESMICH.md`: Bedienungsanleitung, Stand bis 26.10. abends
- `ZIELE.md`: die fünf Benchmarks
- `data/rl/NACHTPROTOKOLL.md`: Protokolle der beiden Nachtläufe

---

## Inhalt

1. [Ziel, Regeln und Grundsätze](#1-ziel-regeln-und-grundsätze)
2. [Hardware, Umgebung, Ordnerstruktur, Bedienung](#2-hardware-umgebung-ordnerstruktur-bedienung)
3. [Der Collector: visuelle Erfassung](#3-der-collector-visuelle-erfassung)
4. [Die KI: Engine, Bots, Netze, Training, Suche](#4-die-ki-engine-bots-netze-training-suche)
5. [Live-Betrieb: Vorschläge, Lynx-Leiste, Turnier-Erkennung](#5-live-betrieb-vorschläge-lynx-leiste-turnier-erkennung)
6. [Benchmarks: Methodik und alle Ergebnisse](#6-benchmarks-methodik-und-alle-ergebnisse)
7. [Chronik: was versucht wurde, auch Fehlschläge](#7-chronik-was-versucht-wurde-auch-fehlschläge)
8. [Aktueller Stand, Einschätzung, Schwächen, Roadmap](#8-aktueller-stand-einschätzung-schwächen-roadmap)
9. [Anhang: Begriffe, Dateien, Spezifikationen](#9-anhang-begriffe-dateien-spezifikationen)

---

## 1. Ziel, Regeln und Grundsätze

### 1.1 Ziel

Das Projekt hat drei Teile:

1. **Collector:** Er erfasst PokerTH-Web-Partien im Browser **ausschließlich visuell**, also über das, was auf dem Bildschirm zu sehen ist. Er rekonstruiert daraus die Hände, belegt jedes Detail und prüft das Ergebnis unabhängig gegen das PokerTH-Log. Genau das ist das Experiment: Geht es nur über das Bild?
2. **Lynx:** eine eigene Poker-KI, die „maximal gut“ werden soll. Sie wird im Simulator trainiert und soll in PokerTH gegen Menschen gewinnen.
3. **Live-Berater:** Während Jakob selbst spielt, zeigt Lynx Handlungsvorschläge an (Fold, Check, Call, Raise auf X). Jakob entscheidet und klickt selbst.

Lynx soll allgemein stark werden, nicht nur gegen einen bestimmten Gegner. Slumbot ist ausdrücklich nur Maßband und kein Trainingsziel (Vorgabe vom 28.10.).

### 1.2 Feste Regeln (aus `PROJEKTUEBERGABE.md`, vom Nutzer bestätigt)

| Regel | Umsetzung |
|---|---|
| Keine Browser-Fernsteuerung, keine automatischen Klicks, Tasten, Wetten oder Aktionen | Der Collector liest nur Bildschirmpixel (mss). Die Leiste ist reine Anzeige und nimmt nie den Fokus. Im Code gibt es keine Eingabe-Funktion. |
| Kein DOM, kein Netzwerk, kein Speicher, kein interner Spielzustand als Quelle | Die Quelle ist ausschließlich das Bild: Windows-OCR, Formvergleich, Farben. |
| Das PokerTH-Log ist nur unabhängige Referenz | Es wird nur in `compare.py` und `reference.py` gelesen, nie von der Erfassung. Für das Training wird es nie verwendet. Die Kartenvorlagen stammen bewusst nicht aus dem Export. |
| Gegnerkarten nie schätzen und als bekannt ausgeben | Die Observation enthält nur Sichtbares. Ranges sind Verteilungen, keine Fakten. |
| Lücken melden statt erfinden | Unsichere Werte stehen in `Observation.uncertain`, Lücken und Widersprüche in jeder Hand. |
| Alles bleibt lokal | Daten liegen auf dem Stick, ein Backup unter `C:\Poker-Backup\Poker-Projekt-Windows`. Als externe Dienste sind nur HandHQ- bzw. PHH-Daten (Download) und die Slumbot-API erlaubt, beide ausdrücklich freigegeben. |

### 1.3 Methodische Grundsätze, die sich bewährt haben

- **Gepaart messen:** Zwei Bots spielen dieselben Karten an denselben Tischen in allen Sitzrotationen. Verglichen wird die Differenz je Schema, das nimmt den größten Teil des Kartenglücks heraus.
- **95-%-Intervall immer angeben.** „Besser“ gilt nur, wenn die untere Grenze der Differenz über 0 liegt.
- **Aufnahmeprüfung (Gate) nicht wiederholen, bis sie zufällig besteht.** Ist das Ergebnis knapp, gibt es höchstens eine vorab festgelegte, größere Bestätigung, und deren Ergebnis gilt. Das wurde nach den Erfahrungen mit opt-1 und opt-2 eingeführt (Abschnitt 7).
- **Jeder Trainingslauf hat einen eigenen Prüfsatz-Seed** (100000 + Trainings-Seed). Vorher teilten alle Gates Seed 777, und dieser Prüfsatz „nutzte sich ab“.
- **Feste Prüfstand-Sets zum Verfolgen, frische Karten zum Entscheiden.** Wer auf einem oft angeschauten Set vorn liegt, kann Glück mit genau diesen Karten haben.
- **Neuer Live-Standard nur nach bestandenen Bestätigungen:** Liga-Gate plus Mensch-Tische, beide vorab festgelegt und einmalig.
- **Ergebnisse einzelner Hände sind nie Trainingslabel.**

---

## 2. Hardware, Umgebung, Ordnerstruktur, Bedienung

### 2.1 Hardware und System

| | |
|---|---|
| Laptop | Intel i5-1335U (10 Kerne: 2 P + 8 E, 12 Threads), 16 GB RAM, **keine GPU** |
| System | Windows 11 Pro (10.0.26200), PowerShell 5.1 und Git Bash |
| Stick | Intenso cMobile Line, Label „POKER“, exFAT, meist Laufwerk `D:` |
| Browser | Google Chrome, Fenster „PokerTH Web Client — Free Texas Hold’em in Your Browser“ |
| Später möglich | Hetzner-VPS (4 geteilte vCPU, 8 GB, etwa ⅓ so schnell wie der Laptop), ein neues ThinkPad (4 Kerne, 8 Threads, 16 GB) |

### 2.2 Laufzeitumgebung (alles auf dem Stick, nichts installiert)

- **Python:** `tools\python\cpython-3.12.12-windows-x86_64-none\python.exe`, portabel
- **uv:** `tools\uv\uv.exe` mit Offline-Cache `tools\uv-cache`
- **Projekt-venv:** `collector\.venv` (Python 3.12)
- **Abhängigkeiten** (`collector/pyproject.toml`): numpy ≥ 2.1, opencv-python, mss, torch (CPU-Index), numba, pillow, winrt-Pakete für Windows.Media.Ocr; pytest für die Tests
- **Startskripte:**
  - `pc.cmd`: alle Befehle, nutzt `uv run --no-sync`, damit laufende Trainings nicht gestört werden
  - `tests.cmd`: alle Tests
  - `sync.cmd`: Pakete aktualisieren, nur ausführen, wenn nichts läuft
  - `pc.sh`: Linux bzw. Server

### 2.3 Ordnerstruktur

```
<Projektordner>\
  PROJEKTUEBERGABE.md   Plan & Regeln (25.10.)
  LIESMICH.md           Bedienung (bis 26.10.)
  ZIELE.md              die 5 Benchmarks
  DOKUMENTATION.md      dieses Dokument
  pc.cmd / tests.cmd / sync.cmd / pc.sh
  train_*.sh, night*.sh, morning.sh, morgen_lynx3.sh, slumbot_long.sh, measure.sh   Lauf-Skripte der Trainings
  collector\
    pyproject.toml
    src\pokercollector\           Collector (Erfassung)  ~25 Module
      ai\                         KI  ~35 Module
      profiles\pokerth_web_v1.json  Tischprofil
    tests\                        31 Testdateien, 171 Tests (alle grün, 28.10. abends)
    testdata\                     Testbild(er)
  data\
    sessions\<UTC-Zeit>_<id>\     aufgezeichnete PokerTH-Sitzungen
    rl\<lauf>\                    Trainingsläufe (Checkpoints, Logs, Gates)
    bench\                        Prüfstand: results.jsonl, report.md, slumbot\*.jsonl, *.txt
    league\                       Liga: players.json, games.jsonl, report.md/html
    humans\                       HandHQ-Auswertung, Mensch-Bots (mensch-25nl.json)
    datasets\                     pluribus.npz, pluribus-feat-2.npz
    external\phh-dataset          Pluribus-Teil des PHH-Datensatzes
    ziele\pokerth.jsonl           echte PokerTH-Turniere (Ziel 1)
    live\leiste.json              Position der Lynx-Leiste
    sim\, play\, train\, templates\
  tools\                          Python, uv, Cache
```

Codeumfang: etwa **13.800 Zeilen** Python in `src` (Collector etwa 4.800, KI etwa 9.000), dazu die Tests.

### 2.4 Wichtigste Befehle

**Collector und Live:**
```
pc.cmd windows PokerTH                         Fenster auflisten
pc.cmd live --leiste                           Live: Erfassung + Lynx-Vorschläge in der Leiste (+ Ton)
pc.cmd live --leiste --still                   ohne Ton
pc.cmd live --leiste --mischen                 Vorschlag aus gemischter Strategie statt wahrscheinlichster Aktion
pc.cmd live --leiste --kein-eintrag            Turnierende nicht automatisch eintragen
pc.cmd live --hwnd <Nummer>                    bestimmtes Fenster
pc.cmd live --advice --agent <Bot>             Vorschläge nur in der Konsole, anderer Berater
pc.cmd leiste-demo [--still] [--sekunden N]    Leiste ohne Tisch vorführen
pc.cmd live-replay <sitzung>                   Aufnahme wie live abspielen (Vorschläge + Gegnermodell)
pc.cmd analyze aufnahme.mp4                    Video auswerten -> neue Sitzung
pc.cmd reconstruct last                        Hände neu rekonstruieren
pc.cmd compare last export.pdb                 gegen PokerTH-Log prüfen (compare.md)
pc.cmd inspect-reference export.pdb            Schema einer Logdatei zeigen
pc.cmd calibrate screenshot.png                Erkennung an einem Bild prüfen (Overlay)
pc.cmd harvest-cards bild1.png ...             Kartenvorlagen lernen
pc.cmd verify last                             Prüfsummen
```

**Simulation, Liga, Training:**
```
pc.cmd sim agents | match | hand | tournament | pushfold | review
pc.cmd play [--coach]                           selbst gegen Bots spielen (Terminal)
pc.cmd league show | run | add | retire | bench
pc.cmd train bc | rl | cem | gate | cfr | deepcfr | exploit | humans-fit
pc.cmd data pluribus | humans | agree
```

**Prüfstand und Ziele:**
```
pc.cmd bench run <bot> --sets mensch480,praezise [--exploit] [--name X]
pc.cmd bench show                               Tabelle -> data\bench\report.md
pc.cmd bench compare A B                        gepaarter Vergleich über alle gemeinsamen Sets
pc.cmd bench slumbot "<spec>" --name X --hands N --workers 4    gegen Slumbot (fortsetzbar)
pc.cmd bench slumbot x --name X --hands 0       nur Auswertung anzeigen
pc.cmd bench ziele <bot> [--messen] [--exploit] [--slumbot NAME]
pc.cmd bench turnier <Platz> --spieler 6 [--bot X] [--notiz "..."]   Turnier von Hand eintragen
```

Einzeltests: `cd collector && PYTHONIOENCODING=utf-8 ../tools/uv/uv.exe run --quiet --no-sync pytest -q -p no:cacheprovider tests/test_x.py`

### 2.5 Fallstricke (alle mindestens einmal aufgetreten)

| Problem | Ursache | Gegenmittel |
|---|---|---|
| **Stick fällt aus** („No Media“, Ereignis „disk 11 Controllerfehler“): 27.10. 07:10, 28.10. 04:15, 28.10. nachmittags | USB-Energiesparen. Windows trennt den Stick bei Standby bzw. schwarzem Bildschirm (Modern Standby). | Am 28.10. das **selektive USB-Energiesparen per `powercfg` für Netz und Akku abgeschaltet**. Lange Läufe halten den Rechner wach (`system.keep_awake`, SetThreadExecutionState). Nach einem Ausfall hilft nur Umstecken, `pnputil` ohne Adminrechte geht nicht. Notfalls von SSD bzw. Backup arbeiten. |
| **Speicher-Wächter von Claude Code** beendet Hintergrundjobs bei RAM-Knappheit | 16 GB reichen nicht für Training plus Prüfstand plus Slumbot plus Analyse gleichzeitig | Läufe nacheinander, Worker reduzieren (4 statt 6). Oft wird nur die Hülle beendet und die Rechenprozesse laufen weiter, deshalb die Prozessliste prüfen. Nach einem Abbruch nicht eigenmächtig neu starten. |
| **Gestoppter Monitor lief weiter** (28.10.) | `TaskStop` auf einen Monitor beendete die Kindprozesse nicht. Die Kette lief doppelt, Slumbot und PokerTH-Vergleich also zweimal parallel. | Nach dem Stoppen die Prozessliste prüfen (`Get-CimInstance Win32_Process`). |
| `&` in Bot-Spezifikationen | cmd zerlegt die Zeile | Für `hus?bp=...&iters=...` Python-Skripte nutzen. Netz-Specs ohne `&` schreiben (`nn?run=lauf@ckpt`). |
| Laufende Trainings laden Module lazy nach | Ein Code-Umbau während eines Laufs kann ihn stören | Entwicklung in der Kopie `dev/` (PYTHONPATH) oder warten, bis der Lauf fertig ist |
| Live nimmt nur im Vordergrund auf | mss fotografiert den Bildschirm. Ein überdeckendes Fenster würde mitgelesen. | Das PokerTH-Fenster muss aktiv und unverdeckt sein, sonst gibt es eine Lücke („Quelle verloren“). |
| Fenster unter ca. 1500 px Breite | Die Erkennung wird unzuverlässig (unter ca. 80 % der Referenzgröße) | Fenster groß bzw. maximiert lassen |

---

## 3. Der Collector: visuelle Erfassung

### 3.1 Datenfluss

```
Quelle (WindowSource live | VideoFileSource | ImageDirSource)            capture.py
  -> FrameAnalyzer: Layout + OCR + Karten -> TableSnapshot                analyzer.py, layout.py, ocr.py, cards.py, glyphs.py, parse.py
       (je Feld: Wert, Konfidenz, Rohwert, Bildbereich, Methode)
  -> Stabilizer: change / transient / unknown                            stabilize.py
  -> Session/Journal: observations.jsonl (+ Belegbild), Video-Segmente   journal.py
  -> Reconstructor: Hände mit Aktionen, Lücken, Widersprüchen            reconstruct.py   (jederzeit neu berechenbar)
  -> compare(hands, Referenzlog)  (nur hier wird das Log gelesen)        compare.py, reference.py
  -> live: LiveBot -> Observation -> Lynx -> Leiste                      ai/live.py, ai/replay.py, overlay.py
```

`pipeline.py` verbindet alles. Bei `LiveRunner` (live) hat die Aufnahme Vorrang: Frames gehen sofort in den Recorder, die Analyse läuft in einem eigenen Thread mit begrenzter Warteschlange. Kommt die Analyse nicht hinterher, werden **Analyse-Frames ausgelassen (gezählt), nie Videoframes**. Die Sitzung startet automatisch, wenn der Tisch stabil erkannt ist, und endet etwa 20 s nachdem er verschwindet.

### 3.2 Bausteine im Einzelnen

| Modul | Aufgabe | Technik / Details |
|---|---|---|
| `capture.py` (335 Z.) | Bildquellen, segmentierte Aufnahme | `WindowSource` per mss auf den Client-Bereich. Prüft, ob das Fenster im Vordergrund ist, sonst Lücke. Video als `mp4v` (OpenCV) in Segmenten mit Zeitstempel je Frame. Windows.Graphics.Capture (überdeckungsfest) war geplant, wurde aber nicht gebaut. |
| `layout.py` (279 Z.) | Tisch, Sitz-Panels, Board, Marker (D/SB/BB), Aktionsleiste | Sitze werden **nicht an festen Positionen** gesucht, denn PokerTH ordnet je nach Spielerzahl anders an. Erkannt werden alle Panels, das größte unten in der Mitte ist Sitz 0 (Jakob), die übrigen werden im Uhrzeigersinn um die Tischmitte nummeriert (= Aktionsreihenfolge). **SeatMemory** hält die Nummern stabil, auch wenn ein Panel verschwindet. Der Maßstab ergibt sich aus der gemessenen Panelbreite. Geprüft an 10er- (Testbild), 6er- und 4er-Tischen. |
| `ocr.py` (221 Z.) | Texterkennung | Windows.Media.Ocr über winrt, ohne Zusatzprogramm. Cache für unveränderte Bereiche, Ersatzvarianten (Vergrößerung, Kontrast). |
| `parse.py` | Beträge, Blinds, Straße, Spiel/Hand-Nummer, Aktionswörter | inklusive typischer OCR-Verleser (z. B. `$O` statt `$0`) |
| `cards.py` (306 Z.) + `glyphs.py` (80 Z.) | Kartenslot (leer/Rückseite/offen), Rang, Farbe | **Rang:** Windows-OCR liefert isolierte Einzelzeichen schlecht (gemessen: 3 von 7 Rängen). Deshalb Formvergleich gegen die 13 Ränge, gezeichnet in mehreren Standardschriften, normiert und per Korrelation verglichen, inklusive Seitenverhältnis („10“ breit, „7“ schmal). Dazu lernbare Vorlagen (`harvest-cards`). **Farbe:** rot/schwarz aus der Tinte, Form über Vorlagen oder Konturheuristik. |
| `analyzer.py` (347 Z.) | Frame → TableSnapshot | Feldschlüssel u. a. `table.found`, `info.street`, `info.game_hand`, `info.blinds`, `info.total`, `pot.total`, `board.cards`, `hero.buttons`, `seat.<n>.present/name/stack/bet/folded/active/cards/action_label/marker` |
| `stabilize.py` (120 Z.) | zeitliche Stabilisierung | Ein Wert gilt erst nach `min_frames` und `min_ms` als stabil. Kurzlebige Werte werden **nicht weggemittelt**, sondern als `transient` gemeldet. Unlesbares ersetzt einen stabilen Wert erst nach `unknown_after_ms`. |
| `journal.py` (218 Z.) | Sitzungsordner | `observations.jsonl` (append-only, unveränderlich), `evidence/` (Bildausschnitt je Ereignis), `video/segment_NNNN.mp4` + `.frames.jsonl`, `hands.json/.md`, `index.sqlite`, `manifest.json` (SHA-256), `session.json` (Quelle, Versionen, Lücken, Fehler, Statistik) |
| `reconstruct.py` (735 Z.) | regelbasierte Handrekonstruktion | State-Machine über die Feldereignisse, Details in 3.3 |
| `reference.py` (270 Z.) | Import PokerTH-Log (SQLite `.pdb`) | Tabellen Game/Player/Hand/Action laut PokerTH-Desktop-Quelle. Das Schema ist mittlerweile an echten Web-Exporten benutzt (Vergleich 26.10.), Kartencodierung 0..51 je Farbe d,h,s,c. |
| `compare.py` (281 Z.) | feldweiser Vergleich | Precision/Recall je Feld, Betragssemantik („auf“ vs. „zusätzlich“), Sichtbarkeitsklasse. Was im Log steht, aber nicht sichtbar war (verdeckte Karten), zählt nicht als Fehler. |
| `advisor.py` / `poker.py` | Baseline-Empfehlung, Handbewertung | Equity gegen Zufallshände plus Pot Odds. Bewusst die einfachste ehrliche Baseline, heute von Lynx abgelöst. |
| `fastpoker.py` (201 Z.) | schnelle Handbewertung, Monte-Carlo-Equity | numba, Karten als 0..51, Bewertung als Integer (Kategorie << 20 \| Ränge). Rangfolge identisch mit `poker.evaluate`, getestet über 40.000 Vergleiche. Etwa 85× schneller. |
| `system.py` | Standby verhindern | SetThreadExecutionState (System + Bildschirm), weil bei Modern Standby das Abschalten des Bildschirms zum Standby führt |

### 3.3 Handrekonstruktion (`reconstruct.py`, Version `reconstruct-2`)

- **Handgrenzen:** über die Handnummer (`info.game_hand`, „observed“) oder abgeleitet („inferred“). PokerTH schaltet die Handnummer um, bevor der Tisch aufgeräumt ist. Deshalb werden Sitz-Ereignisse bis zu **SETTLE_S = 2,5 s** gepuffert, bis Marker und Blinds stehen („Einschwingen“). Danach werden Startstacks, Dealer, SB/BB aus dem Tischzustand gesetzt und die gepufferten Ereignisse geordnet nachgespielt.
- **Quellen jeder Aktion** (Provenienz):

  | Quelle | Bedeutung |
  |---|---|
  | `observed_label` | Aktionsbeschriftung am Platz gelesen (z. B. „Check“) |
  | `observed_fold` | Fold über Beschriftung oder ausgeblendetes Panel |
  | `derived_bet` | aus der Änderung des sichtbaren Einsatzes |
  | `derived_turn` | Wechsel der Hervorhebung ohne Einsatzänderung → Check |
  | `derived_stack` | aus einem Stackzuwachs (Gewinn/Rückgabe), auch nach dem Handwechsel gutgeschrieben |
  | `inferred_gap` | Die Reihenfolge verlangt eine Aktion, die nicht gesehen wurde |
  | `inferred_street_end` | Am Straßenende erschlossen: Wer noch in der Hand ist, hat gecallt bzw. gecheckt. Der abschließende Call ist praktisch nie zu sehen, weil die Einsätze sofort eingesammelt werden. |

- **Zeitkonstanten:**
  - TURN_GRACE_S 0,9 s: Wartezeit nach einem Hervorhebungswechsel, ob noch ein Einsatz kommt
  - SWEEP_WINDOW_S 2,0 s: Ein Einsatz fällt nahe einem Straßenwechsel auf 0 → das ist Einsammeln, keine Aktion
  - LATE_S 1,5 s: Ein später Fold bzw. Einsatz gehört zur vorigen Straße
- **Stackbilanz je Sitz:** Start = Ende − Gewinne + Einsätze. Abweichungen werden als Widerspruch markiert.
- **Status jeder Hand:** `complete` oder `partial`, mit Gründen, z. B. „Dealer nicht gesehen“, „Gewinner nicht beobachtet“, „n Lücken“.
- **Abstimmung über mehrere Bilder:** für Board- und Spielerkarten (`board_votes`, `card_votes`), damit ein einzelnes Fehlbild keine Karte festlegt

### 3.4 Genauigkeit gegen das PokerTH-Log (unabhängige Referenz)

Erste echte Aufnahme am 26.10.2026 (6er-Tisch gegen PokerTH-Bots, 12 Hände im Log). Dieselbe Partie wurde zweimal ausgewertet: einmal mit dem Stand vom Morgen, einmal nach den Korrekturen des Tages (Sitzgedächtnis, Formvergleich für Ränge, Rekonstruktions-Timing).

| Feld | erste Auswertung (`20261026-220836`) | nach Korrekturen (`20261026-224738`) |
|---|---|---|
| Hände zugeordnet | 12/12 | 12/12 |
| Blinds | 100 % | 100 % |
| Dealer | 11 % | **92 %** |
| SB/BB-Sitz | 0 % / 11 % | **100 % / 100 %** |
| Boardkarten | Precision 60 %, Recall 5,5 % | **100 % / 100 %** (55/55) |
| Gezeigte Karten (Showdown) | 0 % | **100 %** (2/2, 11 nicht sichtbar) |
| Aktionen | Precision 18 %, Recall 5 % | **Precision 88 %, Recall 89 %** (147 Treffer, 18 fehlen, 20 zusätzlich) |
| Aktionsbeträge | – | **98,7 %** (76/77) |
| Startstacks | 0 % | **90 %** (53/59) |
| Gewinner | 0 % | **Recall 100 %, Precision 87 %** (13 Treffer, 2 zusätzlich) |

Ein 4er-Tisch funktionierte am selben Abend ebenfalls (Sitzungen `230753`, `231440`). Ein formaler Vergleich dafür liegt nicht als compare.md vor.

**Verbleibende Fehlerklassen** (Analyse vom 26.10.):
1. **Blinds als Aktion:** Das Log führt „setzt SB/BB“ als eigene Aktion. Die Rekonstruktion kannte SB/BB, schrieb sie aber nicht als Aktion. Seitdem werden Blinds als `post_sb`/`post_bb` ausgegeben.
2. **Checks zu spät, doppelt oder beim falschen Sitz:** Das „Check“-Label bleibt teils bis in die nächste Straße stehen oder ist so kurz sichtbar, dass es bei 4 Bildern/s durchrutscht. Daher kommen die meisten fehlenden bzw. zusätzlichen Checks. **Offen:** Checks landen teils beim falschen Sitz.
3. **Falsche Startstacks:** Der Stack wird gelesen, bevor der letzte Pot gutgeschrieben ist, außerdem gibt es OCR-Ausreißer (Beispiel: „9511“ statt „511“).

**Bekannte Semantik-Fallen** (für Live wichtig, 28.10. behoben):
- `info.total` („Gesamt“) ist der **eingesammelte Pot ohne die Einsätze der laufenden Straße**.
- `pot.total` (Tischmitte) fehlt in manchen Sitzungen ganz (`230753`, `231440`) und hat OCR-Ausreißer, z. B. 9280 statt 280.
- `replay.live_pot()` nimmt deshalb `pot.total` nur, wenn es zu `info.total + Einsätze` passt, sonst `info.total + Einsätze`. `LiveBot.observation` nimmt den Pot aus dem rekonstruierten Live-Verlauf, wenn der Bild-Pot unter 90 % davon liegt.

**PokerTH-Format** (aus dem Log): PokerTH Web startet mit **1000 Chips bei 10/20 = 50 BB, Blinderhöhung nach 9 Händen**. Daraus entstand das Prüfstand-Format `pokerth` bzw. `mensch`.

**Messwerte Tempo:**
- Analyse am Screenshot (1905×980): erste Analyse ca. 200 ms, unveränderte Frames ca. 40 ms
- Live mit 4 fps neben laufendem Training: 718 Analyse-Frames übersprungen, das Video blieb vollständig

### 3.5 Noch nicht geprüft beim Collector

- **Karo und Kreuz:** Bisher sind nur Pik und Herz sicher gegen echte Bilder geprüft. In den Vergleichen stimmten aber alle 55 Boardkarten. Ein systematischer Test aller vier Farben fehlt.
- **Sonderfälle:** Side Pots, Split Pots, Sitzwechsel und Verbindungsabbruch sind nicht gezielt getestet.
- **Tischgrößen:** 2, 3, 7–10 Spieler live ungetestet. Der 10er-Tisch ist nur am Testbild geprüft.
- **Überdeckung:** Eine überdeckungsfeste Aufnahme (Windows.Graphics.Capture, C#) ist nicht gebaut.

---

## 4. Die KI: Engine, Bots, Netze, Training, Suche

### 4.1 Gemeinsame Schnittstelle

`ai/observation.py`: **Observation → Action**. Dieselbe Observation entsteht im Simulator, im Replay und live aus dem Collector. Sie enthält eigene Karten, Board, Stacks, Einsätze, Positionen, den öffentlichen Aktionsverlauf und `uncertain`, nie fremde verdeckte Karten. Raises werden als „auf“-Betrag angegeben. `clamp_action` macht jede Aktion regelkonform.

### 4.2 Engine und Werkzeuge

| Modul | Inhalt |
|---|---|
| `engine.py` (348 Z.) | NLHE für 2–10 Spieler. Heads-up-Reihenfolge (Button = SB, preflop zuerst, postflop zuletzt). Mindest-Raise = letzte volle Erhöhung (≥ 1 BB). Ein kurzes All-in eröffnet die Setzrunde nicht neu. Side Pots, nicht gecallte Chips zurück, ungerade Chips an den ersten Gewinner links vom Button. Karten: Platz i bekommt `deck[2i], deck[2i+1]`, Board `deck[20:25]`, damit ist Duplicate fair. `Hand.clone()` für Suche und CFR. **Validierung:** 18 Regeltests, 600 Zufallshände mit Chip-Erhaltung, **alle 10.000 Pluribus-Hände aus dem PHH-Datensatz laufen mit identischen Endstacks durch** (±1 Chip bei Split). Behobener Bug: Ein kurzes All-in im BB zwang den SB zum Nachzahlen. |
| `tournament.py` (304 Z.) | Sit&Go: gleicher Startstack, Blinds verdoppeln nach N Händen oder nach Liste, Ausscheiden, Platzierung (gleichzeitig Ausgeschiedene: größerer Startstack besser), Auszahlung, ROI mit Intervall, „moving button“ |
| `evaluate.py` (189 Z.) | Duplicate-Cash-Matches, bb/100 mit 95-%-CI, VPIP/PFR/Aggression/WTSD/W$SD |
| `tables.py` | Preflop-Equity aller 169 Klassen gegen 1–9 Zufallsgegner (Abweichung < 1 Prozentpunkt) |
| `pushfold.py` (337 Z.) | Equity-Matrix 169×169 mit exakten Blocker-Gewichten (`hand_vs_hand.json`). Nash-Push/Fold über fictitious play für 1–25 BB und 1–8 Spieler dahinter. HU exakt (Ausnutzbarkeit < 0,001 BB/Hand), z. B. 10 BB: SB pusht 58,3 %, BB callt 37,4 %. Multiway als vereinfachtes Modell (max. ein Caller), max. Ausnutzbarkeit im Modell 0,013 BB. Chip-EV, **kein ICM**. |
| `league.py` (297 Z.) | Liga mit Weng-Lin/Plackett-Luce-Rating (wie OpenSkill), Anzeige 1500 + 48·(μ−25), „sicher“ = Rating − 3σ. Ein Ligaspiel ist ein Duplicate-Sit&Go-Schema über alle Rotationen. `players.json` enthält 17 Einträge (Stil-Bots, opt-1/2, Netze). Der Liga-Report (`report.md`) ist veraltet (90 Spiele, Stand 26.10.). Die Liga dient heute vor allem als Gegner-Pool und Gate-Register. |

### 4.3 Bot-Pool (`agents.py`, 323 Z.)

- **Regel-Bots:**
  - `random`, `caller`, `equity` (Baseline)
  - Stil-Bots `station`, `rock`, `tag`, `lag`, `maniac` (angelehnt an PokerTH-Bot-Typen, nicht deren Code)
  - Stil-Parameter: vpip, pfr, value_margin, raise_margin, call_slack, bluff, bet_size, open_size, push_bb, nash_stack_factor, dazu `respect` und `sticky` (Call-Down)
  - Push/Fold nach der Nash-Tabelle unter `push_bb`
  - Zufall aus Seed, Hand und Verlaufslänge abgeleitet: gleiche Situation → gleiche Entscheidung (Duplicate-fair)
- **Zufalls-Stilbots** (`optimize.RANDOM_SPACE`): gewürfelte Parameter von Calling-Station bis Dauerbluffer, für Robustheit im Training
- **NASH_BOT** = `tag?push_bb=40&nash_stack_factor=1`: spielt unter 40 BB nur Push/Fold nach Nash, als Endspiel-Maßstab
- **Mensch-Bots** (`humanbots.py`, `data/humans/mensch-25nl.json`): siehe 4.4

### 4.4 Echte Spielerdaten (erlaubt: PHH / HandHQ)

**Pluribus-Datensatz** (PHH-Format der Univ. Toronto, MIT-Lizenz, `phh.py`):
- 10.000 Hände Pluribus gegen Profis, 6-max, 100 BB, alle Karten bekannt
- 91.356 Entscheidungen, davon 15.169 von Pluribus
- Genutzt für Behavior Cloning (`pluribus.npz`, `pluribus-feat-2.npz`) und als Anker bzw. Leine im PPO
- Kennzahl „Pluribus-Übereinstimmung“: Wie oft wählt das Netz dieselbe Aktion?

**HandHQ** (`humans.py`, `pc.cmd data humans`, 27.10.):
- PokerStars + Party, 25NL, **5,72 Mio. Hände, 121.391 Spieler**
- Karten sind nur am Showdown bekannt, Nachahmen geht also nicht. Gemessen wird, **wie** Menschen spielen (HUD-Statistiken je Spieler).
- **Datenfallen:**
  - PokerStars-`winnings` fehlen bei kampflosen Pots
  - Party-`winnings` enthalten den Rückfluss
  - „????“ steht mitten im Verlauf bei All-in
  - Antes und Straddles werden übersprungen
- **Sechs Spielertypen und ihre Mensch-Bots** (Ziel vs. erreicht nach CEM-Anpassung):

| Bot | Typ | Anteil | VPIP | PFR | Agg | Fold auf Einsatz | 3-Bet | C-Bet | WTSD |
|---|---|---|---|---|---|---|---|---|---|
| mensch-1 | Nit (sehr eng) | 27 % | 15/16 | 7/4 | 73/81 | 66/75 | 2/0 | 71/79 | 25/24 |
| mensch-2 | Durchschnitt | 25 % | 20/15 | 14/14 | 76/74 | 62/53 | 5/3 | 73/66 | 26/33 |
| mensch-3 | Durchschnitt | 17 % | 21/20 | 9/11 | 63/45 | 57/49 | 3/2 | 50/48 | 30/20 |
| mensch-4 | passiver Freizeitspieler | 14 % | 31/43 | 7/13 | 62/66 | 49/48 | 2/0 | 76/74 | 33/23 |
| mensch-5 | TAG/Reg | 9 % | 9/8 | 8/7 | 80/78 | 71/58 | 4/2 | 79/85 | 39/39 |
| mensch-6 | Durchschnitt (locker) | 9 % | 37/35 | 19/19 | 69/74 | 48/50 | 7/5 | 68/79 | 32/30 |

(Werte in %, „Ziel/Bot“.) Der Preflop-Teil ist gut getroffen. Postflop passen einzelne Werte weniger, etwa WTSD bei mensch-3 und mensch-4. In Version 1 waren die Stil-Bots Calling-Stations (Fold auf Einsatz 6–17 % statt 50–70 %), deshalb kamen die Parameter `respect` und `sticky` dazu. Je Typ wurde die bessere Version aus v1 und v2 übernommen.

### 4.5 Merkmale, Aktionen, Netz

**Merkmale** (`features.py`): vorverdaut statt roher Karten.

| Version | Anzahl | Inhalt |
|---|---|---|
| feat-1 | 46 | Equity (Preflop-Tabelle bzw. Monte-Carlo gegen Zufallshände), Handtyp, Board-Textur, Pot Odds, Stack/Pot, effektiver Stack, Position, Raises/Aggressor, Spielerzahl, Turnierlage |
| feat-2 | 49 | + Equity gegen die geschätzten **Ranges** der Gegner, Abstand zur Zufalls-Equity, Enge der Ranges |
| feat-3 | 57 | + 8 Merkmale aus dem **Gegnermodell** (VPIP, PFR, Aggression, Fold auf Einsatz, Belastbarkeit des aktuellen Gegners; Durchschnitt der Gegner in der Hand) |

Jede Version erweitert die vorige nur hinten. `widen_net` setzt neue Eingänge auf 0, das Netz spielt anfangs also identisch.

**Aktionen:**
- **act-1 (6 Aktionen):** Fold, Check/Call, Raise ½ Pot, Raise Pot, Raise 2× Pot, All-in
- **act-2 (8 Aktionen):** zusätzlich Raise ⅓ Pot und Min-Raise. Neue Aktionen starten als Kopie von „Raise ½“ mit Logit −2.
- Fold ist maskiert, wenn Checken geht. Die Maske enthält keine Duplikate zum Min-Raise.

**Netz** (`nn_agent.py`, Version `nn-mlp-1`):
- MLP: Merkmale → 128 → 128 (ReLU) → Politik (6 bzw. 8 Logits) + Wert (1)
- Gelernt wird mit PyTorch auf der CPU, gespielt mit einer numpy-Kopie (schnell, viele Prozesse)
- Gespielt wird **gemischt** (Ziehen nach Wahrscheinlichkeit, Zufall aus der Situation); live **greedy** (wahrscheinlichste Aktion)
- Spec: `nn?run=<Lauf>@<Checkpoint>`, ein Checkpoint ist etwa 100 KB groß

### 4.6 Training (`rl.py`, 590 Z., Version `ppo-1`)

1. **Behavior Cloning:** Nachahmung eines Lehrer-Bots oder des Pluribus-Datensatzes → Checkpoint 0
2. **PPO:**
   - Je Iteration werden viele Sit&Gos parallel gespielt
   - Belohnung je Hand = Chip-Änderung / Startstack × reward_scale
   - GAE mit γ = 1 innerhalb einer Hand
   - Optimiert wird damit **Chip-EV, nicht die Turnierauszahlung** (noch kein ICM)

**Hyperparameter** (Stand lynx-3):

| Parameter | Wert | Parameter | Wert |
|---|---|---|---|
| hidden | 128 | Turniere/Iteration | 512 |
| Lernrate | 3e-4 | Epochen | 4 |
| Minibatch | 2048 | Clip | 0,2 |
| vf_coef | 0,5 | ent_coef | 0,01 |
| λ (GAE) | 0,95 | max_grad_norm | 0,5 |
| reward_scale | 10 | Self-Play-Anteil | 0,3 |

**Wichtige Optionen** (das „Rezept“, das funktioniert hat):

| Option | Bedeutung | lynx-3 |
|---|---|---|
| `--anchor-coef` / `--anchor` | Leine (piKL wie bei Metas Cicero): KL-Strafe gegen einen Anker-Bot | 0,3 gegen `pros-r1:0` (Pluribus-Nachahmer) |
| `--anchor-min-players` / `anchor_min_bb` | Leine nur, wo der Anker Erfahrung hat | ab 4 Spielern, ab 25 BB |
| `--human-share` | Anteil Mensch-Bots an den Tischen | 0,4 |
| `--random-share` | Zufalls-Stilbots | 0,05 |
| `--self-play-seats` | Plätze mit eigenen früheren Versionen | 0,3 |
| `--random-formats` | 2–10 Spieler, 20–200 BB, Blind-Tempo 5–20 Hände, verschiedene Auszahlungen | an |
| `--table-weights` | Häufigkeit je Spielerzahl | 2:3, 3:2, 4:2, 5:2, 6:3, 7–10:1 |
| `--exploit-every` / `--exploit-iters` | alle N Iterationen ein Ausbeuter als neuer Gegner (PSRO/AlphaStar-Prinzip) | 100 / 30 |
| `--bench-every` / `--bench-sets` / `--bench-ref` | Prüfstand während des Trainings, gepaart gegen eine Referenz (`best.json`) | 100 / mensch480, praezise, pluribus / lynx-2@500 |
| `--gate-schemes`, `--champion` | Aufnahmeprüfung je Abschnitt | 600 frische Turniere gegen den Liga-Besten |
| `--widen-from`, `--features`, `--actions`, `--lr` | Netz aufweiten bzw. umstellen, Lernrate | `--widen-from lynx-2@500` |

Eine Iteration dauert mit 512 Turnieren etwa 7 s plus Prüfstände und Ausbeuter. 1500 Iterationen sind ein Nachtlauf.

### 4.7 Weitere Verfahren (gebaut, aber nicht der Hauptweg)

- **CEM-Stiloptimierung** (`optimize.py`): Cross-Entropy über 10 Stil-Parameter. Ergebnis: opt-1/opt-2. Das Verfahren ist ausgereizt, siehe Chronik.
- **Tabellen-MCCFR** (`cfr.py`): wie der Pluribus-Blueprint (External Sampling, Linear CFR, grobe Abstraktion, etwa 77.000 Infosets). Bei Rechenzeit im Laptop-Maßstab klar schwächer als die Netze (cfr-1@200: mix96 Δ rock −22,7) und stark ausnutzbar (Ausbeuter +69 %).
- **Deep CFR** (`deepcfr.py`): Vorteils-Netz plus Strategie-Netz mit Reservoir-Puffer. Bei It 10/20 vielversprechend (mix96 +5 %, 66 % Pluribus-Übereinstimmung ohne Pluribus-Daten), bei It 30 Einbruch (−16 %), bei It 60 −31 %. **Aufgegeben am 27.10.**, wäre ein Server-Experiment.
- **Rollout-Suche Stufe 1** (`search.py`, `search?bp=...,worlds=16`): je Aktion 16–24 „Welten“ mit dem Netz für alle zu Ende gespielt. **Schädlich** (mix96 −18,9 statt +49 %): Sie nimmt an, alle Gegner spielen wie unser Netz (folden viel), und überstimmt deshalb Folds mit großen Raises. Verworfen. `world_from_obs` wird weiter genutzt.

### 4.8 Ranges und Gegnermodell

**`ranges.py`:**
- Je Gegner Gewichte über alle **1326 Kombinationen**, verschoben durch seine Aktionen (Bayes-artig, Heuristik)
- **Preflop:**
  - Raise ≈ obere q % mit OPEN_Q = 30/10/4,5/3 % (Open/3-Bet/4-Bet/5-Bet)
  - Call ≈ CALL_Q = 60/35/14/6 %
  - Kurze All-ins breiter
  - **Heads-up eigene Quantile** (28.10.): OPEN_Q_HU = 85/15/6/3,5 %, CALL_Q_HU = 90/70/45/12 %
- **Postflop**, mit s = Stärke-Perzentil auf dem damaligen Board:
  - Bet/Raise ×(0,15 + 0,85·s^1,5)
  - Call ×(0,3 + 0,7·s^0,6)
  - Check ×(1 − 0,35·s^4)
- Equity per numba-Monte-Carlo gegen die Ranges. Beispiel: QJ gegen Open + 3-Bet hat 41 % gegen Zufallshände, aber 23 % gegen die Ranges.
- `opponent_ranges(obs, heads_up=...)`

**`opponents.py`:**
- OpponentTracker wie ein HUD (VPIP, PFR, Agg, Fold auf Einsatz) mit Prior (28/16/45/45 %), conf = Hände / (Hände + 20)
- Live mit unscharfem Namensabgleich gegen OCR-Rauschen und Rückfall auf die Platznummer

### 4.9 Heads-up-Suche zur Laufzeit (`husearch.py`, 634 Z.) – „hus“

**Idee:** Ab dem Moment, in dem nur noch zwei Spieler in der Hand sind, wird in jeder Entscheidung ein Teilspiel per **CFR+ über alle 1326 Kombinationen beider Spieler gleichzeitig** gelöst, statt nur dem Netz zu folgen. Das orientiert sich an Libratus, DeepStack und ReBeL. Der Gegner ist dabei der ungünstigste (Gleichgewicht im Teilspiel), es wird nicht ausgebeutet.

**Spezifikation:** `hus?bp=<Liga-Name>|run:<Lauf>@<N>&iters=120&iters_river=300&streets=turn,river&ranges=pre,flop`, Standard-Streets seit 30.10. `turn,river`, Standard-Ranges seit 30.10. 14:08 `pre,flop` (6.8) (der Preflop-Löser kostete in der Nachtdiagnose rund 25 Punkte im Turnierformat, 6.8; `streets=preflop,...` schaltet ihn zu).

**Blueprint-Ranges (`bpranges.py`, 30.10.):** Die Ranges zu Straßenbeginn kommen nicht mehr aus der Faustformel in `ranges.py` („Button eröffnet 85 %, BB verteidigt 70 %“), sondern aus dem Blueprint-Netz selbst. Die Hand wird mit der Engine von vorn nachgespielt; bei jeder Preflop-Entscheidung eines der beiden Spieler wird für alle 169 Handklassen gefragt, mit welcher Wahrscheinlichkeit das Netz genau diese Aktion gewählt hätte (`forward_batch`, gemeinsame Maske, `from_action` ordnet die Größe zu). Das Produkt ist die Range, auf die 1326 Kombinationen verteilt; Flop- und Turn-Aktionen bekommen weiter die Heuristik-Faktoren, mit `ranges=pre,flop` auch die Flop-Aktionen über alle Kombinationen vom Netz. Für den eigenen Spieler ist das exakt (er spielt preflop das Blueprint), für den Gegner die Annahme „spielt wie unser Netz“. Kosten: rund 50 ms (preflop) bzw. 470 ms (mit Flop) je Straße, gecacht je Hand. Passt der Verlauf nicht zur Engine (Live-Unsicherheit), fällt die Suche auf `public_ranges` zurück (`last["ranges"]` = „bp“ oder „heur“). Beispiel 50 BB, Button 2,5 BB, BB callt, Flop check/check: Netz gibt dem Caller nur 4,7 % Top-15-Masse (er 3-bettet die starken Hände) und dem Eröffner 35 %; die Heuristik hatte 20,5 % gegen 16,8 %, also die Verhältnisse fast umgekehrt. `ranges=heur` stellt das alte Verhalten her. Tests `test_bpranges.py` (5).

**Technik:**
- **Rechenkern in numba** (`nogil`, `cache`), Baum BFS-flach als Arrays
- **Funktionen:**
  - `_solve`: alternierendes CFR+, Durchschnitt mit Gewicht t^GAMMA, GAMMA = 2
  - `_best_response`: Ausnutzbarkeit, über `solve(..., exploit=True)`
  - `_showdown` und `_fold_sums` mit exakten Blockern
- **Turn-Baum** mit allen 44 möglichen Rivers (div = 44)
- **Einsatzgrößen:**

  | Straße | Bets (× Pot) | Raises |
  |---|---|---|
  | River | 0,33 / 0,75 / 1,5 | 1,0 |
  | Turn | 0,66 | – |
  | River im Turn-Baum | 0,75 | – |
  | immer | All-in | MAX_RAISES = 4 je Straße, Größen über 85 % des Stacks → All-in (ALLIN_SNAP) |

- **Wichtige Korrektur vom 28.10.: Lösen ab Straßenbeginn mit dem tatsächlichen Pfad.**
  - `root_state(obs)` liefert (State, Gegner, Pfad). `build_tree(root, path)` fügt die **echt gespielten Größen** als Äste ein (SAME_SIZE 4 %, `_matches`), `Tree.current` ist die aktuelle Entscheidung.
  - Die Ranges (`public_ranges`) nutzen nur den Verlauf **bis Straßenbeginn**. So passt die Startverteilung zum Baum.
  - Vorher wurde ab dem aktuellen Knoten mit heuristischer Range neu gelöst. Das führte zu massenhaft verlorenen All-ins: hus-2 stand bei −440 bb/100 und wurde abgebrochen.
- **Schutz:** `applies()` verlangt `obs.street in iters`. Das behebt einen KeyError „preflop“ im 6er-Turnier, wenn preflop zwei Spieler übrig waren.
- **Ausnutzbarkeit im Teilspiel:**
  - Turn mit 60 It ca. 3 % des Pots, mit 120 It ca. 1,5 %
  - River mit 300 It unter 1 %
- **Rechenzeit:** etwa **2,4 s je Suche** (Match hus gegen bp: 156 Suchen in 383 s)

### 4.10 Heads-up-Preflop-Löser (`hupreflop.py`, 252 Z.)

- **Anlass:** Gegen Slumbot lag das größte Leck preflop. Der BB 3-bettete etwa 50 % und callte kaum. Hände, die preflop endeten (50 % aller Hände), kosteten −18,7 bb/100.
- **Verfahren:** CFR+ über die **169 Starthand-Klassen**, ITERATIONS = 800, `strategy()` mit lru_cache (Slumbot: fast nur Cache-Treffer)
- **Aktionen:**
  - SB: Fold, Limp, Open 2,5 BB, All-in
  - BB gegen Limp: Check, Raise auf 4 BB (ISO), All-in
  - Gegen einen Raise: Fold, Call, Reraise mit Faktor 3,0 (3-Bet) / 2,3 (4-Bet) / 2,2 (5-Bet), solange unter 45 % des Stacks, sonst All-in
  - Die tatsächlichen Größen werden als zusätzliche Äste eingefügt
- **Postflop-Modell** (nicht ausgespielt):
  - Der Pot wird nach realisierter Equity geteilt
  - OOP_REALIZE = 0,80, ALPHA = 1,3 (starke Hände realisieren mehr), gegen 1 bei kleinem SPR
  - All-in mit exakter Equity aus der 169×169-Matrix
- **Ausnutzbarkeit** im Modell unter 0,2 BB/100
- **Ergebnisse:**

  | Stack | SB foldet | BB gegen 2,5×: Fold / Call / 3-Bet |
  |---|---|---|
  | 100 BB | 14 % | 30 / 50 / 18 % |
  | 200 BB | 11 % | 32 / 49 / 20 % |

  AA wird im Modell oft gelimpt (Trap).
- **Einbindung:** in `HUSearchAgent.preflop()`, greift nur am echten Heads-up-Tisch (`sum(in_hand) == 2`)

---

## 5. Live-Betrieb: Vorschläge, Lynx-Leiste, Turnier-Erkennung

### 5.1 LiveBot (`ai/live.py`)

- Neben der Erfassung läuft ein **Reconstructor live mit**:
  - Fertige Hände füttern das Gegnermodell.
  - Der Verlauf der laufenden Hand kommt in die Observation. Bis zum 27.10. war er live leer, der Bot sah keine Raises vor sich.
- **„Du bist dran“** heißt: eigenes Panel hervorgehoben **und** Call/Check-Buttons sichtbar. Ein alter Fehler: `hero.to_act` blieb dauerhaft gesetzt, dadurch gab es nur einen Vorschlag pro Sitzung.
- **Ruhezeit:** Ein Vorschlag erscheint erst, wenn die Lage **0,7 s ruhig** ist (`SETTLE_S` in `live.py`, seit 28.10.; vorher 0,4 s), und wird neu berechnet, wenn sich danach Karten, Einsätze, Board oder Pot ändern.
- **Die Straße** wird aus der Zahl der Boardkarten bestimmt, weil die Straßenanzeige nachhinkt.
- **Pot** wie in 3.4 (Bild, sonst Verlauf). Mindest-Raise min_raise_to ≥ max(Einsätze) + BB.
- **Standard-Berater:** **lynx-3-300**, greedy

### 5.2 Lynx-Leiste (`overlay.py`, 282 Z.)

- **Fenster:** kleines Tk-Fenster über der Taskleiste (neben Uhr und Akku), in eigenem Thread mit thread-sicherer Warteschlange
- **Verhalten:**
  - topmost, ohne Rahmen, `WS_EX_NOACTIVATE` + `WS_EX_TOOLWINDOW`: nimmt nie den Fokus, kein Taskleisten-Knopf
  - **Sichtbar, aber ausgeschnitten (seit 3.11.2026):** Die Leiste ist ein normales Fenster, das jede Bildschirmaufnahme sieht. Sie meldet ihr Fenster bei der Aufnahme an, und `WindowSource` füllt ihre Fläche in jedem Bild mit der Umgebungsfarbe (8.7). Bis 2.11. verbarg sie sich per `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` vor allen Aufnahmen (Gegenprobe mit mss: 0 % Leistenfarbe im Foto, ohne Sperre 94 %).
- **Anzeige:**
  - Bist du dran, leuchtet die Leiste in der Farbe der Aktion und spielt einen Ton (winsound): Fold tief, Check/Call mittel, Raise hoch, All-in doppelt
  - Dazu Alternativen (`alternatives()`): „Check“, wenn checken geht, und „Min-Raise“
  - Warnungen bei unsicherem Pot bzw. geschätztem Call-Betrag
  - Statuspunkt grün/gelb/rot (Aufnahme / Tisch erkannt bzw. Analyse verzögert / Quelle verloren)
- **Bedienung:** Ziehen verschiebt sie (gespeichert in `data/live/leiste.json`). Rechtsklick: Ton an/aus, Position zurücksetzen.
- Windows 11 kennt keine Taskleisten-Deskbands mehr, daher das schwebende Fenster
- Der Nutzer fand die Leiste „mega passt erstmal so“

### 5.3 Automatische Turnier-Erkennung (`TournamentWatch`, 28.10. abends)

- **Ausgeschieden:**
  - Nach einer Hand ist der eigene Stack 0. Der Platz ist 1 plus die Zahl der Gegner, die noch Chips haben.
  - **Bestätigt** wird das über die Startstacks der nächsten Hand, die nach dem Einschwingen gutgeschriebene Gewinne enthalten. Hat man dort doch Chips (OCR-Fehler „0“), wird das Ausscheiden verworfen.
- **Gewonnen:** Nur man selbst hat noch Chips. Das zählt als Platz 1, endgültig bei Sitzungsende (Strg+C) oder beim nächsten Spiel.
- **Eintrag:** Je Spiel (`info.game_hand`) gibt es höchstens ein Ergebnis. Es wird automatisch in `data/ziele/pokerth.jsonl` eingetragen (`quelle=auto`, Hände, Spiel, letzte Hand). Konsole und Leiste zeigen z. B. „Turnier vorbei: Platz 2 von 6 nach 87 Händen“ und die Bilanz.
- **Turnierbeginn verpasst:** Dann wird der Eintrag markiert, weil die Spielerzahl evtl. zu klein ist.
- **Geprüft:** Unit-Tests, außerdem auf allen 6 echten Aufnahmen keine Fehlmeldungen. **Ein echtes Turnierende war noch nicht dabei**, der Live-Test läuft seit dem 28.10. abends.

### 5.4 Ablauf eines Live-Abends

1. PokerTH Web öffnen, noch kein Spiel starten.
2. `pc.cmd live --leiste` starten, **vor** Turnierbeginn.
3. Spiel gegen PokerTH-Bots starten, das Fenster vorn und unverdeckt halten.
4. Vorschlag in der Leiste lesen, **selbst klicken**, möglichst konsequent folgen (dann wird Lynx gemessen, nicht Jakob).
5. Auffällige Hände merken (falsche Karten oder Pot, Abweichungen).
6. Nach einem Sieg `live` mit Strg+C beenden, damit der Sieg eingetragen wird.
7. Danach: Aufnahme mit `live-replay` und `compare` (Log nur als Gegenprobe) auswerten.

---

## 6. Benchmarks: Methodik und alle Ergebnisse

### 6.1 Prüfstand (`ai/bench.py`, Version bench-1)

**Feste Testsets** (feste Karten und feste Tische):

| Set | Inhalt | Format |
|---|---|---|
| `fest48` | 48 Sit&Go-Schemata gegen rock/tag/lag/station/maniac | 6 Sp., 3000 Chips 10/20 (150 BB), ×2 alle 10 Hände, 50/30/20 |
| `mix96` | 96 Schemata, Tische aus stärkerer Mischung (u. a. opt-1, pros-bc) | wie oben |
| `cash` | 300 Duplicate-Cash-Hände | bb/100 |
| `pluribus` | Übereinstimmung mit Pluribus | nur Netze |
| Formate je 48 | `hu48`, `3max48`, `10max48`, `turbo48` (30 BB, Blinds alle 5), `deep48` (200 BB), `pokerth48` (6 Sp., 1000 Chips = 50 BB, alle 9 Hände) | |
| **`mensch480`** | 480 Schemata, PokerTH-Format, 5 Gegner aus den Mensch-Bots nach Anteil | Hauptmaß Ziel 2 |
| `praezise` | mix960 + pokerth480 + hu480 + 10max240 | Intervalle etwa 3× enger (±3 statt ±12) |
| `nash240` | Heads-up 20 BB (400 Chips, 10/20, alle 10 Hände, Sieger nimmt alles) gegen NASH_BOT | Ziel 5 |
| `kurz240` | dasselbe gegen einen Mensch-Bot | Ziel 5 |

Die Zahl am Namen ist frei wählbar. Größere Sets beginnen mit den Schemata der kleinen.

**Kennzahlen:**
- **ROI** = mittlere Netto-Auszahlung in Buy-ins. Bei 6 Spielern und 50/30/20 sind maximal +200 % möglich (Sieg = 3 Buy-ins netto +2).
- **Δ rock** bzw. **Δ Ref** = gepaarte Differenz auf denselben Karten

**Weitere Prüfungen:**
- **Ausbeuter-Test** (`train exploit`): Ein Netz (Start pros-1@0) lernt 30–40 Iterationen gegen 5 Kopien des Prüflings. Gemessen wird sein ROI auf 48 frischen Schemata. Je kleiner der ROI, desto robuster der Prüfling.
- **Aufnahmeprüfung** (`gate`): 120–600 frische Schemata, gepaart gegen den Titelverteidiger, bestanden bei untere CI-Grenze > 0
- **Bestätigung** (`confirm.py`): einmalig, frische Mensch-Tische bzw. ein Liga-Gate mit eigenem Seed, vorab festgelegt

### 6.2 Entwicklung der Spielstärke (Hauptlinie)

| Datum | Bot | Kernergebnis | Status |
|---|---|---|---|
| 25.10. | rock (Regel-Bot) | Referenz Δ rock = 0, Ausbeuter **+100 %** | bester Regel-Bot |
| 25./26.10. | opt-1 (CEM) | Gate vs tag +8,9 [1,1; 16,7], mix96 −2,4 | Überanpassung |
| 26.10. | nn-1 (PPO ohne Leine) | mix96 +19 @100, dann Absturz, Pluribus 63 → 13 % | Ausbeutung der Liga, kein gutes Poker |
| 26.10. | pros-1 (BC Pluribus + Leine) | mix96 −20 @0 → +8 @200 → +14 @500, Pluribus 80 % | |
| 26.10. | **pros-2** (+ 512 Turniere/It) | **Gate vs rock +19,8 % [8,8; 30,7]**, mix96 +22,8, Ausbeuter +3,8 % | erster großer Sprung |
| 26.10. | pros-r1@300 (+ Ranges, feat-2) | mix96 +23,0, fest48 +25,0, Pluribus 82 % | später als bester bestätigt (präzise) |
| 27.10. | pros-r3-200 (Multi-Format) | Gate vs pros-ppo2 +13,3 [3,0; 23,6] | in der Liga, auf präzise nicht besser |
| 27.10. | **pros-h1@600** (feat-3, act-2, Self-Play-Plätze, viele HU-Tische) | präzise vs pros-r1@300: hu +8,3*, mix960 +2,9, pokerth +1,4, 10max +8,3; Bestätigung 600 Schemata +6,0 [1,4; 10,6] | Name **Lynx** |
| 27.10. | **lynx-2@500** (+ 40 % Mensch-Bots) | vs Lynx: mensch480 **+17,7***, mix960 +8,1*, hu480 +8,5*; Bestätigungen +12,1 [7,0; 17,3] und +7,4 [2,6; 12,3] | größter Sprung durch Mensch-Bots |
| 28.10. | **lynx-3-300** (lynx-2 weiter, Nachtlauf) | Gate +4,5 [0,3; 8,6]; Bestätigungen Mensch-Tische **+9,2 [4,8; 13,6]**, Liga **+6,7 [2,3; 11,0]** | **aktueller Bester und Live-Standard** |

(* = 95-%-Intervall über 0)

### 6.3 Große Testsets (Auszug aus `data/bench/report.md`, ROI, in Klammern Δ rock gepaart)

| Bot | 10max240 | hu480 | mensch480 | mix960 | pokerth480 |
|---|---|---|---|---|---|
| rock | +43,9 % | −16,9 % | +43,8 % | +24,6 % | +21,1 % |
| pros-r1@300 | +56,2 (+12,2) | +35,6 (+52,5) | +73,0 (+29,3) | +41,3 (+16,8) | +32,6 (+11,5) |
| pros-h1@600 | +64,5 (+20,6) | +44,0 (+60,8) | +75,9 (+32,1) | +44,3 (+19,7) | +33,9 (+12,8) |
| pros-h1@200 | +59,3 (+15,4) | +48,3 (+65,2) | +76,8 (+33,0) | +45,4 (+20,8) | +31,4 (+10,3) |
| lynx-2@500 | +72,9 (+29,0) | +52,5 (+69,4) | +93,6 (+49,9) | +52,4 (+27,8) | +37,1 (+16,0) |
| lynx-2@300 | +73,3 (+29,4) | +52,9 (+69,8) | +94,8 (+51,0) | +59,2 (+34,7) | +42,8 (+21,6) |
| **lynx-3@300** | +73,6 (+29,6) | +49,6 (+66,5) | **+96,8 (+53,0)** | +50,6 (+26,0) | +35,2 (+14,1) |
| lynx-3@500 | +72,0 (+28,0) | +51,0 (+67,9) | +103,2 (+59,5) | +53,2 (+28,7) | +37,9 (+16,8) |
| lynx-3@1000 | +74,9 (+30,9) | +49,8 (+66,7) | +103,2 (+59,4) | +51,8 (+27,2) | +40,1 (+18,9) |
| lynx-3@1100 | +61,5 (+17,6) | +50,2 (+67,1) | **+108,5 (+64,7)** | +47,0 (+22,4) | +39,4 (+18,3) |
| lynx-3@1500 | +69,0 (+25,0) | +50,8 (+67,7) | +100,4 (+56,6) | +51,5 (+27,0) | +37,1 (+16,0) |

**Einordnung:**
- Spätere lynx-3-Stände liegen auf mensch480 teils höher, etwa @1100 mit +108,5 %, haben aber **ihr Gate gegen lynx-3-300 nicht bestanden** (@600 −3,7, @900 +0,1, @1200 −2,5, @1500 +2,8).
- Nach der Methodenregel bleibt deshalb lynx-3-300 der Beste. Ein Spitzenwert auf dem oft angeschauten mensch480 allein reicht nicht.
- best.json (gepaart gegen lynx-2@500) lag @1000 bei Mittel +2,22, mit mensch480 +9,6 [4,5; 14,6].

### 6.4 Format-Prüfstand vom 27.10. morgens (Δ rock, je 48 Schemata, CI ±15–20)

| Bot | hu48 | 3max48 | 10max48 | turbo48 | deep48 | pokerth48 | Ø |
|---|---|---|---|---|---|---|---|
| pros-r2@350 | +50,0 | +17,1 | +30,7 | +4,1 | +24,2 | +9,4 | +22,6 |
| pros-r3@200 | +50,0 | +13,6 | +19,3 | −1,2 | +26,9 | +19,4 | +21,3 |
| pros-r1@300 | +41,7 | +13,1 | +13,4 | +12,1 | +23,5 | +20,4 | +20,7 |
| pros-2@300 | +54,2 | +29,2 | +12,4 | −7,9 | +29,6 | +3,8 | +20,2 |

Fazit damals: alle im Rauschen gleichauf. Daraus entstanden die größeren, präziseren Sets.

### 6.5 Ausnutzbarkeit (Ausbeuter-ROI, kleiner = robuster)

| Bot | Ausbeuter-ROI |
|---|---|
| rock | **+100,2 %** [85,9; 114,5] |
| cfr-1 (Tabelle) | +68,8 % [59,4; 78,1] |
| pros-2@300 | +3,8 % [−7,1; 14,6] |
| pros-h1@600 | ca. +10 % |
| lynx-2@500 | ca. +1 % (lynx-2@300 dagegen +28 %, also ausnutzbar) |
| **lynx-3-300** | **+2,3 %** [−11,5; 16,1] |

### 6.6 Endspiel heads-up 20 BB (Ziel 5)

| Bot | nash240 (gegen Push/Fold-Nash) | kurz240 (gegen Mensch-Bots) |
|---|---|---|
| lynx-3-300 | **+17,9 %** [10,4; 25,5] | **+83,3 %** [78,3; 88,3] |

Gegen eine Nash-Push/Fold-Strategie zu gewinnen ist möglich, weil Nash-Push/Fold gegen einen Spieler, der auch kleinere Raises und postflop spielt, nicht optimal ist.

### 6.7 Slumbot (Heads-up 200 BB Cash, Ziel 3)

**Methodik:**
- **Format:** API von slumbot.com, Blinds 50/100, 20.000 Chips je Hand. Je Hand wird sofort in `data/bench/slumbot/<name>.jsonl` geschrieben (fortsetzbar), 4–6 parallele Sitzungen.
- **roh:** tatsächliche Gewinne in bb/100
- **All-in-EV:** Bei einem All-in vor dem River zählt die Equity statt der ausgeteilten Karten.
- **Baseline:** Slumbot meldet je Hand, was **Slumbot selbst auf unserem Platz mit denselben Karten** gewonnen hätte. Das ist ein Maß für Kartenglück mit Erwartungswert 0.
  - Die alte Spalte „vs Baseline“ (Gewinn − Baseline) ist **verzerrt und kaum genauer**: Die Korrelation liegt nur bei etwa 0,4–0,6, weil Slumbot die Karten anders spielt.
  - Am 27.10. war mit r = 0,15 sogar von „nutzlos“ die Rede. Das galt für die rohen Gewinne.
- **Neues Hauptmaß seit 28.10.: „bereinigt“** = All-in-EV − β·Baseline mit geschätztem optimalem β (Kontrollvariable, `slumbot.adjusted`). Das ist erwartungstreu und hat den kleinsten Fehlerbalken. Es steht auch in der Zieltafel.

**Alle Läufe** (bb/100, 95-%-Intervall):

| Bot | Hände | roh | All-in-EV | Kartenglück | **bereinigt** | β |
|---|---|---|---|---|---|---|
| pros-r1@300 | 15.767 | −21,5 ±17 | −22,7 [−39; −6] | −42,8 | **−13,7 [−29; +2]** | 0,21 |
| pros-h1@200 | 8.935 | −6,0 ±28 | −8,0 [−36; +20] | +4,7 | **−9,8 [−34; +15]** | 0,38 |
| pros-h1@600 (Lynx 1) | 7.666 | −33,2 ±24 | −38,6 [−61; −16] | −16,7 | **−35,4 [−57; −14]** | 0,20 |
| lynx-2@500 | 20.000 | −27,2 ±16 | −26,3 [−42; −11] | −31,0 | **−18,6 [−33; −4]** | 0,25 |
| **lynx-3@300** | 10.000 | −21,3 ±24 | −23,0 [−45; −1] | −23,4 | **−17,2 [−38; +4]** | 0,25 |
| hus-1 (alte Suche, ab Turn) | 3.000 | −16,5 ±75 | −12,6 [−83; +58] | −25,3 | +2,5 [−49; +54] | 0,60 |
| hus-2 (Suche, Fehler) | 458 | −396 | −382 [−661; −103] | −335 | −81,6 [−211; +48] | 0,89 |
| **hus-3** (Suche ab Straßenbeginn + Preflop-Löser) | 8.167 | −8,7 ±36 | −8,2 [−43; +27] | **+29,4** | **−23,7 [−52; +5]** | 0,53 |
| **lynx-4@300** (29.10., 2 Sitzungen) | 10.000 | −10,3 ±42 | −7,2 [−46; +31] | −13 | **+0,2 [−29; +30]** | |
| **hus-4** (30.10., Suche Turn+River ohne Preflop-Löser, Blueprint-Ranges pre+flop) | 3.000 | −41,0 ±91 | −48,7 [−125; +28] | −17 | **−39,0 [−95; +17]** | |
| **hus-5** (30./31.10., Cash-Konfiguration: Preflop-Löser + Gleichgewichts-Ranges `eq,flop` + Netz-Blätter) | 10.000 | −15,3 ±37 | −7,4 [−41; +26] | +1 | **−8,0 [−35; +19]** | |

**Lehren daraus:**
0. **lynx-4-300 ist gegen Slumbot auf Augenhöhe** (bereinigt +0,2 nach 10.000 Händen, roh −10 bei Kartenpech −13). Das ist rund +17 bb/100 besser als lynx-3@300 und erfüllt Stufe 1 des Ziels 3 (> −15); Stufe 2 (> 0 gesichert) braucht viel mehr Hände oder eine klar stärkere Version. Der Verlauf schwankte stark (+38 nach 1.800, +42 nach 4.400, +16 nach 5.700, +9 nach 6.600, +19 nach 7.200 Händen), Zwischenstände unter 5.000 Händen bleiben wertlos. Slumbot ist seit der Konkurrenzanalyse nur noch Vorstufe, Hauptmaß wird GTO Wizard AIVAT.
1. **Gegen Slumbot verliert Lynx ehrlich etwa 15–20 bb/100.** Die erste Stufe von Ziel 3 (> −15) ist knapp verfehlt.
2. **Die Suche (hus-3) ist gegen Slumbot nicht nachweislich besser als das Netz allein.** Ihr scheinbares Plus (zwischenzeitlich +54 bb/100 nach 1.833 Händen, am Ende All-in-EV −8) war **Kartenglück**: Slumbot selbst hätte mit diesen Karten +29 bb/100 gewonnen.
3. **Preflop ist durch den Preflop-Löser repariert:** Preflop-Anteil +0,7 statt −18,7 bb/100, SB-Fold 12 %, BB gegen Open Fold 10 %, 3-Bet 26 %. Das Netz verliert demnach postflop.
4. Rohe Zwischenstände unter etwa 5.000 Händen sind wertlos, das Intervall liegt bei ±60–130. Erst das bereinigte Maß nach vielen Tausend Händen ist belastbar.
5. pros-h1@200 hat die beste Slumbot-Schätzung (−9,8), ist aber auf den PokerTH-nahen Sets schwächer. Ein HU-Spezialist ist nicht automatisch der beste PokerTH-Bot.
6. **Leck-Analyse lynx-2** (`scratchpad/slumbot_leaks.py`, 27./28.10.):
   - Hände, die preflop enden (50 %), kosten −18,7 bb/100
   - Der BB 3-bettete gegen Opens 53 %
   - Früher (pros-r1): Button foldet 40 % sofort (stark wären 10–20 %), BB foldet 51 % gegen Opens (stark wären 25–35 %)

### 6.8 Suche gegen Netz in PokerTH-Formaten

- **hus gegen bp lokal** (HU 200 BB, 300 Deals duplicate): **+41,8 bb/100 [−36; +119]**, nicht signifikant
- **PokerTH-Vergleich** `hus?bp=lynx-3-300&iters=60&iters_river=150` auf hu480 und mensch480 gegen das Netz allein (Referenz Netz hu480 +49,6 % [44,2; 54,9]): **zweimal gestartet, nie fertig geworden.** Er wurde vom Speicher-Wächter bzw. bei Spielbeginn am 28.10. abends abgebrochen, ein Ergebnis gibt es nicht.
- **29.10. (17:20–21:12, losgelöst, 4 Prozesse): `hus?bp=lynx-4-300&iters=60&iters_river=150` (hus-1, Turn+River im Baum, Ausspielen) auf hu480, gepaart gegen lynx-4@300: Suche +17,1 % [11,1; 23,1], Netz allein +46,5 % → Differenz −29,4 [−36,8; −21,9].** Die Suche ist in diesem Format **signifikant schlechter** als ihr eigenes Blueprint-Netz. Zusammen mit Slumbot (hus-3 −23,7 gegen lynx-3 −17,2, 6.7) heißt das: die Suche in der jetzigen Form hilft nirgends. Sie wird **nicht** Live-Standard. Die Ursache ist offen (zu wenige Iterationen, Gegner-Range aus dem eigenen Blueprint, Ausspielen am Blatt, Aktionsabbildung); sie muss gefunden werden, **bevor** Rechenzeit für das Wertnetz ausgegeben wird (Meilenstein 3 baut auf der Suche auf). Nächste Diagnose: Suche gegen ihr Blueprint direkt (duplicate HU), Konvergenz mit 5× Iterationen, Stichproben einzelner Entscheidungen gegen das Netz.
- **Nachtdiagnose 29./30.10. (`bench_diag_nacht.py`, statt hus-2), Phase A (21:16–21:59):** `hus?bp=lynx-4-300&streets=preflop`, also **nur der Preflop-Löser** (hupreflop), postflop das Netz, auf hu480 gepaart: **+21,2 % [15,4; 27,1] gegen Netz +46,5 → Differenz −25,2 [−32,3; −18,1]**; gegen hus-1 +4,2 [−1,9; +10,3]. **Das Leck sitzt preflop:** das Heads-up-Gleichgewichtsmodell (gebaut für 200 BB Cash, gegen Slumbot gut: Preflop-Anteil +0,7 statt −18,7) kostet im 50-BB-Turnier mit alle 10 Hände steigenden Blinds gegen die Pool-Bots rund 25 Punkte; die Turn/River-Suche selbst macht nur etwa −4 aus (nicht signifikant). Konsequenzen: (1) `streets=preflop` ist im Turnierformat falsch, der Preflop-Löser gehört nur in tiefe Cash-Spots (oder muss Stacktiefe/ICM/Blindanstieg lernen); (2) die Prüfstände gegen Pool-Bots belohnen Ausbeutung, ein Gleichgewichtsspieler verliert dort immer gegen das darauf trainierte Netz, deshalb bleibt GTO Wizard das Maß für „stark gegen Menschen“; (3) Phasen B und C zeigen, ob die Postflop-Suche ohne Preflop-Löser wenigstens gleichauf liegt und ob sie im Heimformat 200 BB ihr Blueprint schlägt.
- **Phase B (21:59–23:15):** `hus?bp=lynx-4-300&streets=turn,river&iters=60&iters_river=150` (Suche **ohne** Preflop-Löser) auf hu480: **+37,9 % [32,1; 43,7] gegen Netz +46,5 → Differenz −8,5 [−14,7; −2,3]**; gegen hus-1 +20,8 [+13,2; +28,5]. Zerlegung der −29,4 von hus-1: rund 25 Punkte Preflop-Löser, rund 8 Punkte Postflop-Suche. Die Postflop-Suche ist im Turnierformat gegen Pool-Bots also immer noch schlechter als das darauf trainierte Netz, aber nur noch knapp signifikant; der Preflop-Löser ist das eigentliche Problem.
- **Phase C (23:15–00:14):** hus-1 gegen lynx-4@300 direkt, HU 200 BB Cash duplicate, 40 Aufgaben × 25 Blätter = 2000 Hände: **−0,6 bb/100 [−62,2; +61,0]**, unentschieden. Die Messung ist für dieses Format viel zu grob: die Standardabweichung je 50-Hände-Aufgabe liegt bei rund 200 bb/100 (viele All-ins bei 200 BB, VPIP ~68 %), für ein Intervall von ±10 bräuchte man rund 75 000 Hände. Auffällig ist der Verlauf: Aufgaben 0–23 im Mittel +103, Aufgaben 24–39 im Mittel −156 (14 von 16 negativ). Seeds sind deterministisch (1000+k), husearch hat kein Zeitbudget, also sollte das Seed-Zufall sein; zur Sicherheit werden die Aufgaben 2 (+455,3) und 30 (−283,3) einzeln nachgerechnet (`data/bench/diag-nacht-repro.txt`).
- **Gesamtdeutung der Nachtdiagnose:** (1) **Hauptleck ist der Preflop-Löser** (rund 25 der 29 Punkte): sein Heads-up-Gleichgewicht ist für 200 BB Cash gerechnet und passt nicht zum 50-BB-Turnier mit alle 10 Hände steigenden Blinds, außerdem spielt es gegen die Pool-Bots nicht ausbeutend. (2) **Die Postflop-Suche** kostet auf hu480 noch rund 8 Punkte gegen das darauf trainierte Netz, Gleichgewicht gegen Ausbeutung. (3) **Selbst im Heimformat 200 BB** ist kein Vorteil der Suche über ihr Blueprint nachweisbar, das frühere +41,8 [−36; +119] und dieses −0,6 [−62; +61] sagen beide nichts. Damit ist die Suche als Lehrer bzw. Orakel für das Wertnetz **nicht belegt**. Nächste Schritte vor der Hetzner-Tranche: (a) hupreflop in `hus` standardmäßig aus (`streets=turn,river`), Preflop-Löser nur in tiefen Cash-Spots; (b) die Ranges der Teilspiel-Lösung aus dem Blueprint statt aus der Heuristik ableiten (`ranges.py` public_ranges/opponent_ranges HU) und auf hu480 gegen das Netz prüfen, Ziel Differenz ≥ 0; (c) eine varianzarme Heimformat-Messung (All-in-EV-Bereinigung wie beim Slumbot-Protokoll oder fester dritter Gegner) statt 2000 roher Hände; (d) der 1000er-Test der River-Daten (rund 0,06 €) ist davon unabhängig und kann nach Jakobs Go laufen, die 500k-Tranche erst, wenn (b) die Suche als besser belegt hat.
- **Nachprüfung Phase C (00:52–00:58):** Aufgaben 2 und 30 einzeln nachgerechnet ergaben exakt +455,3 und −283,3, die Messung ist deterministisch, der Vorzeichenwechsel zwischen den Hälften war Seed-Zufall.
- **30.10. 09:04, Umbau und Messung D/E (`bench_hus1bp.py`, `data/bench/hus1bp.txt`):** Standard der Suche jetzt `streets=turn,river` ohne Preflop-Löser und `ranges=pre` (Blueprint-Ranges, 4.9). Gemessen wird auf hu480 gepaart: D `hus1bp-lynx-4-300` (ranges=pre) und E `hus1bpf-lynx-4-300` (ranges=pre,flop), jeweils gegen Netz +46,5, gegen die Heuristik-Suche hus1np +37,9 (Phase B) und gegen hus-1 +17,1. Erfolgskriterium: Differenz zum Netz ≥ 0 (Phase B lag bei −8,5). Der erste Lauf von D starb nach 85 Minuten mit dem Elternprozess (Ursache unbekannt, kein Traceback); seitdem sichert `run_set` jeden fertigen Block (`bench/partial-*.json`, `resume=True`) und meldet Zwischenstände.
- **Messung D fertig (10:59–12:15):** `hus1bp-lynx-4-300` (streets=turn,river, ranges=pre) auf hu480: **+41,2 % [35,5; 47,0]**. Gegen Netz +46,5 → **−5,2 [−11,6; +1,1]** (nicht mehr signifikant); gegen die Heuristik-Suche hus1np +37,9 → **+3,3 [−0,3; +7,0]** (knapp nicht signifikant); gegen hus-1 +17,1 → +24,2 [+16,6; +31,7]. **Deutung:** Die Blueprint-Ranges bringen rund 3 Punkte, die Lücke zum Netz ist von −29 (hus-1) über −8,5 (ohne Preflop-Löser) auf −5,2 geschrumpft. Die Suche ist auf hu480 jetzt statistisch gleichauf mit dem darauf trainierten Netz, aber noch nicht nachweisbar besser. Was bleibt, ist vermutlich der Grundkonflikt Gleichgewicht gegen Ausbeutung: das Netz nutzt die Pool-Bots aus, die Suche spielt im Teilspiel unausnutzbar. Messung E (zusätzlich Flop-Aktionen vom Netz bewertet) läuft.
- **Messung E fertig (12:15–14:05):** `hus1bpf-lynx-4-300` (ranges=pre,flop) auf hu480: **+44,0 % [38,3; 49,7]**. Gegen Netz +46,5 → **−2,5 [−8,7; +3,7]** (gleichauf); gegen die Heuristik-Suche hus1np +37,9 → **+6,0 [+1,8; +10,3]**, erstmals signifikant besser; gegen hus-1 +26,9 [+19,1; +34,7]; gegen D (nur Preflop vom Netz) +2,7 [−1,4; +6,8]. **Die Reihe Suche gegen Netz lautet jetzt −29,4 → −8,5 → −5,2 → −2,5** (Preflop-Löser raus, Blueprint-Ranges preflop, Blueprint-Ranges preflop+flop). Die Ranges waren also tatsächlich der zweite Hebel nach dem Preflop-Löser. `ranges=pre,flop` ist seit 14:08 Standard der Suche (rund 0,5 s je Straße zusätzlich). Auf hu480 ist damit das Ende der Fahnenstange erreicht: gegen die Pool-Bots gewinnt das ausbeutende Netz, ein Gleichgewichtsspieler kann dort höchstens gleichziehen. Die nächste Messung für die Suche gehört zu Slumbot und GTO Wizard, wo Gleichgewicht belohnt wird.
- **Slumbot hus-4 (15:02–17:20, 3000 Hände, 4 Sitzungen):** genau diese Konfiguration (streets=turn,river, ranges=pre,flop) gegen Slumbot: **roh −41,0 [−132; +50], All-in-EV −48,7, bereinigt −39,0 [−95; +17]** (6.7). Nicht signifikant schlechter als das Netz (+0,2), aber in der Reihe hus-1 −12,6 / hus-3 −23,7 / hus-4 −39,0 bleibt die Suche gegen Slumbot hinter dem Netz. Aufschlüsselung roh nach Beitrag in bb/100: **River −99 (Netz −65, hus-3 −32)**, Position BB −62 (Netz −4), Showdown-Hände −4,8 bb je Hand (Netz −2,7), Pots ab 50 BB −67 (Netz −46); preflop, flop und turn etwa wie das Netz. **Deutung:** Das Leck ist das River-Spiel der Suche, also Calls und Bluffs am Showdown, und das ist ein Range-Problem: die Blueprint-Ranges unterstellen „der Gegner spielt wie unser Netz“, Slumbot tut das nicht, und ohne Preflop-Löser kommen bei 200 BB die Preflop-Ranges eines Turnier-Netzes herein. hus-3 mit Preflop-Löser war gegen Slumbot die beste Suche (−8,7 roh über 8167 Hände). Das ist das Spiegelbild der hu480-Ergebnisse: dort passt das Netz als Gegnermodell, bei Slumbot nicht. **Nächster Schritt (noch nicht gebaut): formatabhängige Konfiguration.** Tiefes Cash: Preflop-Löser an, und die Preflop-Ranges direkt aus seiner CFR-Lösung ziehen (exakte Gleichgewichts-Ranges je Preflop-Linie statt Heuristik oder Blueprint). Turnier: wie jetzt. Danach GTO Wizard als Maß gegen Menschen-nahes Gleichgewicht.
- **Messung V fertig (18:08–18:52, `bench_hus1v.py`):** `hus1v-lynx-4-300` = Konfiguration E, aber die River-Teilbäume im Turn-Baum durch das Wertnetz `kaggle-t2-big` ersetzt (2048×3, trainiert auf 752 000 Situationen, davon 252 000 von echten Suchblättern). hu480: **+43,1 % [37,3; 48,9]**; gegen E (exakte River-Teilbäume) +44,0 → **−0,8 [−3,9; +2,3]**, gepaart und damit praktisch gleich stark; gegen Netz −3,3 [−9,4; +2,8]; gegen die Heuristik-Suche +5,2 [+0,8; +9,6]. Laufzeit der Messung 44 statt 110 Minuten, je Turn-Entscheidung 1,1 statt 4,8 s. **Deutung:** Die erste Stufe der DeepStack-Leiter trägt. Das River-Netz ersetzt die exakte River-Lösung an den Blättern ohne messbaren Verlust und macht die Turn-Suche 4,4-mal schneller. Damit wird die Flop-Suche (hus-2-Baum, bisher 17 bis 62 s je Entscheidung) bezahlbar, und der Weg zu Turn-Daten und Turn-Netz ist offen. Das Netz ist noch nicht Standard (Spec-Parameter `vnet=kaggle-t2-big/vnet-river`, braucht den Checkpoint lokal).
- **Abend 30.10., drei Schritte parallel (Jakob: „mach weiter“):** (1) **Flop-Suche mit Netz-Blättern** lokal gemessen: 1,6 s je Flop-Entscheidung (hus-2-Baum k 6/6, 1323 Knoten) statt 17 bis 62 s; mit k 4/4 0,9 s. Messung F (`bench_hus2v.py`, `hus2v-lynx-4-300`: streets=flop,turn,river, iters_flop 40, vnet) auf hu480 gegen V, E und Netz gestartet 20:11. (2) **Tranche 3** (weitere 252 000 Blatt-Situationen, Scherben 1010–1019) auf cpx62 gestartet 20:12, ≈ 0,50 €. (3) **Gleichgewichts-Ranges für tiefes Cash** gebaut: `hupreflop.path_ranges` liefert die Ranges beider Spieler nach dem tatsächlichen Preflop-Verlauf als Produkt der Durchschnittsstrategie (auch für abgeschlossene Verläufe), `equilibrium_ranges(obs)` rastert den Stack wie `decide`; in `bpranges` der Modus `eq` (Preflop aus dem Gleichgewicht, Zuordnung über `sb_seat`, braucht kein Netz), Spezifikation `ranges=eq` oder `eq,flop`. Test `test_gleichgewichts_ranges_preflop_fuer_cash`. Damit **Slumbot hus-5** gestartet 20:15: `streets=preflop,turn,river&ranges=eq,flop&vnet=kaggle-t2-big/vnet-river`, 3000 Hände, 2 Sitzungen, also die Cash-Konfiguration (Preflop-Löser an, Gleichgewichts-Ranges, Netz-Blätter). Erwartung: besser als hus-4 (−39) und hus-3 (−23,7); Ziel ≥ Netz (+0,2).
- **Messung F fertig (20:11–22:39):** `hus2v-lynx-4-300` (Suche ab Flop, k 6/6, 40 Flop-Iterationen, Netz-Blätter) auf hu480: **+37,3 % [31,5; 43,1]**; gegen Netz −9,2 [−15,7; −2,7], gegen V (Turn-Suche mit Netz) **−5,8 [−11,4; −0,3]**, gegen E −6,7 [−12,6; −0,8]. Die Flop-Suche in dieser Form ist also **signifikant schlechter** als die Turn-Suche, obwohl sie mit 1,6 s je Entscheidung endlich bezahlbar wäre. Wahrscheinliche Ursache: die grobe Abstraktion (6 von 47 Turn- und 6 von 46 Rivercards, 40 Iterationen, 1323 Knoten) und der Netzfehler, der sich über zwei Straßen aufsummiert. Konsequenz: der Flop bleibt beim Blueprint, `streets=turn,river` bleibt Standard. Ein zweiter Versuch lohnt erst mit mehr Karten (k 12/12) und einem Turn-Netz, das die Turn-Teilbäume ersetzt.
- **HandHQ-Extraktion (H11, Jakob 20:50 „fang schon mal an“), fertig 22:57 nach 2 h 21 min mit zwei Prozessen niedriger Priorität:** neues Modul `humandata.py` (Hand mit der Engine nachspielen wie `phh.replay`, Dollar × 100, heads-up Button = SB, nur gezeigte Spieler liefern Zeilen: 49 Merkmale feat-2, Aktionsmaske und Aktion im 8er-Raster, Metadaten Straße/Position/Spielerzahl/Pot/Einsatz/Stack/Art/Betrag/Handklasse/Spieler), CLI `data humandata`, Tests `test_humandata.py` (3). **Ergebnis: 5,97 Mio. Hände, 1,47 Mio. mit gezeigten Karten, 1,21 Mio. nachgespielt, 7,35 Mio. Entscheidungen** in 120 Scherben (`data/humans/actions/`, 245 MB); übersprungen 239 000 Straddle-Hände, 15 700 Reihenfolge-Fälle, 1 000 Stack/Blind-Fälle. Verteilung in der Stichprobe: je Straße rund 70 % Check/Call, preflop Raises meist Pot-Größe (17 %), postflop meist halber Pot, Drittel und Min-Raise; Tische mit 3 bis 9 Spielern, 6 und 8–9 am häufigsten, kein Heads-up. **Kein einziger Fold in den Daten** (wer foldet, zeigt nicht): das Modell lernt P(Aktion | Hand, weitergespielt); Fold-Raten müssen aus den unverzerrten Häufigkeiten kommen, Flop- und Turn-Ranges unterschätzen aufgegebene Bluffs, River-Ranges sind fast unverzerrt. Nächster Schritt: Menschen-Politiknetz darauf trainieren (Kaggle, Blueprint-Schnittstelle), Abnahme per Log-Likelihood der gezeigten Karten auf Hold-out, dann `ranges=human` in der Suche.
- **Slumbot hus-5 fertig (20:15–23:45, 3000 Hände, 2 Sitzungen):** Cash-Konfiguration `streets=preflop,turn,river&ranges=eq,flop&vnet=kaggle-t2-big/vnet-river`: **roh −5,5 [−72; +61], All-in-EV −10,4, bereinigt +0,0 [−50; +50]** (6.7). Damit liegt die Suche gegen Slumbot erstmals gleichauf mit dem Netz (+0,2 über 10 000 Hände) statt dahinter (hus-3 −23,7, hus-4 −39,0). Die Gleichgewichts-Ranges aus dem Preflop-Löser haben den River-Verlust von hus-4 behoben, das Netz als Blatt hat nichts gekostet. Zwischenstand bei 1000 Händen war +93 [+5; +181], am Ende Varianz; das Intervall ±50 verlangt für eine Aussage „besser als das Netz“ etwa 10 000 Hände. Deutung beider Formate: hu480 will das Netz als Gegnermodell (Pool-Bots spielen wie unser Netz), Slumbot will das Gleichgewicht; die formatabhängige Konfiguration ist damit bestätigt und sollte in der Spezifikation automatisch gewählt werden (Turnier mit Blindanstieg → `turn,river` + `pre,flop`; tiefes Cash → `preflop,turn,river` + `eq,flop`).
- **Wertnetz auf 1 Mio. Situationen (Kaggle, 23:23–00:12, 2048×3, 60 Epochen, 47 min T4):** 500 000 breite + 504 000 Blatt-Situationen (Tranchen 1–3). Hold-out 0,0192; Kunstverteilung EV-Fehler 0,0035 (unverändert); **Blatt-Prüfsatz EV-Fehler 0,0081 Pot, 95 %-Quantil 0,022, Maximum 0,042** (vorher 0,035 / 0,19 / 0,23). **Damit ist das Abnahmeziel für die Blätter (EV-Fehler unter 0,02) erreicht.** Die Reihe lautet 0,121 (nur breit) → 0,035 (252k Blatt) → 0,0081 (504k Blatt): die zweite Blatt-Tranche hat den Fehler noch einmal um den Faktor 4 gedrückt, Daten aus der echten Suchverteilung sind der Hebel. Checkpoint `data/valuenet/kaggle-t3-big/vnet-river.pt`, Kopie als Standardname `data/valuenet/vnet-river-1.pt` (`vnet=vnet-river-1`). Gesamtkosten der drei Tranchen ≈ 1,70 €.
- **Menschenmodell human-1 (H11 Schritt 2, Kaggle 00:10, 49 s):** Politiknetz 49 → 512 → 512 → 8 auf 7,2 Mio. HandHQ-Entscheidungen, Hold-out jede 50. Hand: NLL 0,720 gegen 0,95–1,06 der Häufigkeits-Vergleichslinie, Treffer 78 % preflop, 73–75 % postflop. Zum Vergleich sagt lynx-4@300 dieselben menschlichen Entscheidungen mit NLL 2,26 und 35,6 % Treffern vorher (preflop 9 %): Lynx spielt völlig anders als Normalspieler. Als Bot (`nn?run=human-1@1`) foldet es nie (keine Folds in den Daten), ist also eine Calling-Station mit Raise-Instinkt, und schlägt lynx-4 heads-up in einem Schnelltest (−64 / −76 bb/100 über je 300 Hände, Intervalle riesig): Lynx blufft gegen Stationen zu viel (V1-Befund). **Messung H (00:12–05:22):** Suche `auto=1&opp=human-1@1&vnet` (Gegneraktionen mit dem Menschenmodell bewertet): hu480 +42,5 [36,8; 48,2], gleich wie V und E; **mensch480 +95,1 [89,5; 100,7] gegen Netz +115,1 → −20,0 [−25,5; −14,5], signifikant schlechter.** Zwei Gründe: ohne Fold-Modell sind die Gegner-Ranges zu breit, und mensch480 besteht aus unseren eigenen Stilbots, auf die das Netz trainiert ist, nicht aus HandHQ-Menschen. Konsequenz: erst ein Fold-Modell (zweite Extraktion aller Entscheidungen ohne Karten → P(fold | Zustand), Karten der Folder als Bayes-Rest), dann `ranges=human` gegen den Menschen-Bot selbst und gegen GTO Wizard messen. `opp=human-1` ist nicht Standard. Neu dazu: `auto=1` (Formatwahl je Hand) und `opp=<Lauf>@<Ckpt>` als Spezifikationsparameter der Suche, `teacher.py` (Suche als Lehrer: sammeln und nachtrainieren, CLI `train teacher-collect` / `teacher-fit`, Serverskript `cloud/run-teacher.sh`).
- **Slumbot hus-5 Endstand (10 000 Hände, 20:15–05:55, 4 Sitzungen ab 00:01):** roh −15,3 [−52; +22], All-in-EV −7,4 [−41; +26], **bereinigt −8,0 [−35; +19]** (6.7). Nach 3000 Händen stand es bei +0,0, nach 1000 bei +93; der Endstand liegt leicht unter null, das Intervall schließt die Null ein. Gegen das Netz (+0,2 [−29; +30] über 10 000) ist der Unterschied nicht signifikant. **Antwort auf „schlagen wir Slumbot mit der Suche?“: nein, nicht nachweisbar; die Suche liegt gegen Slumbot auf dem Niveau des Netzes, eher einen Hauch darunter.** Der Fortschritt gegenüber hus-3 (−23,7) und hus-4 (−39,0) bleibt, aber ein Plus gegen Slumbot braucht mehr als Gleichgewichts-Ranges: mehr Iterationen (jetzt bezahlbar), breitere Einsatzgrößen, und vor allem den Preflop-Löser, der bisher ein Postflop-Modell statt echter Postflop-Werte nutzt.

- **Fold-Modell human-fold-1 und erste Messung gegen den Menschen-Bot (31.10. 06:30–08:01, `bench_humanopp.py`, `data/bench/humanopp.txt`):** Das Menschenmodell human-1 kennt keine Folds (nur gezeigte Hände in HandHQ). Deshalb zweite, kartenfreie Extraktion aller 55,5 Mio. Entscheidungen (`data humanpublic`, `public-*.npz`, mit Folds) und daraus `ai/humanfold.py`: f(s) = P(Fold | öffentlicher Zustand, 20 Merkmale) und g(c | s) = Verteilung der gezeigten 169 Klassen; Weiterspiel-Faktor je Kombination = clip(g·(1−f)/P(c|s), 0, 1) (Bayes-Rest), in der Suche als `oppfold=human-fold-1` vor jeder Nicht-Fold-Aktion des Gegners auf dessen Range multipliziert. Plausibel: BB gegen UTG-Raise 6-max foldet 75 %, bleibt mit AA 98 %, 93o 2 %. **Messung Suche gegen `nn?run=human-1@1` HU 40/100 BB duplicate, je 480 Hände:** 40 BB: Netz −4, A Standard-Ranges −7, B `opp=human-1@1` −95, C B+`oppfold` **−127 [−191; −63]**; 100 BB: Netz +142, A +392, B +271, C +385 [+203; +566]. Riesige Varianz (Blöcke ±200 bb/100), weil der Gegner nie foldet: jede Hand geht groß zum Showdown. **Deutung:** Gegen eine Calling-Station, die nie foldet, ist das Fold-Modell falsch (es nimmt 75 % Folds an, der Gegner callt immer) und verengt die Gegner-Range zu Unrecht; bei 40 BB kostet das signifikant. Die Messung prüft also nicht das Modell, sondern einen Zerrbild-Gegner. Konsequenz: **Menschen-Bot mit Fold-Verhalten gebaut**, `nn?run=human-1@1&fold=human-fold-1` (NNAgent.fold_model: bei offenem Einsatz wirft er mit 1 − Weiterspiel-Faktor seiner Hand weg, sonst Netz-Aktion ohne Fold; AA 0,2 %, KQs 1,3 %, 93o 96,5 %, 72o 97,1 % Fold gegen 3-BB-Raise). **Netz lynx-4@300 gegen diesen Menschen-Bot über je 10 000 Hände: 40 BB +13,5 [−5; +32], 100 BB −21,1 [−43; +0,4]** (ohne Fold: −10,8 bzw. −13,3 mit viel breiterem Intervall). Das Blueprint-Netz schlägt die Nachbildung eines 25NL-Normalspielers heads-up NICHT, bei 100 BB verliert es eher. Das ist der Prüfstand, der Jakobs Ziel (gegen Menschen gewinnen) am nächsten kommt; zweite Messreihe der Suche gegen diesen Gegner gestartet (`bench_humanopp2.py`, 6 Blöcke × 120 Hände je Zelle, 5 Worker, 08:08). Tests: `test_humanfold.py` (3), `test_humandata.py` (4).

- **Messung 2 der Suche gegen den Menschen-Bot MIT Folds (31.10. 08:08–08:54, `bench_humanopp2.py`, `data/bench/humanopp2.txt`, je 720 Hände, 6 Blöcke):** 40 BB: Netz +76 [−32; +183], A Standard +53, B `opp=human-1@1` **+70 [+9; +130]**, C B+`oppfold` +44; 100 BB: Netz +59, A +26, B +38, C +27, alle Intervalle ±70 bis ±120. **Keine Variante unterscheidet sich nachweisbar**, die Suche ist gegen den Menschen-Bot nicht besser als das Netz, B (Gegnermodell ohne Fold-Faktor) ist die stabilste Suchvariante (alle sechs 40-BB-Blöcke positiv), der Fold-Faktor bringt nichts Messbares. Mit Folds läuft die Suche doppelt so schnell (Hände enden früher). Für ±25 bb/100 braucht es ~10 000 Hände je Zelle, lokal ~11 h, auf Hetzner ~2 h; als Server-Lauf nach der Lehrer-Sammlung vorgesehen (`bench_humanopp_srv.py`).
- **Lehrer-Sammlung auf Hetzner gestartet (lehrer-1, cpx62, 09:00 Ortszeit, Jakob: „mach alles“):** `cloud/run-teacher.sh 16 120`: 16 Prozesse, je 4 Gegner (lynx-4@300, Menschen-Bot mit Folds, mensch-2, mensch-4) × 4 Stacks (25/50/100/200 BB) × 240 Hände duplicate = 61 440 Hände, Suche `auto=1&iters=60&iters_river=150&threads=1&vnet=vnet-river-1`. Datenupload per `cloud/upload-teacher-data.sh <IP>` (Wertnetz, lynx-4@300, human-1, Fold-Modell, Mensch-Bots, Liga-Datei), `teacher.resolve_opponent` löst `mensch-N` über `mensch-25nl.json` auf. Erster Start hatte Last 27–50 auf 16 Kernen (Torch-Threads je Prozess), mit `OMP_NUM_THREADS=1` neu gestartet 09:00. Erwartung ~3 h ≈ 0,75 €, dann `teacher-fit lynx-4@300 → lynx-5t` und Gate.

- **Stufe 2 vorbereitet: Turn-Wertnetz-Daten (31.10. 09:10–09:40):** `valuedata` kennt den Modus **`turn-leaf`**: Flop-Zustand mit synthetischen Ranges, Flop-Baum mit 8 gezogenen Turn- und 4 Rivercards exakt gelöst (40 It.), Ranges an den Turn-Anfängen (`Tree.turn_roots`, neu in `build_tree`) unter der Durchschnittsstrategie ausgelesen, bis zu 12 davon je Flop mit dem **River-Wertnetz als Blatt** gelöst (DeepStack-Rezept: das Turn-Netz lernt aus Lösungen, deren Blätter das River-Netz liefert). Gemeinsame Hilfsfunktion `_roots_rows` für river-leaf und turn-leaf; `--vnet` an der CLI; `solve_sample` nimmt für turn/flop ebenfalls ein Netz. Probe: 2 Flop-Seeds → 20 Turn-Zeilen, 1,35 s je Turn-Lösung (100 It.) lokal; Label-Prüfung gegen exakte Turn-Lösungen (150 It., alle Rivers exakt): EV-Fehler der Labels im Mittel 0,014 Pot, max 0,054 (5 Zeilen). Das Wertnetz-Merkmal kodiert Straße und Boardlänge bereits, ein gemeinsames Netz für River+Turn ist möglich. Suche: neue Option **`leaf=4`** (Flop-Teilbäume enden an den Turn-Anfängen, alle 47 Turncards, kein Ziehen) für den Einsatz des Turn-Netzes. Tests: `test_valuedata.py` (5), `test_husearch.py` (+1 leaf). Volle Testsuite 220 grün (`data/tests-31-10.txt`).
- **Server-Kette auf lehrer-1 (`cloud/run-after-teacher.sh`, gestartet 09:12):** wartet auf die Lehrer-Sammlung, dann (1) Benchmark Suche vs Menschen-Bot mit Folds mit 16 Prozessen (`cloud/bench_humanopp_srv.py`, 64 Blöcke = 7680 Hände je Zelle, ~1,5 h), dann (2) erste Turn-Tranche `run-vdata.sh turn-leaf 0 10 2000` (20 000 Flop-Seeds → ~240 000 Turn-Zeilen, geschätzt 4–5 h). Gesamt lehrer-1 ≈ 8–9 h ≈ 2,1 €. Danach: pull, Kaggle-Training vnet-2 (River+Turn gemischt), Suche mit `leaf=4` am Flop messen.

- **Lehrer-Sammlung fertig, lynx-5t trainiert (31.10. 10:20–10:45):** lehrer-1 brauchte 1 h 22 min (0,35 €) für 16 × 16 Matches: **41 730 Lehrer-Zeilen** (nur Turn/River, da die Suche nur dort entscheidet; gegen die Stil-Menschen kaum Zeilen, weil deren Hände früh enden). `train teacher-fit --kl 0.5` → **`data/rl/lynx-5t/ckpt_000001.pt`**: Übereinstimmung der Top-Aktion mit der Suche 29 % → 64 %, Kreuzentropie 2,61 → 0,98, KL zum Anker 0,49 (Hold-out 4173 Zeilen). Variante `--kl 2.0` (lynx-5t-k2): 40 %.
- **Entdeckung beim Gate: das Sampling kostet im Heads-up-Cash massiv.** Kontrolle `nn?run=lynx-4@300&greedy=1` gegen das gesampelte lynx-4@300, 100 BB, 10 000 Hände duplicate: **+97,7 bb/100 [+58; +137]**. Das Netz mischt (Entropie 0,79 nats je Entscheidung, die Suche 0,48), und die gestreuten Nebenaktionen verlieren gegen jeden Gegner. Gesampelt verliert lynx-5t gegen lynx-4 (−14/−55/−77 bei 40/100/200 BB, Entropie 1,06, der Lehrer-Fit verbreitert die Verteilung), greedy gewinnt es gegen das gesampelte lynx-4 (+16/+33/+39), greedy gegen greedy ist gleich (−2,8 [−22; +17]). **Gegen den Menschen-Bot mit Folds (10 000 Hände je Zelle): greedy lynx-5t +64,0 [+50; +78] bei 40 BB und +65,5 [+46; +85] bei 100 BB, greedy lynx-4 +3,3 bzw. −21,9.** Der Lehrer-Fit bringt gegen den Menschen-Nachbau also 60–85 bb/100, gegen lynx-4 selbst nichts. Offen: Greedy ist deterministisch und damit von Menschen ausbeutbar (später Temperatur statt Vollgreedy), und ob Greedy auch im Turnierformat gewinnt. Läuft: Prüfstand hu480/mensch480/mix960 für lynx-5t-g, lynx-4-300-g, lynx-5t-s (`bench_lynx5t_sets.cmd`, `data/bench/lynx5t-sets.txt`) und Slumbot 3000 Hände für greedy lynx-5t (`data/bench/slumbot-lynx-5t-g.txt`).

- **Prüfstand lynx-5t fertig (31.10. 10:59, `data/bench/lynx5t-sets.txt`, Turnierformat hu480/mensch480/mix960):** lynx-4@300 gesampelt (Referenz) 46,5 / 115,1 / 59,3 %; **lynx-4@300 greedy 55,8 / 128,2 / 79,8 %** (neuer Bestwert auf allen drei Sets, mix960 +20 Punkte); lynx-5t greedy 35,6 / 103,2 / 61,3 %; lynx-5t gesampelt 28,5 / 81,7 / 35,5 %. Deutung: Greedy hilft überall (die gestreuten Nebenaktionen kosten auch im Turnierformat), aber der Lehrer-Fit lynx-5t ist gegen den Bot-Pool schlechter als lynx-4 – er hat gelernt, was die Suche gegen Menschen-Bots tut, und das ist gegen Pool-Bots nicht besser. lynx-5t ist damit ein Menschen-Ausbeuter (HU-Cash gegen Mensch+Fold +64/+65 statt +3/−22), kein allgemeiner Fortschritt.
- **Slumbot lynx-5t greedy, 3000 Hände (`data/bench/slumbot-lynx-5t-g.txt`):** bereinigt **+35,3 bb/100 [−6; +77]** (roh +35,3, All-in-EV +34,6, Kartenglück −3). Nicht signifikant, aber die bisher beste Slumbot-Zahl (lynx-4@300 gesampelt +0,2 bei 10 000 Händen, lynx-3 −17).
- **Server-Benchmark Suche vs Menschen-Bot mit Folds fertig (lehrer-1, 16 Prozesse, 64 Blöcke = 7680 Hände je Zelle, `data/bench/humanopp_srv.txt`):** 40 BB: A-standard +19,7 [+1,8; +37,5], B-human +17,8 [−1,3; +36,8], **C-human+fold +30,4 [+13,3; +47,5]**, Netz lynx-4@300 gesampelt +2,9 [−20; +26]; 100 BB: A +23,8 [−2,9; +50,4], **B +33,6 [+5,8; +61,4]**, C +29,3 [+3,7; +54,9], Netz **−40,3 [−68; −12]**. Die Suche schlägt das gesampelte Netz bei 100 BB um ~65 bb/100 und ist in allen Varianten positiv, Fold-Faktor bei 40 BB am besten – aber alle Suchvarianten (+20…+34) liegen klar unter dem greedy lynx-5t (+64/+65 bei 10 000 Händen). Der Lehrer-Schüler schlägt also seinen Lehrer gegen diesen Gegner; vermutlich weil die Suche preflop (Netz gesampelt) und in ihren gemischten Strategien noch streut, der greedy Schüler nicht.
- **Turn-Tranche läuft (lehrer-1, ab 11:28 Ortszeit, `run-vdata.sh turn-leaf 0 10 2000`, 16 Prozesse × 1 Thread, voll ausgelastet):** 2,6 s je Flop-Seed → ~87 min je Scherbe (2000 Seeds ≈ 20 000 Turn-Zeilen), 10 Scherben ≈ 14,5 h ≈ 3,6 € statt der geschätzten 4–5 h. Jede fertige Scherbe ist einzeln nutzbar und wird abgeholt.

- **Temperatur statt Vollgreedy (31.10. 12:14–13:05, `nn?run=…&temp=T`, `data/bench/temp-hu.txt`, HU-Cash je 10 000 Hände):** p ∝ p^(1/T), T=1 Sampling, T=0 greedy. **lynx-4@300** gegen Mensch+Fold bringt die Temperatur fast nichts (40 BB +6 / +12 / +11 / +8 / +7 bei T = 1 / 0,7 / 0,5 / 0,3 / 0; 100 BB −23 / −22 / −15 / −16 / −18), gegen das gesampelte lynx-4 steigt der Gewinn monoton mit der Schärfe: +24 / +43 / +66 / +87 (T 0,7 → 0). **lynx-5t** ebenso monoton: gegen Mensch+Fold 40 BB +40 / +47 / +55 (T 0,7 / 0,5 / 0,3; greedy +64), 100 BB +52 / +59 / +71 (greedy +66); gegen lynx-4 gesampelt −30 / −1 / +22 (greedy +33). Ausbeutbarkeits-Duelle: lynx-4 T=0,5 gegen lynx-4 greedy **−63** [−79; −47], T=0,3 gegen greedy −43; lynx-5t greedy gegen lynx-4 greedy +10 [−1; +22]; lynx-5t T=0,5 gegen lynx-4 T=0,5 −13 [−25; −1]. **Fazit: Gegen alle vorhandenen (nicht anpassungsfähigen) Gegner ist Greedy durchweg am besten, jede Temperatur > 0 kostet; eine echte Ausbeutbarkeit von Greedy lässt sich nur mit einem lernenden Ausbeuter messen (`train exploit`, nächster Schritt).** Das Netz lynx-4 bleibt gegen den Menschen-Bot bei 100 BB bei jeder Temperatur negativ – der Lehrer-Fit (lynx-5t) ist dort der eigentliche Hebel, nicht die Schärfe. Prüfstand T=0,5/0,3 läuft (`temp-pruefstand.txt`).
- **Turn-Wertnetz, erste Scherbe (lehrer-1, 12:53):** `turn-leaf-00000000.npz`, 22 136 Zeilen aus 2000 Flop-Seeds (11 je Flop), 0 Fehler, Nullsummen-Rest 0,021 Pot, 3,3 s je Lösung je Prozess; nach `data/valuenet/hetzner-turn/` geholt und als privates Kaggle-Dataset **`YOUR_KAGGLE_USER/lynx-vdata-turn`** angelegt (`cloud/kaggle-upload-turn.sh create|version`). Kaggle-Kernel **`cloud/kaggle/lynx-train-vnet2/`** (River + River-Leaf + Turn-Leaf gemischt, Turn-Scherben doppelt, je letzte River-Leaf- und Turn-Leaf-Scherbe als sauberer Test je Straße in test.json, optional RESUME von vnet-river-1). **Baseline: vnet-river-1 auf Turn-Zeilen MAE 0,090 Pot** (River 0,019) – ohne Turn-Training ist `leaf=4` unbrauchbar.

- **Prüfstand mit Temperatur (13:05–13:20, `temp-pruefstand.txt`, hu480 / mensch480 / mix960):** lynx-4@300 gesampelt 46,5 / 115,1 / 59,3; **T=0,5 53,5 / 127,2 / 75,5; T=0,3 53,3 / 127,3 / 78,5; greedy 55,8 / 128,2 / 79,8**; lynx-5t T=0,5 35,0 / 98,4 / 57,2 (greedy 35,6 / 103,2 / 61,3). Auch im Turnierformat monoton: je schärfer, desto besser, T=0,3 praktisch gleich greedy. Der Live-Berater (`pc.cmd live`) spielt ohnehin greedy (ohne `--mischen`), die Liga-/Prüfstand-Referenz war bisher gesampelt – **neue Referenz für Vergleiche: `nn?run=lynx-4@300&greedy=1` (lynx-4-300-g).** Ausbeuter-Test (`train exploit`, Start lynx-4@300) läuft gegen greedy, gesampelt, T=0,3 und lynx-5t greedy (`exploit-greedy.txt`).

- **Ausbeuter-Test Greedy vs Sampling (13:22–17:31, `exploit_greedy.cmd` → `data/bench/exploit-greedy.txt`; Laptop war ~13:35–17:10 im Ruhezustand):** `train exploit <Prüfling> --init lynx-4@300` (40 Iterationen gegen 5 Kopien, ROI auf 48 frischen Schemata, kleiner = robuster): **lynx-4 greedy −15,0 % [−26,7; −3,3]**, lynx-4 gesampelt −3,8 % [−18,4; +10,9], lynx-4 T=0,3 +8,7 % [−3,2; +20,7], **lynx-5t greedy +24,6 % [+8,6; +40,5]**. Greedy lynx-4 ist mit dem besten verfügbaren Werkzeug nicht ausbeutbarer als Sampling, eher robuster → **lynx-4@300 greedy ist Standard und Referenz.** lynx-5t (Lehrer-Fit auf Menschen-Gegner) ist dagegen deutlich ausbeutbar: ein Menschen-Ausbeuter, der sich selbst ausbeuten lässt – nur gegen Menschen-Gegner einsetzen, nicht gegen lernende/starke Gegner.
- **Turn-Scherben 0–3 geholt (17:18): 88 252 Zeilen, 0 Fehler** (`data/valuenet/hetzner-turn/`), Kaggle-Dataset `lynx-vdata-turn` Version „Scherben0-3“, Kernel `lynx-train-vnet2` gestartet (Test = Scherbe 3). Server: 84 min je Scherbe, Ende Scherbe 9 gegen 02:00.

- **Erstes Turn-fähiges Wertnetz vnet-2 (Kaggle T4, 17:33–18:35, 62 min, `data/valuenet/vnet-2.pt`, Protokoll `data/valuenet/kaggle-vnet2/`):** 2048×3, 60 Epochen, 1 111 280 Zeilen = 500k River + 19 River-Leaf-Scherben + 3 Turn-Leaf-Scherben (66k Zeilen, doppelt gewichtet); Hold-out MAE 0,0209 Pot. Sauberer Test auf zurückgehaltenen Scherben: River-Leaf 0,0338, **Turn-Leaf 0,0544 Pot** (vnet-river-1 auf Turn-Zeilen 0,090). Lokal: Turn-Probe MAE 0,090 → 0,051, EV-Fehler 0,047 → 0,034 Pot; River-Orakel MAE 0,047 → 0,053 (etwas schlechter am River, EV-Fehler aber 0,041 → 0,029). Erste Flop-Suche mit `leaf=4` (alle 47 Turns, Turn-Blätter per vnet-2) läuft, ist aber 7× langsamer als leaf=5 mit 6×6 gezogenen Karten (12,6 s statt 1,6 s bei 60 It.) – für den Einsatz braucht leaf=4 Turn-Sampling. Mit allen 10 Scherben (~220k Turn-Zeilen, Server fertig ~02:00) wird nachtrainiert (vnet-2b).

- **Flop-Suche leaf=4 gegen Referenz (18:50, `scratchpad/leaf4_vs_ref.py`, 6 zufällige Flop-Situationen, 60 It., 4 Threads):** Referenz = leaf=5 mit ALLEN 47 Turns und 6 Rivers (vnet-river-1, 4–21 s). Mittlere Abweichung zur Referenz (EV in Pot / range-gewichteter Strategie-Abstand an der Wurzel, 0…1 / Zeit): **bisher leaf=5 6×6: 0,112 / 0,471 / 2,1 s; leaf=4 alle Turns (vnet-2): 0,144 / 0,233 / 12,6 s; leaf=4 k_turn=8: 0,124 / 0,369 / 2,3 s; leaf=4 k_turn=12: 0,083 / 0,388 / 3,5 s.** Zwei Erkenntnisse: (1) Das Ziehen von nur 6 Turncards macht die Wurzelstrategie der bisherigen Flop-Suche sehr verrauscht (Abstand 0,47 zur gleichen Suche mit allen Turns). (2) Mit dem Turn-Netz halbiert leaf=4 diesen Abstand bei allen Turns, und schon mit 8 gezogenen Turns ist es bei gleicher Rechenzeit näher an der Referenz als 6×6 – obwohl vnet-2 erst 3 Turn-Scherben gesehen hat. Nächster Schritt: `k_turn` auch bei leaf=4 zulassen, dann Benchmark der Suche `leaf=4` gegen Netz und Menschen-Bot (auf dem Server, nach der Tranche), und vnet-2b mit allen 10 Scherben.

- **Suche: neue Optionen `bpgreedy=1` (Blueprint-Netz spielt greedy, wo nicht gesucht wird, also preflop; die Ranges bleiben die gelernte Mischung), `greedy=1` (die Suche nimmt die Top-Aktion ihrer gemischten Strategie) und `k_turn` bei `leaf=4` (Turncards ziehen statt alle 47); Tests in test_husearch.py (19:10).** Messlauf `bench_humanopp3.py` (losgelöst, 8 Prozesse, `data/bench/humanopp3.txt`, 40 Blöcke × 120 Hände je Zelle = 4800 Hände) gegen Mensch+Fold bei 40/100 BB: netz-g, lynx5t-g, C (Server-Basis +30/+29), C-bpg, C-bpg-g, C-5t-bpg (Blueprint lynx-5t), C-leaf4 (vnet-2, leaf=4, k_turn=8). Frage: Schlägt die Suche mit greedy Preflop-Netz und Turn-Netz den greedy Schüler (+64/+66)?

### 6.9 Zieltafel (`ZIELE.md`, `pc.cmd bench ziele lynx-3-300`)

| # | Benchmark | Stufen | Stand lynx-3-300 |
|---|---|---|---|
| 1 | Echte PokerTH-Turniere | 50 Turniere ROI > 0 → 200 Turniere ROI > +20 % und Siegquote > 1/6 | **6 Turniere (28./29.10., PokerTH-Bots „normal“): Plätze 1, 3, 6, 6, 1, 1 → 3 Siege, ROI +70 %** (statistisch noch wertlos, siehe 8.6) |
| 2 | mensch480 | ROI ≥ +100 % → ≥ +120 % | +96,8 % [91,3; 102,2]: knapp unter Stufe 1 |
| 3 | Slumbot | > −15 → > 0 → untere 95-%-Grenze > 0 (je ≥ 20.000 Hände) | lynx-3: bereinigt −17,2 [−38; +4] @10.000, Stufe 1 knapp verfehlt. **lynx-4-300: +0,2 [−29; +30] @10.000 (29.10.), Stufe 1 erreicht, Stufe 2 nicht gesichert** |
| 4 | Ausnutzbarkeit | Ausbeuter ≤ +5 % | +2,3 %: **erreicht** |
| 5 | Endspiel HU 20 BB | nash240 ≥ 0 → kurz240 > +20 % | +17,9 % / +83,3 %: **erreicht** |

Bewusst kein Ziel: Übereinstimmung mit Menschen (Ähnlichkeit ist keine Stärke) und Training auf Slumbot.

---

## 7. Chronik: was versucht wurde, auch Fehlschläge

### Sa 25.10.2026: Grundlagen

- Projekt auf dem Stick gesichtet. Der Nutzer stellte klar: **Visuelle Erfassung ist das Experiment selbst**, keine Abkürzungen über Log oder DOM.
- **Collector gebaut:** Layout, Windows-OCR, Parser, Karten, Analyse, Stabilisierung, Journal, Rekonstruktion, Live-Quelle, Export-Import, Vergleich, Baseline-Advisor. Zunächst nur an einem Preflop-Screenshot geprüft, 36 Tests.
- **KI Stufen 1–3:** Engine, Bot-Pool, Duplicate-Bewertung, Turniermodus, Push/Fold-Nash, Liga mit Rating, Mensch-gegen-Bot-Modus.
- **Erstes Kräftemessen:**
  - Cash: tag +140 bb/100, station −185
  - Turnier: rock +57 % ROI vor tag +39 % (Überleben zahlt sich bei 3 bezahlten Plätzen aus)
- **CEM-Stiloptimierung** → opt-1: Gate vs tag +8,9 % bestanden, Benchmark-SNG bester, Liga-Rating aber unter tag. Hinweis auf **Überanpassung bzw. Nicht-Transitivität**.

### So 26.10.: lernender Bot, Tempo, erste echte Aufnahmen

- **Liga-Training 1** (Start tag): Gate +5,2 auf 120 Schemata, Bestätigung auf 300 Schemata −5,3 → durchgefallen.
- **Liga-Training 2** → opt-2: Gate +8,5, Bestätigung +1,9 [−2,2; 6,1] → aus der Liga genommen.
  - Dabei gefunden: **Alle Gates teilten Seed 777** (abgenutzt). Jetzt hat jeder Lauf einen eigenen Seed.
  - Fazit: Stil-Parameter-Tuning ist ausgereizt.
- **Netz plus PPO:**
  - **nn-1** (ohne Leine) lernte, die Liga auszunutzen: Pool-ROI +84 %, Gate vs rock −8,5 %, Pluribus-Übereinstimmung 63 → 13 %.
  - **Lehre:** Ohne Anker bzw. Leine entsteht Ausbeutung, kein gutes Poker.
- **PHH/Pluribus** eingelesen. Die Engine spielt alle 10.000 Hände identisch nach. BC → pros-1/plu-1 mit 84 % Übereinstimmung, im Turnier schwach (Pluribus kennt kein Kurzstack-Spiel).
- **Prüfstand, numba-Beschleunigung (~85×), MCCFR, Ausbeuter-Test gebaut.** Der Nutzer will Richtung „besser als Pluribus“.
- **pros-2** (große Batches mit 512 Turnieren/It) besteht das **Gate vs rock mit +19,8 %**, Ausbeuter nur +3,8 %. **Durchbruch:** Große Batches waren der Schlüssel.
- **cfr-1** (Tabellen-CFR): schwach und ausnutzbar (+69 %).
- **Zufalls-Gegner, Ausbeuter im Training, Ranges, feat-2, Suche Stufe 1** gebaut → pros-3, pros-r1.
- **Erste echte PokerTH-Aufnahmen** (21:56–23:12, 6er- und 4er-Tisch, mit Log-Export):
  - Erste Auswertung: Aktionen 18 %/5 %
  - Nach Korrekturen am selben Abend (Sitzgedächtnis, Glyphen-Ränge, Timing): **88 %/89 %, Board 100 %, Beträge 99 %**
  - Erkenntnis: PokerTH-Standard ist 50 BB, Blinds alle 9 Hände
- **Speicherprobleme:** Deep CFR plus Nachauswertung gleichzeitig → beide beendet. Danach gilt: nacheinander.
- **Deep CFR** dcfr-1: It 10 +5,3 %, It 20 +5,7 %, It 30 −16,1 % (typischer Deep-CFR-Einbruch).
- **Multi-Format-Training gebaut** (2–10 Spieler, 20–200 BB, Turbo bis langsam) plus Format-Prüfstand.

### Nacht 26./27.10.: erster autonomer Nachtlauf

- **pros-r2** (Multi-Format ab pros-r1@300):
  - Gates @300 und @600 gegen pros-ppo2 nicht bestanden
  - Prüfstand über mehrere Messungen fallend → bei It ~690 abgebrochen
- **pros-r3** (ab pros-r2@350, Lernrate 1,5e-4, Leine 0,5): Gate @200 **+13,3 % bestanden**, @400 und @600 nicht.
- Format-Prüfstand am Morgen: alle Kandidaten im Rauschen gleichauf.
- **Stick-Ausfall 07:10** (Controllerfehler). Deep CFR kam bis It 62, Checkpoint @60, war aber −31 % → **Deep CFR aufgegeben**.

### Mo 27.10.: präziser Prüfstand, Gegnermodell, Live, Mensch-Bots, Lynx

- **Großer Prüfstand** (`praezise`, ±3 statt ±12), `bench compare`, Slumbot-Anbindung (vom Nutzer freigegeben).
  - Ergebnis: **pros-r1@300 ist bester Bot**. Gate-Sieger ≠ bester Bot.
  - Suche Stufe 1 ist schädlich (−18,9) und wird verworfen.
- **Gegnermodell** (opponents, feat-3), `widen_net`. Training **pros-o1** bei @100/@200 gepaart −3,9/−4,4 gegen pros-r1@300 → abgebrochen.
- **Live-Anbindung:** LiveBot mit Live-Rekonstruktion, Handverlauf, Gegnermodell, `live-replay`. Alter Fehler behoben: nur ein Vorschlag pro Sitzung.
- **Slumbot-Leck-Analyse** (pros-r1, ~11.000 Hände): heads-up viel zu eng (Button-Fold 40 %, BB-Fold 51 %), ca. −31 bb/100 Anteil.
  → **act-2** (Min-Raise, ⅓ Pot), `--self-play-seats`, `--table-weights`, `--anchor-min-players`.
- **pros-h1@600 = neuer Bester** (Bestätigung +6,0 [1,4; 10,6]).
  - **Lehre:** Self-Play-Plätze, Ausbeuter, viele HU- und 3er-Tische und die Leine erst ab 4 Spielern bringen zusammen den Erfolg.
  - Slumbot: Button-Fold 40 → 13 %.
- **HandHQ ausgewertet** (5,72 Mio. Hände), **Mensch-Bots** gebaut, Prüfstand **mensch480**.
  - pros-h1@200 lag dort vorn, die Bestätigung gegen @600 mit +4,0 [−0,6; 8,6] bestand aber nicht → **Lynx = pros-h1@600**.
- **Name „Lynx“** vom Nutzer gewählt. Gefragt nach Poker-KI-Wettbewerben: Die ACPC lief von 2006 bis etwa 2018, ein offener Wettbewerb ist aktuell nicht bekannt.
- **lynx-2** (40 % Mensch-Bots): mensch480 +17,7 gegen Lynx, beide Bestätigungen bestanden → **lynx-2@500 neuer Bester**.
  - **Lehre:** **Mensch-Bots als Trainingsgegner brachten den größten Sprung bisher.**

### Nacht 27./28.10.: lynx-3

- Nachtlauf bis 1500 Iterationen: nur das Gate @300 bestanden, danach ein **Plateau** (Gates @600–1500 gegen lynx-3-300 alle nicht bestanden).
- Der Speicher-Wächter beendete den parallelen Slumbot-Lauf. Danach lief Slumbot erst nach dem Training.
- **Stick-Ausfall 04:15** („No Media“). Das Training war um 03:58 schon fertig, verloren ging nichts. Erst um 10:00 umgesteckt.
- Vorab festgelegte Bestätigungen **beide bestanden** → **lynx-3-300 Live-Standard** (10:07).

### Di 28.10.: Suche, Ziele, Leiste, Live-Fixes, ehrliche Slumbot-Zahlen

- **Heads-up-Suche (husearch)** gebaut. Der Nutzer wünschte „Suche zur Laufzeit“ als größten Hebel.
  - hus-1 (ab Turn): Slumbot −12,6 @3.000, Intervall riesig
  - **hus-2: zwischenzeitlich −440 bb/100**, nach 458 Händen abgebrochen (roh −396, All-in-EV −382)
  - **Ursache:** Neulösen ab dem aktuellen Knoten mit heuristischer Range passte nicht zur Lage. Viele All-ins mit schwachen Händen gingen verloren.
  - **Fix:** Lösen **ab Straßenbeginn** mit dem echten Pfad.
- **HU-Preflop-Löser** gebaut und eingebunden → hus-3.
- **Ziele definiert** (`ZIELE.md`, `ai/ziele.py`), Prüfstand-Sets nash/kurz.
- **Lynx-Leiste** gebaut (unsichtbar für die Aufnahme, Ton), vom Nutzer abgenommen.
- **Live-Fixes:** Pot-Semantik (`info.total`), fehlendes `pot.total`, OCR-Ausreißer, Mindest-Raise, greedy-Modus.
- **Befund Mini-Bets:**
  - Lynx setzt postflop oft 1 BB in große Pots.
  - Die Vermutung „Mensch-Bots folden unrealistisch auf Mini-Bets“ stimmt **nicht**: Die Stil-Bots callen Mini-Bets fast immer (Equity ≥ Pot Odds − Toleranz).
  - Das Verhalten ist also eher ein Artefakt bzw. eine Schwäche des Netzes und wird nicht weiter verfolgt.
- **Speicher-Wächter** beendete hus-3 (bei 1.833 Händen) und den PokerTH-Vergleich. Später Neustart als Kette.
- **Stick fiel bei Standby aus** → USB-Energiesparen per powercfg abgeschaltet, Wachhalte-Skript.
- **Fehler bei der Kette:** Ein gestoppter Monitor lief weiter, dadurch lief **alles doppelt**: Slumbot mit 8 statt 4 Sitzungen, insgesamt 8.167 statt 5.000 Hände, und der PokerTH-Vergleich zweimal. Daraus entstand die RAM-Not. Das Duplikat wurde beendet.
- **Slumbot-Baseline geklärt** → bereinigtes Maß als Hauptmaß. Die Suche ist gegen Slumbot **nicht besser**, ihr Plus war Kartenglück (+29).
- **Automatische Turnier-Erkennung und -Eintragung** gebaut. Der Nutzer will, dass Ergebnisse automatisch notiert werden. 171 Tests grün.
- **Abends:** alles gestoppt, `pc.cmd live --leiste` gestartet, der erste echte Live-Test mit Lynx-Beratung gegen PokerTH-Bots läuft.

### Was nicht funktioniert hat (Übersicht)

| Ansatz | Ergebnis | Warum |
|---|---|---|
| Stil-Parameter-Tuning (CEM) | ausgereizt nach opt-1/opt-2 | 10 Regler reichen nicht, sonst wird nur Rauschen gefunden |
| PPO ohne Leine (nn-1) | lernt Bot-Ausbeutung | Gegner-Pool zu eng, keine Verankerung an gutem Spiel |
| Pluribus nur nachahmen | im Turnier schwach | Pluribus kennt kein Kurzstack-Turnierspiel |
| Tabellen-CFR | schwach, ausnutzbar | grobe Abstraktion, zu wenig Rechenzeit |
| Deep CFR | instabil, Einbruch ab It 30 | Strategie-Netz jedes Mal neu trainiert. Bräuchte einen Server. |
| Rollout-Suche Stufe 1 | −18,9 | Annahme, alle spielen wie unser Netz |
| Multi-Format-Training allein (pros-r2/r3) | kein messbarer Gewinn | auf 6er-Sets verdünnt. Später mit Tischgewichten erfolgreich (pros-h1). |
| Gegnermodell-Training (pros-o1) | schlechter als pros-r1 | zu früh, ohne die anderen Zutaten |
| lynx-3 über 300 It hinaus | Plateau | Rezept ausgereizt, neue Zutaten nötig |
| husearch ab aktuellem Knoten (hus-2) | −440 bb/100 | Ranges passten nicht zum Baum |
| husearch gegen Slumbot (hus-3) | bereinigt −23,7, nicht besser als das Netz | Postflop-Abstraktion grob (wenige Größen), unsicheres Neulösen ohne Garantie |

---

## 8. Aktueller Stand, Einschätzung, Schwächen, Roadmap

### 8.1 Beste Version

**lynx-3-300 = `nn?run=lynx-3@300`**: Netz feat-3 / act-2, 57 Merkmale, 8 Aktionen, MLP 128×128. Live-Standard, greedy.

| Stärke (gemessen) | Wert |
|---|---|
| Simulierte Mensch-Tische (PokerTH-Format) | **+96,8 % ROI** |
| gegen den Vorgänger lynx-2 (frische Tische) | +9,2 %, gesichert |
| Ausnutzbarkeit | Ausbeuter +2,3 %, keine groben Lecks |
| Endspiel HU 20 BB | +17,9 % gegen Nash, +83 % gegen Mensch-Bots |
| Slumbot | **bereinigt −17,2 bb/100** |

### 8.2 Einschätzung des Levels (Einschätzung, keine Messung)

- **Gegen Gelegenheitsspieler bzw. das typische PokerTH-Feld:** wahrscheinlich klar gewinnend. Lynx spielt diszipliniert, ist kaum ausnutzbar und kennt keinen Tilt.
- **Gegen starke Bots bzw. Profis:** klar unterlegen. −17 bb/100 gegen Slumbot (Top-HU-Bot von etwa 2018) heißt, dass gegen ein Gleichgewicht noch spürbare Fehler bleiben, vor allem postflop.
- **Grobe Einordnung:** solider Amateur bzw. Micro-Stakes-Regular. Besser als der Durchschnitt auf Spielgeld-Plattformen, nicht auf Profi- oder Solver-Niveau.
- **Vorbehalt:** Die Mensch-Bots sind Nachbildungen. Echte PokerTH-Turniere (Ziel 1) fehlen noch. Erst 10–20 echte Turniere erlauben eine bessere Einordnung, 100–200 eine belastbare.

### 8.3 Bekannte Schwächen

1. **Kein ICM:** Optimiert wird Chip-EV, nicht die Turnierauszahlung.
2. **Postflop-Schwächen gegen starke Gegner** (Slumbot), dazu **Mini-Bets** (1 BB in große Pots).
3. **Kein echtes Anpassen an Gegner im Spiel:** Das Gegnermodell fließt als Merkmal ein, aber keine Suche gegen die Gegner-Range.
4. **Suche nur heads-up** und gegen Slumbot nicht besser. Ob sie in PokerTH-Formaten hilft, ist **offen**, der Vergleich wurde nie fertig.
5. **Erfassung live:**
   - Checks teils beim falschen Sitz
   - Pot- und Startstack-OCR-Ausreißer
   - nur Vordergrund-Aufnahme
   - Tischgrößen außer 4/6 live ungetestet
   - Karo und Kreuz nicht systematisch geprüft
6. **Simulierte Gegner:** Mensch-Bots aus 25NL-Online-Daten von 2009, keine PokerTH-Bots oder -Menschen. Postflop-Werte (WTSD, C-Bet) teils schlecht getroffen.
7. **Infrastruktur:** USB-Stick unzuverlässig, 16 GB RAM begrenzen Parallelität, keine GPU.

### 8.4 Offene Punkte (konkret)

- [x] **Live-Test auswerten** (28./29.10.): erledigt, siehe 8.6
- [ ] **PokerTH-Vergleich Suche gegen Netz** (hu480): läuft in der Nacht 28./29.10. nach dem Training (`night_lynx4.sh`). Erst bei gepaartem Gewinn wird die Suche Live-Standard.
- [ ] Echte Turniere sammeln (Ziel 1: 50, dann 200); ab 10 Turnieren „normal“ auf „hard“ wechseln und getrennt führen
- [ ] Liga-Report aktualisieren (`league run`), der ist veraltet
- [ ] `compare`: abgeleitete Hände (ohne gelesene Handnummer) über Reihenfolge und Karten dem Log zuordnen
- [ ] Code-Review-Befunde der Nacht 28./29.10. einarbeiten (`scratchpad/review-live.md`, `review-ki.md`)

### 8.5 Roadmap (Ideen, nach erwartetem Nutzen)

1. **PokerTH-eigene Gegnermodelle:** Aus echten PokerTH-Sitzungen (Collector) PokerTH-spezifische Mensch- bzw. Bot-Profile ableiten und damit trainieren und prüfen. Das ist am nächsten an Ziel 1.
2. **Mensch-Bots verbessern:** Postflop-Werte (WTSD, C-Bet, Fold auf Einsatz) genauer treffen, damit das Training realistischer wird.
3. **ICM** in Belohnung bzw. Suche für Turnierentscheidungen nahe der Geldränge.
4. **Suche mit Gegnermodell-Ranges** statt reinem Gleichgewicht (ausbeuterisch, gegen schwache Gegner mehr Gewinn). Feinere Postflop-Größen und mehr Iterationen für den Slumbot-Pfad.
5. **Neue Trainingszutaten gegen das Plateau:** größeres Netz, Lernraten-Plan, ICM-Belohnung, mehr Ausbeuter-Gegner, Suche als Lehrer (Expert Iteration).
6. **Collector:** Check-Zuordnung, Startstack-Zeitpunkt, alle Tischgrößen, alle Kartenfarben systematisch, später Windows.Graphics.Capture (überdeckungsfest).
7. **Server** (Hetzner bzw. dedizierte Kerne) für lange Läufe (Deep CFR, größere Netze), damit der Laptop frei bleibt.

### 8.6 Nachtrag: erster Live-Abend 28./29.10.2026 und die Nacht danach

**Sechs echte Turniere** (6er-Tisch, PokerTH-Bots, Schwierigkeit „normal“, Berater lynx-3-300 greedy, Jakob klickt):

| Spiel | Platz | Hände | Bemerkung |
|---|---|---|---|
| 1 | **1** | 35 | Export vorhanden (`sessions/20261028-222209/pokerth-log.txt`) |
| 2 | 3 | 20 | kein Export; Platz aus der Aufnahme nachsimuliert |
| 3 | 6 | 10 | Q7o-Jam war ein Phantom-Vorschlag (Handnummer hing) |
| 4 | 6 | ~7 | KK gegen Ass auf A-Q-4-4, zwei Calls |
| 5 | **1** | 25 | Export vorhanden (`sessions/20261028-234434/pokerth-log.txt`) |
| 6 | **1** | 31 | HU gegen Falcon Fay |

Zieltafel: 3 Siege aus 6, ROI +70 %. Zufall wären 1 von 6 Siegen. Mit 6 Turnieren liegt das 95-%-Intervall noch etwa bei −60 bis +200 %.

**Was die Live-Kette gelernt hat** (alle Fixes am selben Abend, jeweils auf allen Aufnahmen nachsimuliert und mit Tests):

| Problem | Ursache | Fix |
|---|---|---|
| Vorschläge 10–20 s zu spät | Analyse-Warteschlange (3 Bilder) war immer voll, Analyse ~270 ms/Bild; dazu Ruhezeit und Bestätigung | `pipeline.py`: Queue hält nur das neueste Bild, ältere werden verworfen; Status zeigt „Bildalter“. Danach Vorschlag 0,7–1,8 s nach Erkennung. |
| Phantom-Vorschläge („Raise 0“, „Raise 6000“ nach Handende, nach eigenem All-in, nach Fold aller Gegner) | Buttons/Markierung bleiben kurz stehen | `live.py`: `playable()` (Tisch da, eigener Stack > 0), kein Vorschlag ohne eigene Karten oder wenn alle Gegner gefoldet, `sane()` kappt Raise auf den Stack, macht „Raise ≤ Höchstgebot“ zu Call/Check |
| Flackern (Raise 45 → 40 → 41 → 65) | jede OCR-Korrektur ergab einen neuen Vorschlag | SETTLE_S 0,7 s; `same_as_shown()`: gleiche Straße, Art und Betrag ±25 % lösen nichts Neues aus; Karten im Schlüssel |
| „Falsche Karten“ (Eindruck des Nutzers) | **Handnummer-OCR hing 10–20 s**; neue Karten liefen unter der alten Hand mit deren Verlauf und Pot | `reconstruct.py`: neue Hand auch bei Board → 0 trotz alter Nummer und bei Dealerwechsel (MIN_HAND_S 4 s nach Handbeginn), verspätete Nummer wird übernommen (ADOPT_S 30 s). Gegen das Log von Spiel 1: Aktionen 78/80 % → **88/88 %**, Dealer/SB/BB 74 % → **100 %**, Beträge 94 → 97 %, Startstacks 89 → 93 %. Die Sitzung vom 26.10. wurde dabei nicht schlechter (Dealer 92 → 100 %). |
| Stack „51000“ statt „1000“ | „$“ als „5“ gelesen | `fix_dollar_misreads()` für die Live-Observation (OCR selbst noch offen) |
| Ein Plausibilitätsfilter (Stacks + Pot ≤ Turnierchips) | blockierte **echte** Entscheidungen (Einsätze doppelt gezählt, OCR-Ausreißer) | wieder entfernt: lieber ein Phantom als eine fehlende Entscheidung |
| Turnierende nicht erkannt (Spiel 1, 4, 5, 6 je anders) | All-in ohne lesbare Stacks; Endbildschirm vor Pot-Gutschrift; Tisch verschwindet 1 s nach dem Aus; PokerTH zählt lokal jedes Spiel als „Game 1“ | `TournamentWatch`: alle Chips bei einem Stack → Platz 1/2; eigener Stack 20 s auf 0 (auch unlesbar) ohne neue Hand → ausgeschieden, Gegner = Vereinigung aus „sitzt noch“, letzten Stacks und Überlebenden der letzten Hand; Heads-up-All-in mit größerem Stack → Sieg; Sieg nach 20 s ohne neue Hand bestätigt; Neustart am Rücksprung der Handnummer. Nachsimulation aller 6 Spiele: 1, 3, 6, 6, 1, 1 (richtig). |

Offen beim Collector: `compare` ordnet nur über die Handnummer zu (Spiel 5: 14 von 25 Händen zugeordnet, obwohl die Rekonstruktion richtig trennte); Checks beim falschen Sitz; „$“-Lesefehler in der OCR selbst.

**ICM (Nacht 28./29.10.):** `ai/icm.py` (Malmuth-Harville, Preise aus der Auszahlungsstruktur). `RLConfig.icm` mischt die Belohnung: (1 − icm)·Chips + icm·ΔEigenkapital, Ausscheiden zählt die tatsächliche Auszahlung des Platzes. CLI `train rl --icm 1.0`. Tests `test_icm.py` (6, inkl. Rollout). Testsuite 29.10. 02:00: 185 Tests grün.

**Nachtlauf lynx-4** (`night_lynx4.sh`): lynx-3@300 weiter mit `--icm 1.0`, Lernrate 2e-4, Ausbeuter alle 50 It, Tischgewichte 2:3, 3:3, 4:2, 5:2, 6:4, Abschnitte 300/600/900/1200 mit Gate (600 Schemata) gegen lynx-3-300, Prüfstand alle 100 It gegen lynx-3@300. Danach Suche gegen Netz auf hu480 (`bench_hus_nacht.py`). Ergebnisse: `data/rl/lynx-4/night.txt`, `data/rl/lynx-4-run.txt`, `data/bench/hus-vs-netz-pokerth.txt`.

**Ergebnis Abschnitt 300 (29.10., 03:40): Gate bestanden.** `nn?run=lynx-4@300` gegen lynx-3-300 auf 600 frischen Schemata: ROI 44,5 % gegen 34,5 %, Differenz **+10,0 % [+5,4; +14,6]** → in der Liga als **lynx-4-300**. Prüfstand auf denselben Schemata wie lynx-3@300 (gepaarte Differenz, aus `per_scheme` in `data/bench/results.jsonl`):

| Satz | lynx-3@300 | lynx-4@100 | lynx-4@200 | lynx-4@300 | gepaart @300 − lynx-3 |
|---|---|---|---|---|---|
| mensch480 | 96,8 | 115,8 | 108,2 | 115,1 | **+18,3 [+13,1; +23,5]** |
| mix960 | 50,6 | 68,9 | 59,5 | 59,3 | **+8,7 [+4,9; +12,5]** |
| pokerth480 | 35,2 | 55,9 | 45,0 | 47,5 | **+12,3 [+7,5; +17,1]** |
| 10max240 | 73,6 | 100,2 | 84,7 | 87,0 | **+13,5 [+4,6; +22,4]** |
| hu480 | 49,6 | 51,2 | 50,6 | 46,5 | −3,1 [−8,2; +2,0] |
| Pluribus top-1 | 0,798 | 0,804 | 0,805 | 0,814 | – |

Lesart: ICM-Belohnung plus Ausbeuter bringen an vollen Tischen deutlich etwas, heads-up nichts (eher leicht schlechter). **Auffällig: lynx-4@100 ist auf allen Mehrspieler-Sätzen noch stärker als @300** (mix960 +18,3 statt +8,7 gegen lynx-3) – wie schon bei pros-r1 ist der Gate-Sieger nicht automatisch der beste Stand. Frische Prüfung am 29.10. 12:50 (`train gate "nn?run=lynx-4@100" --champion lynx-4-300 --schemes 600 --seed 2910`): @100 gegen @300 **+1,6 [−3,0; +6,1]**, also kein belastbarer Unterschied – der Vorsprung aus dem Prüfstand war Rauschen auf den fest verdrahteten Schemata. lynx-4-300 bleibt. Ausbeuter gegen lynx-4: @50 +22,5, @100 +1,2, @150 +3,3, @200 −15,8, @250 +16,7, @300 +12,1 (alle Intervalle schließen 0 ein).

**Review-Fixes der Nacht (Live-Pfad, alle mit Tests, `tests/test_live_review.py`):** Pipeline fängt Fehler der Ereignisauswertung ab (Zähler `event_errors`) statt den Analysefaden zu verlieren; `LiveBot` mit Sperre (Ereignisse aus dem Analysefaden gegen `poll` der Anzeige), `playable()` vor dem Verbrauch der Ruhezeit (kurz unlesbarer Stack verschluckt keine Entscheidung mehr), Agent erst nach den billigen Prüfungen, `table.found` falsch → nicht dran, `same_as_shown` betragssensitiv (Call 60 → Call 300 ist eine neue Entscheidung); `session_ended()` meldet beim Beenden der Sitzung ein laufendes Ausscheiden und beginnt frisch; `TournamentWatch`: Sieg „alle Chips“ nur bei exaktem Betrag oder ohne Gegnerchips, offener Platz 1 wird verworfen, wenn der Gegner wieder Chips zeigt, Ausscheide-Uhr stoppt bei Gegneraktivität, Rücksprung der Handnummer nur bei Hand ≤ 2 oder gleichen Startstacks, Turnierchips nur bei sicherem Start; Replay: unlesbarer Stack ist kein All-in, Straße „showdown“ aus dem Board; Capture/Journal/Analyzer/Reconstruct/OCR-Kleinigkeiten (Grab-Fehler → `source_ok` falsch, Sperre im Journal, leere Buttons Konfidenz 0,5, All-in-Reset bei Stack > 0, OCR-Rückfall gedrosselt); Suche: `oop` = erster Sitz links vom Button, totes Geld hälftig, Sigma nicht mehr materialisiert (Speicher), Preflop-Cache quantisiert Stacks ab 30 BB auf 1 BB, ab 60 BB auf 2 BB; Slumbot-Seed crc32 (plattformfest); Zieltafel `t95` und `remove_last_tournament` (`bench turnier --ersetzt`). Berichte: `data/review-live.md`, `data/review-ki.md`. Noch nicht eingebaut (wartet auf Trainingsende, weil Worker `rl.py` importieren): Anker-KL faltet die neuen Aktionen auf Raise ½ Pot, Hinweis bei abweichender Aufrufkonfiguration beim Fortsetzen, ICM-Platz bei gleichzeitigem Ausscheiden.

**Ergebnis der ganzen Nacht (09:15): lynx-4-300 bleibt der Sieger.** Gates gegen lynx-4-300: @600 +3,1 [−1,2; +7,4], @900 +3,4 [−1,2; +8,0], @1200 +4,3 [−0,0; +8,6] – alle nicht bestanden, dasselbe Plateau-Muster wie bei lynx-3 (nur der erste Abschnitt schafft das Gate). Gepaart gegen lynx-3@300 liegt @600 bei mensch480 +18,9, mix960 +12,3, pokerth480 +14,9, 10max240 +14,6, hu480 +1,9 [−3,6; +7,3]. **Seit 29.10. 10:00 ist lynx-4-300 der Live-Standard** (`--agent`-Vorgabe in `live`, `live-replay`, `bench ziele`, `bench turnier`). Testsuite nach allen Review-Fixes: 198 grün.

**Erste Turniere mit lynx-4-300 (29.10. vormittags, PokerTH-Bots):** Spiel 7 Platz 2 (29 Hände, Export in `sessions/20261029-092058_2e5fa2b4/pokerth-log.txt`), Spiel 8 Platz 4 (24 Hände). Beide Plätze wurden von `TournamentWatch` automatisch richtig erkannt und eingetragen. Zieltafel gesamt: 8 Turniere, Plätze 1, 3, 6, 6, 1, 1, 2, 4. Vergleich Aufnahme gegen Log in Spiel 7: 25 von 30 Händen zugeordnet, Aktionen Precision 0,79 / Recall 0,85, Beträge 0,99, Dealer/SB/BB 0,84–0,88, Startstacks 0,82 – schwächer als Spiel 1 nach den Fixes (0,88 / 1,0); offen, ob das an der Sitzung (viele Teilhände, Sitz-Zuordnung) oder an den Nacht-Änderungen liegt.

**GTO-Wizard-Benchmark (29.10. nachmittags, von Jakob freigegeben):** zweites externes Maßband neben Slumbot. Gegner ist GTO Wizard AI (ehemals Ruse), HU 200 BB, Bewertung mit AIVAT (etwa dreifach kleinere Streuung als rohe Gewinne). `ai/gtow.py` nach dem Muster von `slumbot.py`: Verlauf `bX`/`_` wird in die Slumbot-Schreibweise übersetzt und mit `slumbot.replay` in der Engine nachgebaut, Gegenprobe des Ergebnisses je Hand, Ergebnisse in `data/bench/gtow/<name>.jsonl`. CLI `pc.cmd bench gtow <spec> --hands N --workers 2 --server`. Zugang beantragt (Schlüssel selbst gewählt, liegt lokal in `data/bench/gtow/api_key.txt`), Freigabe per Mail ausstehend. Rangliste am 29.10.: die besten Bots verlieren mit etwa −3 bb/100, ein Profi mit −3,9, GPT-6 mit −5,4. Erwartung für lynx-4-300: −20 bis −40. Regel des Anbieters: 100 000 Hände je Monat, nur Spielen und Ergebnisse, keine Solver-Funktionen. Nur Maßband, kein Trainingsziel.

**Zielklärung und Meilenstein 3 (29.10. nachmittags/abends):** Jakob: Ziel ist maximal gutes Poker gegen alle Gegner, vor allem Menschen, nicht gegen die Bots einer Plattform. Daraus `PLAN-NAECHSTES-LEVEL.md` 7a (H8 Bot-Nachbau gestrichen, H5 Suche als Lehrer bleibt Kern, H6 auf Menschen ausgerichtet) und `PLAN-MEILENSTEIN-WERTNETZ.md`: Suche mit Wertnetz in DeepStack-Reihenfolge (River-Netz zuerst, dann Blätter im Turn-Baum, dann Turn- und Flop-Netz), Daten auf Hetzner CPX51 stundenweise, Training auf Kaggle (gratis, privat), Code bleibt privat; Runbook `cloud/README-WERTNETZ-CLOUD.md`. Gebaut am 29.10.:

| Baustein | Stand |
|---|---|
| hus-2: Flop im Suchbaum | gezogene Turn-/Rivercards (`k_turn`/`k_river`, Teiler unverzerrt), Presets `narrow`/`wide`, Spec `streets=preflop,flop,turn,river` |
| Kernel ebenenweise parallel | numba `prange` über die Knoten einer BFS-Ebene, Blätter ohne Kopien, `warmup()` beim Start; identische Ergebnisse, 2,5–3,3× schneller unter Last |
| Live-Tempo | Flop 2,1 s, Turn 1,3 s, River 0,4 s unter Volllast (Spec mit `k_turn=4&k_river=4&k_river_turn=16&iters_flop=20&iters=40&iters_river=120&threads=12`) |
| hus-3: Blattknoten | `LEAF`-Knoten ersetzen River-Teilbäume, Werte aus `valuenet.predict` je `leaf_every=10` Iterationen aus den aktuellen Ranges; Orakel-Test (River exakt gelöst als „Netz“) reproduziert den vollen Turn-Baum (`test_husearch_leaf.py`) |
| `ai/valuedata.py` | Situationen zu Straßenbeginn (Pot 2–80 BB, SPR 0,25–8), boardbezogene synthetische Ranges, exakte Lösung, `.npz`-Scherben; CLI `train valuedata`; River 0,5 s je Situation |
| `ai/valuenet.py` | eigenständig (numpy+torch), 2712 → 1024×3 → 2652, Huber + Nullsummen-Strafe, exakte Nullsummen-Korrektur beim Vorhersagen; CLI `train valuenet`; läuft unverändert auf Kaggle |
| GTO-Wizard-Anbindung | `ai/gtow.py`, Zugang beantragt |

Tests dazu: `test_husearch.py` (12), `test_bpranges.py` (5, Blueprint-Ranges 30.10.), `test_husearch_leaf.py` (3), `test_valuedata.py` (3), `test_valuenet.py` (3), `test_gtow.py` (6).

**Nachtpanne:** `bench_hus_nacht.py` stürzte mit `BrokenProcessPool` ab, weil das Skript keinen `if __name__ == "__main__"`-Schutz hatte; unter Windows (spawn) führt jeder Worker das Hauptskript erneut aus und rief damit wieder `run_bench` auf. Behoben, Regel für alle Skripte mit Prozess-Pool.

**Plan für das nächste Level:** `PLAN-NAECHSTES-LEVEL.md` (29.10.), inklusive Sparvariante (0 € für Phase 0–1 mit ThinkPad, bestehendem VPS und Kaggle; Phase 2 stundenweise Cloud ≈ 10–30 € je Schub).

**Abend 29.10. (21–23 Uhr):**
- **Cloud-Zugänge geprüft:** Hetzner-Token (Projekt „lynx“) und Kaggle-Zugangstoken (Konto YOUR_KAGGLE_USER) liegen in `data/cloud/` (nicht im Backup), SSH-Schlüssel `lynx_hetzner` bei Hetzner hinterlegt. `cloud/hetzner.py` (API ohne `hcloud`: types/list/create/push/ssh/pull/delete), `cloud/server-setup.sh`, `cloud/run-vdata.sh`. Preisfund: **cx53** (16 Kerne, 0,056 €/h = 0,35 ct je Kern-Stunde) statt cpx51 (0,85 ct). Kaggle Ende-zu-Ende: privates Dataset `lynx-vdata` + Skript-Kernel `lynx-train-river` (T4, 3000 Situationen × 20 Epochen in 10 s, Hold-out-MAE 0,20). Kein Server gestartet.
- **Slumbot lynx-4-300 fertig** (10.000 Hände): bereinigt +0,2 [−29; +30], siehe 6.7.
- **hus-1 auf hu480 fertig: −29,4 gegen das Netz; Nachtdiagnose Phase A: der Preflop-Löser allein kostet −25,2** (6.8). hus-2 über Nacht gestrichen, stattdessen Phasen B und C (`bench_diag_nacht.py`).
- **Live-Fehler gefunden (zwei Abendturniere, Sitzung 20261029-202109):** Am Endbildschirm des ersten Turniers wurde der Siegerstack „$13408“ als **Einsatz von Platz 5** gelesen. Der Wert blieb im Tischzustand stehen, weil Platz 5 im zweiten Turnier lange keinen Einsatz brachte, der ihn überschrieb. Da der Pot aus „Gesamt“ + Einsätzen gebildet wird, stand im ganzen zweiten Turnier **Pot 13438 statt 30** in jeder Entscheidung; das Netz sah einen Riesenpot bei winzigem Call und riet entsprechend (T9s preflop All-in 97 %). Zwei Korrekturen in `ai/live.py`: `fix_dollar_misreads` streicht Einsätze, die zusammen mit dem Stack über allen Turnierchips liegen; **`drop_stale_bets`** streicht Einsätze im Bild, zu denen die rekonstruierte Hand keine Aktion des Platzes kennt (Blinds ohne Ereignis bleiben). Replay der Sitzung: Pot wieder 30, 19 von 155 Vorschlägen anders. Tests `test_live.py` (+2). Offen: die Chipsumme des Turniers (`TournamentWatch.chips`) war selbst verfälscht (68.000 bzw. 17.408), deshalb wurden die beiden Turnierplätze nicht erkannt und für Turnier 1 fälschlich „Platz 1“ vorgemerkt (nie gemeldet).

**Morgen 30.10. (09–09:30 Uhr), Nachtdiagnose abgeschlossen, Suche umgebaut, Hetzner-Pipeline bestanden:**
- **Nachtdiagnose fertig** (6.8): Phase C unentschieden (−0,6 bb/100 [−62; +61]), Nachprüfung deterministisch. Gesamtdeutung: Preflop-Löser ist das Hauptleck (−25), Postflop-Suche −8,5, im Heimformat kein Nachweis. Konsequenz umgesetzt: **hus-Standard `streets=turn,river` und `ranges=pre`** (Blueprint-Ranges, 4.9, neues Modul `bpranges.py`). Messung D/E läuft (`bench_hus1bp.py`).
- **Hetzner-1000er-Test bestanden (3. Anlauf, ~5 ct):** cpx62 (die cx-Reihe ist überall ausverkauft), Einrichtung 37 s, 1000 River-Situationen in 19 s = 0,28 s je Situation und Kern (Laptop 0,43) → **Tranche 500k ≈ 2,4 h ≈ 0,60 €.** Datei `data/valuenet/hetzner-test/valuenet/river-00000000.npz` lokal geprüft (Format und Statistik wie die lokale Probe, Nullsumme 1,7e-5). Drei Fehler auf dem Weg, alle in `hetzner.py` behoben: ssh ohne Konsole hing (BatchMode), Git-Bash verbog den Serverpfad `/opt/lynx/...` und der erste Lauf ging verloren, weil der Server vor der Prüfung gelöscht war (`remote_path`, `pull` bricht bei leerem Ergebnis ab, Reihenfolge pull → prüfen → delete), wiedervergebene IP mit altem Host-Schlüssel blockierte SSH (`ssh-keygen -R`). API-Änderung: Server tragen `location` statt `datacenter`. **Tranche 1 (Go 09:40) lief 09:44–12:18 auf cpx62: 20 Scherben à 25 000 River-Situationen (je 7,6 min, 116 MB), zusammen 2,2 GB in `data/valuenet/hetzner-1/valuenet/`, lokal geprüft (0 Fehler, Nullsumme 2,2e-5), Server 12:30 gelöscht, Kosten ≈ 0,69 €.** Für das Training auf Kaggle wurde `valuenet.train()` speicherschlank gemacht (Eingaben/Ziele float16, Maske einmal als bool, Ranges aus den Eingaben statt getrennt: rund 6 statt 27 GB bei 500k). `train_river.py` trainiert jetzt 1024×3, Batch 1024, 30 Epochen; `SHARDS=n` begrenzt für die Lernkurve.
- Testsuite: 223 grün, `test_hupreflop` auf explizites `streets=preflop,…` umgestellt (224).
- **Erstes River-Wertnetz (Kaggle T4, 13:07–13:16):** 500 000 Situationen, 1024×3, Batch 1024, 30 Epochen OneCycle in 390 s (13 s je Epoche). **Hold-out-MAE 0,0264 Pot** (10 000 Situationen), Nullsummen-Verletzung 0,0079, Trainingsverlust 0,0067 (Huber). Das Abnahmeziel 0,015 ist nicht erreicht; die Kurve flacht in den letzten Epochen ab (0,0269 → 0,0264), die Lücke zwischen Trainings- und Hold-out-Fehler zeigt, dass mehr Daten und mehr Kapazität helfen sollten. Checkpoint `data/valuenet/kaggle-t1/vnet-river.pt`. Zwei Folgeläufe gestartet: `lynx-train-river-curve` (nur 8 Scherben = 200k, Lernkurvenpunkt) und `lynx-train-river-big` (2048×3, 60 Epochen). Dazu ein lokaler Orakel-Test mit 500 frischen Situationen (Seed 999001000; die alte Probe mit Seed 1000 überlappt mit den Tranche-Seeds und taugt nicht als Hold-out). **Lernkurve und Kapazität (13:35–13:46):** 200k Situationen → Hold-out 0,0380; 500k → 0,0264; 500k mit 2048×3 und 60 Epochen → 0,0189 (26 min T4, Trainingsverlust 0,0024, also deutliches Overfitting-Gefälle). **Entscheidender Befund:** Auf 240 River-Situationen, wie sie an den Blättern echter Turn-Suchen entstehen (neuer `valuedata`-Modus `river-leaf`, lokal exakt gelöst, `data/valuenet/river-leaf-oracle.npz`), liegt der Erwartungswert-Fehler beider Netze bei 0,12 bis 0,13 Pot (95 %-Quantil ~0,5), auf der eigenen Kunstverteilung bei 0,004 bis 0,005. Die Blattverteilung ist eine andere: Stack/Pot-Median 0,44 statt 1,4, dünne und boardgeformte Ranges (bis 8 wirksame Kombinationen). Mehr Kapazität hilft dort nicht (2048×3 sogar schlechter), mehr breite Daten kaum (Fehler ~ n^−0,4). Im Turn-Baum als Blatt eingesetzt ist das Netz 4,4× schneller (2,0 s statt 8,8 s unter Last), die Wurzelstrategie weicht aber um 16 bis 27 % ab, wobei schon 60 gegen 200 exakte Iterationen 10 % Abweichung zeigen (gemischte Strategien sind nicht eindeutig, TV ist ein grobes Maß). Konsequenz: Tranche 2 muss `river-leaf`-Daten liefern (je Seed eine Turn-Suche, bis 24 River-Anfänge nach Erreichmasse gezogen, ~1 s je Zeile und Kern), Training gemischt mit Tranche 1, Abnahme am Blatt-Orakel (EV-Fehler < 0,02 Pot) und an der Spielstärke. Wartet auf Jakobs Go. **Tranche 2 und gemischtes Training (15:02–18:05):** 252 000 Blatt-Situationen (`river-leaf`, 10 Scherben, 1,3 GB, 0 Fehler, wirksame Kombinationen 4 bis 1081, Stack/Pot-Median 0,92) in 2 h auf dem cpx62 (≈ 0,50 €), als zweites privates Kaggle-Dataset `lynx-vdata-leaf`. Training auf allen 752 000 Situationen: 1024×3/30 Epochen → Hold-out 0,0285, Blatt-Prüfsatz EV-Fehler **0,038** (vorher 0,121); 2048×3/60 Epochen (42 min T4) → Hold-out 0,0199, Kunstverteilung EV 0,0035, Blatt-Prüfsatz EV **0,035** (95 %-Quantil 0,19). Die Blattdaten bringen also den Faktor 3,4, mehr Kapazität an den Blättern kaum noch etwas; das Ziel 0,02 steht noch aus (Hebel: mehr oder stärker gewichtete Blattdaten). Checkpoints `data/valuenet/kaggle-t2/` und `kaggle-t2-big/`. **Spieltest V** (`bench_hus1v.py`): Suche wie E, aber mit `vnet=kaggle-t2-big/vnet-river` als Blatt im Turn-Baum, auf hu480 gegen E (+44,0) und Netz (+46,5), gestartet 18:10. Hinweis Kaggle-CLI 2.2.5: beim `datasets version` muss der Ordner `%TEMP%\.kaggle-uploads\<relativer Pfad>` existieren, sonst bricht der Upload bei der ersten Datei still ab.

---


**Morgen 31.10. (06–08 Uhr), Fold-Modell, Menschen-Bot mit Folds, erste Messung dagegen:**
- `ai/humanfold.py` + `data/humans/human-fold-1.npz` (BCE 0,417, Klassen-NLL 4,62 statt 5,13 uniform), Training 37 s auf 18,9 Mio. Zeilen; `oppfold=` in der Suche, `&fold=` am Netz-Bot (6.8).
- Erste Messung der Suche gegen human-1 ohne Folds: nicht auswertbar (Varianz ±200, Gegner nie foldend, Fold-Modell dort fehl am Platz). Gegen human-1 MIT Folds verliert das Netz lynx-4@300 bei 100 BB −21 [−43; +0], bei 40 BB +13 [−5; +32] über je 10 000 Hände. Zweite Messreihe der Suche (A Standard / B opp / C opp+fold) gegen diesen Gegner läuft seit 08:08.
- `ai/teacher.py` (H5, Suche als Lehrer: TeacherRecorder/collect/fit mit KL-Leine, CLI `train teacher-collect/teacher-fit`), Probe 26 Zeilen; Hetzner-Sammlung `cloud/run-teacher.sh` vorbereitet, wartet auf Go (~0,75 €).
- Messung 2 (Suche gegen Menschen-Bot mit Folds, je 720 Hände): kein nachweisbarer Unterschied, Suche nicht besser als Netz, Fold-Faktor ohne messbaren Nutzen (6.8). Lehrer-Sammlung auf Hetzner lehrer-1 seit 09:00 (6.8).
- Stufe 2 (Turn-Netz) vorbereitet: valuedata `turn-leaf`, Suche `leaf=4`; Server-Kette Benchmark + Turn-Tranche nach der Lehrer-Sammlung (6.8).
- Offen: Lehrer-Fit lynx-5t + Gate, GTO-Wizard-Zugang (Gmail), volle Testsuite + Backup nach den neuen Modulen.

### 8.7 Nachtrag 31.10. abends bis 3.11.2026: Abschlussnacht und Veröffentlichung vorbereitet

**Abschlussnacht 31.10./1.11.**
- **Spec-Parser-Fehler** (31.10. 19:29): `make_agent` trennte den Anzeigenamen am **ersten** Doppelpunkt, `hus?bp=run:lynx-5t@1&...:kand` zerfiel, die Messung brach ab. Jetzt zählt der letzte Doppelpunkt, und nur, wenn der Name keines der Zeichen `=&?@/` enthält; Test `test_make_agent_name_hinter_run_doppelpunkt`.
- **Suche gegen den Menschen-Bot mit Folds** (`bench_humanopp3.py`, HU Cash duplicate, je Zelle 4.800 Hände, fertig 1.11. 05:00, `data/bench/humanopp3.txt`):

| Variante | 40 BB | 100 BB |
| --- | --- | --- |
| lynx-5t greedy | **+77,8 [64,6; 90,9]** | **+73,0 [55,9; 90,1]** |
| Suche mit lynx-5t als Blueprint | +55,0 [33,3; 76,8] | +57,1 [24,3; 89,9] |
| Suche greedy, Blueprint greedy | +48,4 | +60,8 |
| Flop-Suche mit Turn-Netz (leaf=4) | +40,7 | +60,7 |
| Suche, Blueprint greedy | +46,2 | +55,7 |
| Suche (Basis C) | +31,5 | +37,4 |
| Netz lynx-4 greedy | +13,0 [−8,6; +34,7] | −14,9 [−40,6; +10,7] |

  Jede Suchvariante schlägt das Netz, keine erreicht lynx-5t; greedy in der Suche bringt etwa +15.
- **Turn-Tranche komplett** (1.11. 02:55): 10 Scherben `turn-leaf`, 220.688 Zeilen, 0 defekt; Server lehrer-1 gelöscht (lief 31.10. 09:00 bis 1.11. 02:54, etwa 4,5 €).
- **vnet-2b** (Kaggle, 1.11. 06:25): Der erste Versuch mit rund 1,37 Mio. Zeilen starb an Speichermangel; mit 977.288 Zeilen (12 River-, 19 River-Leaf-, 9 Turn-Leaf-Scherben) Hold-out 0,0260, Test River-Leaf 0,0336 (vnet-2: 0,0338), Turn-Leaf 0,0510 (vnet-2: 0,0544). Dreimal so viele Turn-Daten bringen nur −6 %: Plateau bei etwa 0,05 Pot.

**Veröffentlichung vorbereitet (2./3.11.)**
- `make_release.py` baut aus dem Projekt einen sauberen Baum für ein öffentliches Repository (`<Laufwerk>\Lynx-Release\lynx-poker`): Whitelist, Ersetzung privater Angaben, Secret-Scan auch in `.pt`/`.npz`. Vorlagen in `release/`: README (englisch und deutsch), MIT-Lizenz, `.gitignore`, `docs/` mit Case Study, technischer Dokumentation, API- und CLI-Referenz (aus dem Code erzeugt), Daten und Lizenzen. Startpaket im Repo: Liga-Datei und zehn Checkpoints (2,5 MB).
- **Leiste mit Maske statt Tarnung:** Die Leiste verbirgt sich nicht mehr per `WDA_EXCLUDEFROMCAPTURE`; sie ist für jede Aufnahme sichtbar, und `WindowSource` schneidet ihre Fläche aus den Bildern des Collectors aus (`capture.apply_masks`, Füllung mit der Umgebungsfarbe, Vermerk `masked` im Sidecar). Praxistest: in einer normalen mss-Aufnahme 93 % der Leistenfläche in Aktionsfarbe, nach der Maske 0 %.
- Weitere Änderungen: Startskripte nutzen ohne `tools\` ein installiertes `uv`; `test_humanfold.py` findet seine Daten relativ statt unter festem Stick-Pfad; die Leiste gibt ihre Tk-Objekte im eigenen Thread frei (vorher Exitcode 3 durch „Tcl_AsyncDelete“ beim Beenden); neue Tests `test_capture_mask.py`.
- Tests: im Projekt 249 bestanden; im exportierten Baum 247 bestanden, 2 übersprungen (brauchen Rohdaten bzw. ein Wertnetz, die nicht im Repo liegen).

## 9. Anhang: Begriffe, Dateien, Spezifikationen

### 9.1 Begriffe

| Begriff | Bedeutung |
|---|---|
| bb/100 | Big Blinds Gewinn je 100 Hände (Cash) |
| ROI | Rendite je Turnier in Buy-ins (Prüfstand: mittlere Netto-Auszahlung) |
| Duplicate / gepaart | dieselben Karten für alle Bots in allen Sitzrotationen; Differenz je Schema |
| Schema | ein festes Kartenblatt (Seed) plus ein Tisch |
| Gate / Aufnahmeprüfung | Kandidat gegen Titelverteidiger auf frischen Schemata; bestanden bei CI > 0 |
| Leine / Anker (piKL) | KL-Strafe gegen einen Referenz-Bot, hält das Lernen bei „vernünftigem“ Spiel |
| PSRO / Ausbeuter im Training | regelmäßig gegen den aktuellen Stand trainierter Ausbeuter wird neuer Gegner |
| CFR / CFR+ | Counterfactual Regret Minimization, nähert sich einem Gleichgewicht |
| Blueprint | Grundstrategie (bei uns: das Netz), die von der Suche verfeinert wird |
| Ausnutzbarkeit | wie viel eine perfekte Gegenstrategie gewinnt (0 = Gleichgewicht) |
| All-in-EV | bei All-in vor dem River Equity statt Kartenausgang |
| Kontrollvariable (bereinigt) | Ergebnis minus β·(Kartenglück) mit E[Kartenglück] = 0, weniger Varianz |
| VPIP / PFR / 3-Bet / Agg / FtB / C-Bet / WTSD | HUD-Kennzahlen: freiwillig investiert / preflop erhöht / Re-Raise / Aggression / Fold auf Einsatz / Continuation Bet / zum Showdown |

### 9.2 Bot-Spezifikationen

| Spec | Bedeutung |
|---|---|
| `rock`, `tag`, `tag?push_bb=15&bluff=0.15` | Stil-Bot mit Parametern |
| `nn?run=lynx-3@300` | Netz aus `data/rl/lynx-3/ckpt_000300.pt` |
| `lynx-3-300`, `lynx-2`, `pros-h1`, `lynx` | Liga-Namen (aufgelöst über `data/league/players.json`) |
| `hus?bp=lynx-3-300&iters=120&iters_river=300&streets=preflop,turn,river` | Heads-up-Suche mit Netz als Blueprint |
| `search?bp=pros-2@300,worlds=16` | alte Rollout-Suche (verworfen) |
| `cfr?run=cfr-1` | Tabellen-CFR-Strategie |
| `mensch-1` … `mensch-6` | Mensch-Bots (Specs in `data/humans/mensch-25nl.json`) |

### 9.3 Trainingsläufe (`data/rl/`)

| Lauf | Start | Besonderheit | Ergebnis |
|---|---|---|---|
| nn-1 | BC rock | PPO ohne Leine | Ausbeutung, verworfen |
| plu-1 / pros-1 | BC Pluribus | Leine | Basis |
| pros-2 | pros-1@0 | 512 Turniere/It | Gate vs rock +19,8 % (Liga pros-ppo2) |
| pros-3 | pros-2@300 | Zufalls-Gegner + Ausbeuter | mix96 bis +24 |
| pros-r1 | – | feat-2 (Ranges) | @300 lange Bester |
| pros-r2 / pros-r3 | pros-r1@300 / pros-r2@350 | Multi-Format | pros-r3-200 Gate bestanden |
| pros-o1 | – | feat-3 Gegnermodell | abgebrochen |
| pros-h1 | – | feat-3 + act-2, Self-Play-Plätze, HU-Gewichte | @600 = Lynx |
| lynx-2 | Lynx | 40 % Mensch-Bots | @500 Bester (27.10.) |
| lynx-3 | lynx-2@500 | gleiches Rezept, Nachtlauf | **@300 Bester (seit 28.10.)** |
| cfr-1, dcfr-1 | – | CFR, Deep CFR | verworfen |

### 9.4 Wichtige Datendateien

| Datei | Inhalt |
|---|---|
| `data/bench/results.jsonl` | alle Prüfstand-Ergebnisse (140 Einträge) |
| `data/bench/report.md` | Tabelle aller Prüfstand-Ergebnisse |
| `data/bench/slumbot/<name>.jsonl` | jede Slumbot-Hand (Karten, Verlauf, winnings, baseline, allin_ev) |
| `data/rl/NACHTPROTOKOLL.md` | Protokoll beider Nachtläufe |
| `data/rl/<lauf>/best.json`, `gate_<It>.json`, `eval.jsonl`, `log.jsonl` | Trainingsverlauf |
| `data/rl/lynx-3-bestaetigung-mensch.json`, `lynx-2-bestaetigung*.{json,txt}` | Bestätigungsprüfungen |
| `data/humans/mensch-25nl.json` | Mensch-Bots mit Ziel- und Ist-Statistiken |
| `data/ziele/pokerth.jsonl` | echte Turniere (Ziel 1) |
| `data/sessions/*/compare.md` | Vergleich Collector gegen PokerTH-Log |

### 9.5 Lücken dieser Dokumentation

- Für den 4er-Tisch (`230753`, `231440`) liegt kein compare.md vor, dort gibt es keine formalen Genauigkeitszahlen.
- Die genauen Werte der frühen Liga-Ratings sind veraltet (Report vom 26.10.).
- Die Live-Sitzung vom 28.10. abends (`20261028-222209` und folgende) ist zum Zeitpunkt der Erstellung noch nicht ausgewertet.
- Die Angaben zur Einsatzgröße der Mini-Bets und zur Leck-Analyse stammen aus Ad-hoc-Auswertungen (Scratchpad-Skripte), nicht aus versionierten Projektdateien.
