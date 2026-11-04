#!/usr/bin/env bash
# River-Daten fuer das Wertnetz auf dem Server rechnen: Scherben zu je N Situationen, Seeds fortlaufend.
# Aufruf (auf dem Server, im Hintergrund):
#   nohup /opt/lynx/cloud/run-vdata.sh river 0 20 25000 > /opt/lynx/data/vdata.log 2>&1 &
#     -> Scherben 0..19 (Seeds 0, 25000, ...), je 25000 Situationen = 500000 (Tranche 1)
#   Tranche 2: run-vdata.sh river 20 40 25000  (Seeds 500000 ...)
#   Turn (Stufe 2): run-vdata.sh turn-leaf 0 10 2000  -> je Scherbe 2000 Flop-Seeds x bis 12 Turn-Zeilen (~24k), River per vnet-river-1
# Fortschritt: tail -f /opt/lynx/data/vdata.log ; fertige Scherben: ls -la /opt/lynx/data/valuenet/
# Eine fertige Scherbe wird uebersprungen (Wiederaufnahme nach Abbruch).
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
echo "$(date -Is) Start $STREET Scherben $FROM..$((TO-1)) x $N, $WORKERS Prozesse"
for ((s = FROM; s < TO; s++)); do
  seed=$((s * N))
  out="$OUT_DIR/$STREET-$(printf %08d "$seed").npz"
  if [[ -s "$out" ]]; then
    echo "$(date -Is) Scherbe $s vorhanden, uebersprungen"
    continue
  fi
  echo "$(date -Is) Scherbe $s (Seed $seed) ..."
  ./pc.sh train valuedata "$STREET" --n "$N" --seed "$seed" --workers "$WORKERS" --threads 1 --out "$out.tmp.npz"
  mv "$out.tmp.npz" "$out"
  echo "$(date -Is) Scherbe $s fertig: $(du -h "$out" | cut -f1)"
done
echo "$(date -Is) alle Scherben fertig"
