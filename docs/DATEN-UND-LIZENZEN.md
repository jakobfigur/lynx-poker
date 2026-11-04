# Daten, Modelle und Lizenzen

Stand 3.11.2026 · Jakob Figur

Das Repository enthält den gesamten Code, ein Testbild und ein kleines Startpaket trainierter Modelle (rund 2,5 MB). Rohdaten, Aufnahmen, Trainingsdaten der Wertnetze und Zugangsdaten sind bewusst nicht enthalten; dieses Dokument sagt, was fehlt, warum, und wie man es selbst erzeugt oder bezieht.

## Startpaket im Repository

| Datei unter `data/` | Inhalt | Wofür |
| --- | --- | --- |
| `league/players.json` | Liga: 18 Spieler mit Spezifikation und Rating (Netz-Bots ohne Ligaspiele) | Liga-Namen wie `lynx-4-300` in allen Befehlen |
| `rl/pros-1/ckpt_000000.pt` | Verhaltensklon aus 10.000 Pluribus-Händen (Liga `pros-bc`) | Gegner in den `mix`- und Format-Testsets, Start des Ausbeuter-Tests |
| `rl/pros-2/ckpt_000300.pt`, `rl/pros-r1/ckpt_000300.pt`, `rl/pros-r3/ckpt_000200.pt` | frühe PPO-Generationen (26.–27.10.) | Liga-Gegner, Vergleich der Generationen |
| `rl/pros-h1/ckpt_000600.pt` | erste Version mit Namen „Lynx“ (27.10.) | Liga `lynx`, `pros-h1` |
| `rl/lynx-2/ckpt_000500.pt`, `rl/lynx-3/ckpt_000300.pt` | Generationen mit Mensch-Bots im Training (27./28.10.) | Liga `lynx-2`, `lynx-3-300` |
| `rl/lynx-4/ckpt_000300.pt`, `rl/lynx-4/best.json` | bester Allround-Bot, Standard der Live-Beratung (29.10.) | Liga `lynx-4-300`, Blueprint der Suche |
| `rl/lynx-5t/ckpt_000001.pt`, `rl/lynx-5t/teacher.json` | Schüler der Suche, stärkster Spieler gegen den Menschen-Nachbau (31.10.) | `nn?run=lynx-5t@1&greedy=1` |
| `rl/human-1/ckpt_000001.pt`, `rl/human-1/train_human.json` | Politiknetz, gelernt aus 7,35 Mio. Showdown-Entscheidungen von HandHQ-Spielern | Menschen-Bot, Gegnermodell der Suche |
| `humans/mensch-25nl.json` | sechs Stil-Bots, angepasst an die Spielertypen der HandHQ-Daten | Testset `mensch480`, Training mit Mensch-Gegnern |
| `humans/human-fold-1.npz` | Fold-Modell aus 55,5 Mio. kartenfreien Entscheidungen | Menschen-Bot mit Folds `nn?run=human-1@1&fold=human-fold-1` |

Die Modelle enthalten nur Netzgewichte bzw. Stilparameter, keine Spielernamen oder Handhistorien. Das Release-Skript prüft auch den Inhalt der `.pt`- und `.npz`-Dateien auf Pfade, Namen und Zugangsdaten.

## Nicht im Repository

| Was | Warum nicht | Selbst erzeugen oder beziehen |
| --- | --- | --- |
| Aufnahmen (`data/sessions/`, 3,2 GB) | Bildschirmvideos eigener Partien, groß | `pc.cmd live` bzw. `pc.cmd analyze <video>` |
| Kartenvorlagen (`data/templates/`) | Ausschnitte aus der PokerTH-Grafik | `pc.cmd harvest-cards <screenshots>` (interaktiv, Teil 1 Abschnitt 4 der Technik-Doku) |
| Wertnetz-Trainingsdaten (`data/valuenet/`, 8 GB) | Größe | `pc.cmd train valuedata ...` lokal oder `cloud/run-vdata.sh` auf einem Server |
| Wertnetze `vnet-river-1.pt`, `vnet-2b.pt` (je 77 MB) | Größe | Kaggle-Kernel unter `cloud/kaggle/`; können als Release-Asset nachgereicht werden |
| PHH-Rohdaten (`data/external/`, 9,3 GB) | Drittquelle | [uoftcprg/phh-dataset](https://github.com/uoftcprg/phh-dataset), Befehle in Teil 2 Abschnitt 9 der Technik-Doku |
| Auswertungen der Menschen-Daten (`data/humans/actions/`, 543 MB) | Größe, abgeleitet aus Drittdaten | `pc.cmd data humandata`, `pc.cmd data humanpublic` |
| Lehrer-Daten (`data/teacher/`) | Zwischenprodukt | `cloud/run-teacher.sh` bzw. `pc.cmd train teacher-collect` |
| Trainingsläufe und Zwischenstände (`data/rl/*` außer Startpaket, 620 MB) | Größe | Rezepte in Teil 2 Abschnitt 10, Originalskripte in `scripts/experimente/` |
| Messprotokolle (`data/bench/`, Slumbot- und GTO-Wizard-Hände) | Protokolle externer Dienste | `pc.cmd bench run`, `bench slumbot`, `bench gtow` |
| Zugangsdaten (`data/cloud/`, `data/bench/gtow/api_key.txt`) | geheim | eigene Zugänge anlegen (Teil 2 Abschnitt 9); `.gitignore` sperrt diese Pfade doppelt |

## Drittquellen und Lizenzen

| Quelle | Nutzung in Lynx | Lizenz bzw. Bedingungen |
| --- | --- | --- |
| [PHH-Dataset](https://github.com/uoftcprg/phh-dataset) (Universal, Open, Free, and Transparent Computer Poker Research Group) | Pluribus-Hände für Verhaltensklon und Engine-Test; HandHQ-Hände für Menschen-Statistik, Mensch-Bots und Menschen-Modell | Repository unter MIT-Lizenz; Rohdaten werden nicht weitergegeben |
| Pluribus-Hände (Brown & Sandholm, *Science* 2019, Supplement) | 10.000 Hände, über das PHH-Dataset | wissenschaftliche Veröffentlichung |
| HandHQ-Handhistorien (Juli 2009, 25NL, anonymisiert) | Statistiken, Spielertypen, Trainingsdaten von `human-1` und `human-fold-1` | über das PHH-Dataset; eigene Nutzungsbedingungen der Originalquelle wurden nicht geprüft |
| [PokerTH](https://www.pokerth.net/) | Spielumgebung (Spielgeld), deren Oberfläche der Collector liest und deren Log er als Referenz nutzt | freie Software; Lynx enthält keinen PokerTH-Code, nur ein Testbild der Oberfläche (`collector/testdata/`) |
| [Slumbot](https://www.slumbot.com/) | externes Maßband über die öffentliche API (`ai/slumbot.py`) | Nutzung der API; keine Daten von Slumbot im Repository |
| GTO Wizard Researcher-API | zweites Maßband, Client in `ai/gtow.py` (Zugang noch nicht erteilt) | Bedingungen des Anbieters; eigener Schlüssel nötig |
| Python-Pakete (numpy, opencv-python, mss, torch, numba, pillow, winrt, pytest) | Laufzeit und Tests | BSD, MIT, Apache 2.0 bzw. HPND; verträglich mit der MIT-Lizenz von Lynx |

Lynx selbst steht unter der MIT-Lizenz (`LICENSE`). Die Lizenz gilt für Code, Dokumentation und das Startpaket; Daten Dritter behalten ihre eigenen Bedingungen.

## Hinweis zur Nutzung

Lynx wurde ausschließlich gegen PokerTH (Spielgeld) und öffentliche Forschungs-Maßbänder entwickelt und getestet. Bots und Echtzeit-Beratung sind auf Echtgeld-Plattformen verboten und können strafbar sein; dafür ist Lynx nicht gedacht. Die Live-Beratung zeigt nur Vorschläge an und klickt nie selbst.
