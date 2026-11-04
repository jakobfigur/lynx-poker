# Ziele für Lynx

Stand: 28.10.2026. Anzeigetafel: `pc.cmd bench ziele <bot>`.
Neu messen: `--messen` (Benchmarks 2 und 5, ca. 15–30 min), `--exploit` (Benchmark 4).

Lynx soll in PokerTH gegen Menschen gewinnen. Die Ziele sind danach sortiert, wie nah sie daran sind.

| # | Benchmark | Was er misst | Stufen |
|---|---|---|---|
| 1 | **Echte PokerTH-Partien** (Jakob spielt, Lynx berät) | Platz und ROI in echten Sit&Gos (Auszahlung 50/30/20 %) | 50 Turniere mit ROI > 0 → 200 Turniere mit ROI > +20 % und Siegquote > 1/6 |
| 2 | **Mensch-Tische** `mensch480` | PokerTH-Format gegen Bots, die echtes 25NL-Verhalten nachbilden (HandHQ) | ROI ≥ +100 % → ROI ≥ +120 % |
| 3 | **Slumbot** (heads-up, 200 BB) | Stärke gegen einen fast fehlerfreien Gegner | > −15 bb/100 → > 0 → untere 95-%-Grenze > 0 (je ≥ 20.000 Hände, All-in-EV) |
| 4 | **Ausnutzbarkeit** | Ein Ausbeuter lernt gegen 5 Kopien des Bots, gemessen wird sein ROI | Ausbeuter ≤ +5 % |
| 5 | **Endspiel heads-up mit 20 BB** | Turnierschluss: `nash240` gegen Push/Fold-Nash, `kurz240` gegen Mensch-Bots | nash240 ≥ 0 % → kurz240 > +20 % |

**Schutz gegen Rückschritte:** Eine neue Version muss das Liga-Gate bestehen und eine vorab festgelegte Bestätigung auf neuen Mensch-Tischen. Beides läuft je einmal und wird nie wiederholt.

## Benchmark 1: echte Turniere eintragen

Nach jedem Turnier eintragen:

```
pc.cmd bench turnier <Platz> --spieler 6 --notiz "gegen PokerTH-Bots"
```

Dabei gilt:
- Gespielt wird von Hand, Lynx gibt nur Vorschläge.
- Es gibt keine automatischen Klicks und kein Lesen von DOM, Netzwerk oder Speicher.
- Das PokerTH-Log ist nur Referenz und wird nie für das Training verwendet.

Bei Sit&Gos schwankt das Ergebnis stark. Vor 100–200 Turnieren sagt die Zahl wenig.

## Bewusst kein Ziel

- **Übereinstimmung mit menschlichen Aktionen:** Ähnlichkeit ist keine Stärke.
- **Training auf Slumbot:** Slumbot ist nur Maßband. Lynx soll allgemein stark werden, auch die Suche rechnet ein Gleichgewicht und keine Slumbot-Anpassung.
