#!/usr/bin/env bash
# Compute river data for the value network on the server: fragments with N situations each, seeds sequential.
# Call (on server, in background):
#   nohup /opt/lynx/cloud/run-vdata.sh river 0 20 25000 > /opt/lynx/data/vdata.log 2>&1 &
#     -> fragments 0..19 (seeds 0, 25000, ...), 25000 situations each = 500000 (tranche 1)
#   Tranche 2: run-vdata.sh river 20 40 25000  (seeds 500000 ...)
#   Turn (level 2): run-vdata.sh turn-leaf 0 10 2000  -> per fragment 2000 flop seeds x up to 12 turn rows (~24k), river via vnet-river-1
# Progress: tail -f /opt/lynx/data/vdata.log ; finished fragments: ls -la /opt/lynx/data/valuenet/
# A finished fragment is skipped (resume after interruption).
set -euo pipefail
STREET="${1:-river}"
FROM="${2:-0}"
TO="${3:-20}"
N="${4:-25000}"
WORKERS="${WORKERS:-$(nproc)}"
OUT_DIR=/opt/lynx/data/valuenet
mkdir -p "$OUT_DIR"
export PATH="$HOME/.local/bin:$PATH"
cd /opt/lynx
echo "$(date -Is) Start $STREET shards $FROM..$((TO-1)) x $N, $WORKERS processes"
for ((s = FROM; s < TO; s++)); do
  seed=$((s * N))
  out="$OUT_DIR/$STREET-$(printf %08d "$seed").npz"
  if [[ -s "$out" ]]; then
    echo "$(date -Is) Shard $s exists, skipped"
    continue
  fi
  echo "$(date -Is) Shard $s (Seed $seed) ..."
  ./pc.sh train valuedata "$STREET" --n "$N" --seed "$seed" --workers "$WORKERS" --threads 1 --out "$out.tmp.npz"
  mv "$out.tmp.npz" "$out"
  echo "$(date -Is) Shard $s complete: $(du -h "$out" | cut -f1)"
done
echo "$(date -Is) all shards complete"
