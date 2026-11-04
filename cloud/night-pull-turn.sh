#!/usr/bin/env bash
# Nachtauftrag 31.10./1.11.: fehlende Turn-Scherben von lehrer-1 holen, pruefen, als Kaggle-Dataset-Version hochladen.
# Aufruf aus dem Projektordner (Git-Bash):  MSYS_NO_PATHCONV=1 bash cloud/night-pull-turn.sh [IP]
# Gibt am Ende "NACHT OK" aus, wenn alle 10 Scherben lokal und geprueft sind; sonst "NACHT UNVOLLSTAENDIG".
# Den Server loescht dieses Skript NICHT (das macht Claude nach Sichtkontrolle: python cloud/hetzner.py delete lehrer-1).
set -uo pipefail
cd "$(dirname "$0")/.."
IP="${1:-SERVER_IP}"
KEY=data/cloud/lynx_hetzner
DST=data/valuenet/hetzner-turn
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o BatchMode=yes root@$IP"
echo "$(date '+%F %T') Serverstand:"
$SSH 'ls -la /opt/lynx/data/valuenet/ | grep turn-leaf; tail -2 /opt/lynx/data/vdata-turn.log; tail -1 /opt/lynx/data/after.log' || { echo "NACHT UNVOLLSTAENDIG (ssh)"; exit 1; }
for i in 0 1 2 3 4 5 6 7 8 9; do
  f=$(printf "turn-leaf-%08d.npz" $((i * 2000)))
  if [[ -s "$DST/$f" ]]; then continue; fi
  if $SSH "test -s /opt/lynx/data/valuenet/$f"; then
    echo "$(date '+%T') hole $f ..."
    scp -q -i $KEY -o StrictHostKeyChecking=no "root@$IP:/opt/lynx/data/valuenet/$f" "$DST/$f.part" && mv "$DST/$f.part" "$DST/$f" || echo "FEHLER beim Holen von $f"
  else
    echo "$f auf dem Server noch nicht fertig"
  fi
done
echo "$(date '+%T') Pruefung:"
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
if [[ $rc -ne 0 ]]; then echo "NACHT UNVOLLSTAENDIG (Scherben fehlen oder defekt, kein Upload)"; exit 1; fi
echo "$(date '+%T') Upload Kaggle-Version Scherben0-9 ..."
MSYS_NO_PATHCONV=1 bash cloud/kaggle-upload-turn.sh version Scherben0-9 2>&1 | tr '\r' '\n' | grep -v "%|" | tail -4
echo "NACHT OK $(date '+%F %T')"
