#!/usr/bin/env bash
# Night task 31.10./1.11.: fetch missing turn fragments from teacher-1, check them, upload as Kaggle dataset version.
# Call from project directory (Git-Bash):  MSYS_NO_PATHCONV=1 bash cloud/night-pull-turn.sh [IP]
# Outputs "NIGHT OK" at the end if all 10 fragments are local and checked; otherwise "NIGHT INCOMPLETE".
# This script does NOT delete the server (the operator does this after manual inspection: python cloud/hetzner.py delete teacher-1).
set -uo pipefail
cd "$(dirname "$0")/.."
IP="${1:-SERVER_IP}"
KEY=data/cloud/lynx_hetzner
DST=data/valuenet/hetzner-turn
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o BatchMode=yes root@$IP"
echo "$(date '+%F %T') Server status:"
$SSH 'ls -la /opt/lynx/data/valuenet/ | grep turn-leaf; tail -2 /opt/lynx/data/vdata-turn.log; tail -1 /opt/lynx/data/after.log' || { echo "OVERNIGHT RUN INCOMPLETE (ssh)"; exit 1; }
for i in 0 1 2 3 4 5 6 7 8 9; do
  f=$(printf "turn-leaf-%08d.npz" $((i * 2000)))
  if [[ -s "$DST/$f" ]]; then continue; fi
  if $SSH "test -s /opt/lynx/data/valuenet/$f"; then
    echo "$(date '+%T') fetching $f ..."
    scp -q -i $KEY -o StrictHostKeyChecking=no "root@$IP:/opt/lynx/data/valuenet/$f" "$DST/$f.part" && mv "$DST/$f.part" "$DST/$f" || echo "ERROR fetching $f"
  else
    echo "$f not yet ready on the server"
  fi
done
echo "$(date '+%T') Validation:"
cd collector
PYTHONIOENCODING=utf-8 ../tools/uv/uv.exe run --quiet --no-sync python - <<'EOF'
import json, glob, sys, numpy as np
tot, bad = 0, 0
files = sorted(glob.glob("../data/valuenet/hetzner-turn/turn-leaf-*.npz"))
for f in files:
    try:
        z = np.load(f, allow_pickle=False); m = json.loads(str(z["meta"]))
        n = z["board"].shape[0]; nb = (z["board"] >= 0).sum(1)
        ok = m["errors"] == 0 and set(nb.tolist()) == {4} and np.isfinite(z["v0"]).all() and np.isfinite(z["v1"]).all() and n > 10000
    except Exception as e:
        ok, n = False, 0; print("  ", f, "FEHLER", e)
    print("  ", f.split("/")[-1], n, "Zeilen", "ok" if ok else "PROBLEM"); tot += n; bad += (not ok)
print(f"gesamt {len(files)} Scherben, {tot} Zeilen, {bad} defekt")
sys.exit(1 if bad or len(files) < 10 else 0)
EOF
rc=$?
cd ..
if [[ $rc -ne 0 ]]; then echo "OVERNIGHT RUN INCOMPLETE (shards missing or invalid, no upload)"; exit 1; fi
echo "$(date '+%T') Upload Kaggle version shards0-9 ..."
MSYS_NO_PATHCONV=1 bash cloud/kaggle-upload-turn.sh version Scherben0-9 2>&1 | tr '\r' '\n' | grep -v "%|" | tail -4
echo "OVERNIGHT RUN OK $(date '+%F %T')"
