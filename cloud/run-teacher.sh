#!/usr/bin/env bash
# Search as teacher (H5) on the server: N processes collect search decisions in parallel (each own seed/file).
# Call: nohup /opt/lynx/cloud/run-teacher.sh 16 60 > /opt/lynx/data/teacher.log 2>&1 &
#   -> 16 processes, 60 leaves per match (duplicate = 120 hands) over 4 opponents x 4 stacks = 16 matches per process
# Requires per scp (data/ is not pushed): data/valuenet/vnet-river-1.pt, data/rl/lynx-4/ckpt_000300.pt, data/rl/human-1/ckpt_000001.pt,
# data/humans/human-fold-1.npz, data/humans/human-25nl.json, data/league/players.json (see cloud/upload-teacher-data.sh).
set -euo pipefail
PROCS="${1:-$(nproc)}"
HANDS="${2:-60}"
OUT_DIR=/opt/lynx/data/teacher
mkdir -p "$OUT_DIR"
export PATH="$HOME/.local/bin:$PATH"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 TORCH_NUM_THREADS=1   # 16 Prozesse x 1 Kern, sonst Ueberbuchung (Last 27 auf 16 Kernen)
cd /opt/lynx
SEARCH="hus?bp=lynx-4-300&auto=1&iters=60&iters_river=150&threads=1&vnet=vnet-river-1"
echo "$(date -Is) Start: $PROCS processes, $HANDS deals per match"
for ((i = 0; i < PROCS; i++)); do
  out="$OUT_DIR/t1-$(printf %03d "$i").npz"
  if [[ -s "$out" ]]; then echo "$(date -Is) $out already exists"; continue; fi
  ./pc.sh train teacher-collect --search "$SEARCH" --student "nn?run=lynx-4@300" \
    --opponents "nn?run=lynx-4@300,nn?run=human-1@1&fold=human-fold-1,mensch-2,mensch-4" --stacks 25,50,100,200 \
    --hands "$HANDS" --seed $((1000 + 37 * i)) --out "$out" > "$OUT_DIR/t1-$(printf %03d "$i").log" 2>&1 &
done
wait
echo "$(date -Is) all processes complete"
ls -la "$OUT_DIR"
