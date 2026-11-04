"""hus-2 (Suche auch am Flop, gezogene Karten 6/6, Preset narrow) gegen Netz lynx-4-300 und gegen hus-1 auf hu480,
gepaart. 4 Worker x 3 numba-Faeden = 12 Threads. Nachtlauf 29./30.10.
Der __main__-Schutz ist Pflicht (Windows spawn startet dieses Skript in jedem Worker neu)."""
from pokercollector.ai.bench import run_bench, compare

SPEC = "hus?bp=lynx-4-300&iters=60&iters_river=150&iters_flop=30&streets=preflop,flop,turn,river&threads=3"
NAME = "hus2-lynx-4-300"


def main():
    run_bench(SPEC, NAME, sets=("hu480",), workers=4,
              progress=lambda s, r: print(s, r.get("roi"), r.get("ci95"), flush=True))
    for other in ("lynx-4@300", "hus-lynx-4-300"):
        try:
            for s, ra, rb, d in compare(NAME, other):
                print(f"{s}: {NAME} {ra['roi']:+.1f} vs {other} {rb['roi']:+.1f}  Differenz {d['roi']:+.1f} "
                      f"[{d['ci95'][0]:+.1f}; {d['ci95'][1]:+.1f}]", flush=True)
        except Exception as e:      # Vergleichspartner fehlt o. ae.: Messung selbst bleibt gueltig
            print(f"Vergleich mit {other} nicht moeglich: {e}", flush=True)


if __name__ == "__main__":
    main()
