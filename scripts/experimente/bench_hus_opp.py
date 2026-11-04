"""30.10. abends: Suche mit Wertnetz-Blaettern (hus1v) auf hu480. Vorlage bench_hus1bp.py.
"""
"""30.10.: Suche mit Blueprint-Ranges (bpranges.py) auf hu480, gepaart gegen Netz und gegen die Heuristik-Suche.
  D  hus1bp:  streets=turn,river, ranges=pre       (Preflop-Aktionen mit dem Netz bewertet)
  E  hus1bpf: streets=turn,river, ranges=pre,flop  (auch Flop-Aktionen)
Referenzen: lynx-4@300 (+46,5), hus1np-lynx-4-300 (Heuristik-Ranges, +37,9), hus-lynx-4-300 (hus-1, +17,1).
Losgeloest starten (Start-Process), 4 Worker x 3 Faeden. __main__-Schutz Pflicht (Windows spawn)."""
import time

from pokercollector.ai.bench import compare, run_bench

BP = "lynx-4-300"
REF = ("lynx-4@300", "hus1v-lynx-4-300", "hus1bpf-lynx-4-300")


def cmp(name, others):
    for other in others:
        try:
            for s, ra, rb, d in compare(name, other):
                print(f"  {s}: {name} {ra['roi']:+.1f} vs {other} {rb['roi']:+.1f}  Differenz {d['roi']:+.1f} "
                      f"[{d['ci95'][0]:+.1f}; {d['ci95'][1]:+.1f}]", flush=True)
        except Exception as e:
            print(f"  Vergleich mit {other} nicht moeglich: {e}", flush=True)


def phase_bench(tag, spec, name):
    print(f"=== {tag}: {spec} ===", time.strftime("%H:%M"), flush=True)
    # resume=True: fertige Bloecke liegen in data/bench/partial-<name>-hu480.json; ein Neustart dieses Skripts
    # rechnet nur weiter (30.10. vormittags starb der Elternprozess nach 85 min ohne Spur, alles verloren)
    run_bench(spec, name, sets=("hu480", "mensch480"), workers=2, resume=True,
              on_chunk=lambda k, n, z: print(f"  Block {k}/{n}: laufend {z['roi']:+.1f} [{z['ci95'][0]:+.1f}; {z['ci95'][1]:+.1f}]",
                                             time.strftime("%H:%M"), flush=True),
              progress=lambda s, r: print(" ", s, r.get("roi"), r.get("ci95"), flush=True))
    cmp(name, REF)
    print(f"=== {tag} fertig ===", time.strftime("%H:%M"), flush=True)


if __name__ == "__main__":
    # H: Suche (auto-Format, Netz-Blaetter) mit MENSCHENMODELL human-1 als Gegner-Range (H11 Schritt 5) auf hu480 + mensch480
    # V: Suche wie E (streets=turn,river, ranges=pre,flop), aber River-Teilbaeume im Turn-Baum durch das Wertnetz
    # kaggle-t2-big (2048x3, 752k gemischt) ersetzt -> schneller; Frage: spielt sie genauso stark wie E (+44,0)?
    phase_bench("H", f"hus?bp={BP}&auto=1&opp=human-1@1&iters=60&iters_river=150&threads=3&vnet=kaggle-t2-big/vnet-river", f"hus1h-{BP}")
    print("ALLE MESSUNGEN FERTIG", time.strftime("%H:%M"), flush=True)
