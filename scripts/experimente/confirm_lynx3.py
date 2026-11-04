import json
import sys
from pokercollector.ai.confirm import confirm_vs_humans

# Predefined (28.10 00:40): Candidate = last lynx-3 state that passed its entrance exam,
# against lynx-2@500 on 600 fresh human tables, seed "lynx3-28-10". Once, do not repeat.

def main():
    cand = sys.argv[1]
    r = confirm_vs_humans(f"nn?run={cand}", "nn?run=lynx-2@500", schemes=600, seed="lynx3-28-10")
    r["candidate"] = cand
    open("<Projektordner>/data/rl/lynx-3-bestaetigung-mensch.json", "w").write(json.dumps(r, indent=1))
    print('Human tables:', cand, r["a"]["roi"], 'vs lynx-2@500', r["b"]["roi"], 'Difference', r["diff"]["roi"],
          r["diff"]["ci95"], "bestanden" if r["passed"] else 'failed')

if __name__ == "__main__":
    main()
