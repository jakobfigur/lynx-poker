# Lynx

**Eine Poker-KI vom Bildschirmpixel an: ein Collector, der PokerTH-Partien ausschließlich aus dem Bildschirmbild liest, und ein selbst trainierter No-Limit-Hold'em-Bot, der live berät.**

Entstanden in acht Tagen (25.10.–1.11.2026) auf einem Laptop ohne Grafikkarte, mit rund 6 € gemieteter Cloud-Rechenzeit. Entwickelt von Jakob Figur mit Claude Code. [English version](README.md).

> **Nicht für Echtgeld.** Bots und Echtzeit-Beratung sind auf Echtgeld-Plattformen verboten und können strafbar sein. Lynx wurde nur gegen PokerTH (Open Source, Spielgeld) und öffentliche Forschungs-Maßbänder entwickelt und getestet. Die Live-Beratung zeigt Vorschläge nur in einem normalen, sichtbaren Fenster an; sie klickt nie, steuert den Browser nicht und versteckt sich nicht vor Bildschirmaufnahmen oder Bildschirmfreigaben.

## Ergebnisse

| Was | Ergebnis |
| --- | --- |
| Collector gegen das PokerTH-Log | Aktionen 88 % Precision / 89 % Recall, Boardkarten 55 von 55, Beträge 98,7 % (erste echte Aufnahme nach einem Abend Korrekturen) |
| Bot-Generationen | fünf Netz-Generationen, jede erst nach bestandenem Gate auf frischen Kartenschemata übernommen (ein Gate wird nie bis zum Bestehen wiederholt); ROI auf dem Menschen-Testset `mensch480` von +43,8 % (Regel-Bot) auf +128,2 % (lynx-4, greedy) |
| Heads-up gegen [Slumbot](https://www.slumbot.com/) (200 BB) | lynx-4: +0,2 bb/100 [−29; +30] über 10.000 Hände (frühere Generationen −14 bis −35) |
| Heads-up gegen einen Menschen-Nachbau | lynx-5t (aus der Suche destilliert): +77,8 / +73,0 bb/100 bei 40 / 100 BB über 4.800 Hände; das Ausgangsnetz lynx-4: +13,0 / −14,9 |
| River-Wertnetz | Blattwert-Fehler 0,121 → 0,0081 Pot durch eine andere Trainingsverteilung, nicht durch mehr Daten |
| Echte PokerTH-Turniere | 10 Sit&Gos gegen PokerTH-Bots mit Live-Beratung: 3 Siege, ROI +32 % (zu wenige für eine belastbare Aussage) |

Intervalle sind 95-%-Intervalle. Die ganze Geschichte mit jeder Zahl, Datum und Quelle steht in der [Case Study](docs/CASE-STUDY.md), der Aufbau des Codes in der [technischen Dokumentation](docs/TECHNISCHE-DOKUMENTATION.md).

## Schnellstart

Voraussetzung: [uv](https://docs.astral.sh/uv/) (installiert Python 3.12 und alle Pakete). Die KI läuft unter Windows, Linux und macOS; Collector und Live-Beratung brauchen Windows 10/11 mit installierter OCR-Sprache.

```bash
uv sync --project collector                                  # Umgebung anlegen (einmalig)
uv run --project collector pytest -q collector/tests         # Tests

# Lynx (lynx-4, greedy) gegen den Regel-Bot "tag", Duplicate heads-up, 100 Blätter
uv run --project collector pokercollector sim match --agents "nn?run=lynx-4@300&greedy=1:lynx,tag" --hands 100

# Liga mit allen Bots und ihren Spezifikationen
uv run --project collector pokercollector league show

# Bot auf einem festen Testset messen (gepaart vergleichen mit "bench compare")
uv run --project collector pokercollector bench run lynx-4-300 --sets hu48

# selbst ein Turnier gegen Lynx im Terminal spielen
uv run --project collector pokercollector play --mode tournament --opponents lynx-4-300,tag,rock
```

Unter Windows tun `sync.cmd`, `tests.cmd` und `pc.cmd <befehl>` dasselbe, unter Linux/macOS `./pc.sh <befehl>`. Collector (nur Windows): `pc.cmd calibrate collector\testdata\pokerth_preflop_hand1.png` analysiert das Testbild und schreibt ein Overlay-Bild. Alle Befehle: [CLI-Referenz](docs/CLI-REFERENZ.md).

## Dokumentation

| Dokument | Inhalt |
| --- | --- |
| [CASE-STUDY.md](docs/CASE-STUDY.md) | was gebaut wurde, wie und warum, Etappe für Etappe, mit allen Ergebnissen und Lehren |
| [TECHNISCHE-DOKUMENTATION.md](docs/TECHNISCHE-DOKUMENTATION.md) | Architektur, jedes Modul, Datenformate, Betrieb, Reproduktion |
| [API-REFERENZ.md](docs/API-REFERENZ.md) · [CLI-REFERENZ.md](docs/CLI-REFERENZ.md) | aus dem Code erzeugt |
| [DATEN-UND-LIZENZEN.md](docs/DATEN-UND-LIZENZEN.md) | welche Daten und Modelle enthalten sind, welche nicht, Drittquellen |
| [projektnotizen/](docs/projektnotizen/) | Originalnotizen, Pläne und Nachtprotokolle |

## Grenzen

- Die meisten Messungen laufen gegen Bots und gegen einen Nachbau von Online-Spielern aus 2009; Ergebnisse gegen echte Menschen gibt es noch nicht.
- Das zweite externe Maßband (GTO Wizard) ist beantragt, aber noch nicht freigeschaltet.
- Der Collector ist auf den PokerTH-Web-Client kalibriert; andere Clients brauchen ein eigenes Layout-Profil und eigene Kartenvorlagen.

## Lizenz

MIT, siehe [LICENSE](LICENSE). Daten Dritter behalten ihre eigenen Bedingungen ([DATEN-UND-LIZENZEN.md](docs/DATEN-UND-LIZENZEN.md)).
