import json
import sys
from pokercollector.ai.confirm import confirm_vs_humans

# Vorab festgelegt (28.10. 00:40): Kandidat = letzter lynx-3-Stand, der seine Aufnahmepruefung bestanden hat,
# gegen lynx-2@500 auf 600 frischen Mensch-Tischen, Seed "lynx3-28-10". Einmal, nicht wiederholen.

def main():
    cand = sys.argv[1]
    r = confirm_vs_humans(f"nn?run={cand}", "nn?run=lynx-2@500", schemes=600, seed="lynx3-28-10")
    r["candidate"] = cand
    open("<Projektordner>/data/rl/lynx-3-bestaetigung-mensch.json", "w").write(json.dumps(r, indent=1))
    print("Mensch-Tische:", cand, r["a"]["roi"], "vs lynx-2@500", r["b"]["roi"], "Differenz", r["diff"]["roi"],
          r["diff"]["ci95"], "bestanden" if r["passed"] else "nicht bestanden")

if __name__ == "__main__":
    main()
