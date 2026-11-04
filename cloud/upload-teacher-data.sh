#!/usr/bin/env bash
# Copy data files for teacher collection to server (hetzner.py push excludes data/).
# Call: cloud/upload-teacher-data.sh <IP>
set -euo pipefail
IP="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY="$ROOT/data/cloud/lynx_hetzner"
S="scp -i $KEY -o StrictHostKeyChecking=accept-new -o BatchMode=yes"
ssh -i "$KEY" -o BatchMode=yes "root@$IP" "mkdir -p /opt/lynx/data/valuenet /opt/lynx/data/rl/lynx-4 /opt/lynx/data/rl/human-1 /opt/lynx/data/humans /opt/lynx/data/league /opt/lynx/data/teacher"
$S "$ROOT/data/valuenet/vnet-river-1.pt" "root@$IP:/opt/lynx/data/valuenet/"
# 31.10.: turn-capable net (if available; vnet-2b replaces vnet-2 once trained) and teacher-student lynx-5t
for f in vnet-2.pt vnet-2b.pt; do [[ -f "$ROOT/data/valuenet/$f" ]] && $S "$ROOT/data/valuenet/$f" "root@$IP:/opt/lynx/data/valuenet/"; done
if [[ -f "$ROOT/data/rl/lynx-5t/ckpt_000001.pt" ]]; then
  ssh -i "$KEY" -o BatchMode=yes "root@$IP" "mkdir -p /opt/lynx/data/rl/lynx-5t"
  $S "$ROOT/data/rl/lynx-5t/ckpt_000001.pt" "root@$IP:/opt/lynx/data/rl/lynx-5t/"
fi
$S "$ROOT/data/rl/lynx-4/ckpt_000300.pt" "root@$IP:/opt/lynx/data/rl/lynx-4/"
$S "$ROOT/data/rl/human-1/ckpt_000001.pt" "root@$IP:/opt/lynx/data/rl/human-1/"
$S "$ROOT/data/humans/human-fold-1.npz" "$ROOT/data/humans/mensch-25nl.json" "root@$IP:/opt/lynx/data/humans/"
$S "$ROOT/data/league/players.json" "root@$IP:/opt/lynx/data/league/"
ssh -i "$KEY" -o BatchMode=yes "root@$IP" "du -sh /opt/lynx/data/*"
