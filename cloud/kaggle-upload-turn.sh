#!/usr/bin/env bash
# Turn shards (turn-leaf-*.npz in data/valuenet/hetzner-turn/) as private Kaggle dataset YOUR_KAGGLE_USER/lynx-vdata-turn
# upload. Run from project folder:  bash cloud/kaggle-upload-turn.sh create|version [message]
# The Kaggle CLI stores helper files under %TEMP%\.kaggle-uploads\<relative folder>; the folder must exist beforehand.
set -euo pipefail
cd "$(dirname "$0")/.."
MODE="${1:-version}"
MSG="${2:-Turn-Scherben}"
export KAGGLE_API_TOKEN="$(cat data/cloud/kaggle.token)"
export UV_CACHE_DIR=$HOME/AppData/Local/uv-cache
mkdir -p "$HOME/AppData/Local/Temp/.kaggle-uploads/data/valuenet/hetzner-turn"
ls -la data/valuenet/hetzner-turn/
if [[ "$MODE" == "create" ]]; then
  tools/uv/uv.exe tool run --quiet --from kaggle kaggle datasets create -p data/valuenet/hetzner-turn --dir-mode skip
else
  tools/uv/uv.exe tool run --quiet --from kaggle kaggle datasets version -p data/valuenet/hetzner-turn --dir-mode skip -m "$MSG"
fi
