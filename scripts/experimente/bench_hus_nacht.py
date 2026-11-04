"""Suche (hus) gegen Netz allein auf dem PokerTH-Pruefstand hu480, gepaart. Entscheidet ueber den Live-Standard.
Basis seit 29.10.: lynx-4-300 (Vergleich gegen den Prueflauf 'lynx-4@300' aus dem Nachttraining).
Der __main__-Schutz ist Pflicht: unter Windows startet jeder Worker-Prozess dieses Skript neu (spawn); ohne den
Schutz rief jeder Worker wieder run_bench auf -> BrokenProcessPool (Nacht 29.10.)."""
from pokercollector.ai.bench import run_bench, compare


def main():
    run_bench("hus?bp=lynx-4-300&iters=60&iters_river=150", "hus-lynx-4-300", sets=("hu480",), workers=4,
              progress=lambda s, r: print(s, r.get("roi"), r.get("ci95"), flush=True))
    for s, ra, rb, d in compare("hus-lynx-4-300", "lynx-4@300"):
        print(f"{s}: {ra['roi']:+.1f} vs {rb['roi']:+.1f}  Differenz {d['roi']:+.1f} [{d['ci95'][0]:+.1f}; {d['ci95'][1]:+.1f}]")


if __name__ == "__main__":
    main()
