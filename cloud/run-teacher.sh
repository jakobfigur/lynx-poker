#!/usr/bin/env bash
# Suche als Lehrer (H5) auf dem Server: N Prozesse sammeln parallel Suchentscheidungen (je eigener Seed/Datei).
# Aufruf: nohup /opt/lynx/cloud/run-teacher.sh 16 60 > /opt/lynx/data/teacher.log 2>&1 &
#   -> 16 Prozesse, je Match 60 Blaetter (duplicate = 120 Haende) ueber 4 Gegner x 4 Stacks = 16 Matches je Prozess
# Braucht per scp (data/ wird nicht gepusht): data/valuenet/vnet-river-1.pt, data/rl/lynx-4/ckpt_000300.pt, data/rl/human-1/ckpt_000001.pt,
# data/humans/human-fold-1.npz, data/humans/mensch-25nl.json, data/league/players.json (siehe cloud/upload-teacher-data.sh).
set -euo pipefail
PROCS="${1:-$(nproc)}"
HANDS="${2:-60}"
OUT_DIR=/opt/lynx/data/teacher
mkdir -p "$OUT_DIR"
export PATH="$HOME/.local/bin:$PATH"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 TORCH_NUM_THREADS=1   # 16 Prozesse x 1 Kern, sonst Ueberbuchung (Last 27 auf 16 Kernen)
cd /opt/lynx
SEARCH="hus?bp=lynx-4-300&auto=1&iters=60&iters_river=150&threads=1&vnet=vnet-river-1"
echo "$(date -Is) Start: $PROCS Prozesse, $HANDS Blaetter je Match"
for ((i = 0; i < PROCS; i++)); do
  out="$OUT_DIR/t1-$(printf %03d "$i").npz"
  if [[ -s "$out" ]]; then echo "$(date -Is) $out vorhanden"; continue; fi
  ./pc.sh train teacher-collect --search "$SEARCH" --student "nn?run=lynx-4@300" \
    --opponents "nn?run=lynx-4@300,nn?run=human-1@1&fold=human-fold-1,mensch-2,mensch-4" --stacks 25,50,100,200 \
    --hands "$HANDS" --seed $((1000 + 37 * i)) --out "$out" > "$OUT_DIR/t1-$(printf %03d "$i").log" 2>&1 &
done
wait
echo "$(date -Is) alle Prozesse fertig"
ls -la "$OUT_DIR"
