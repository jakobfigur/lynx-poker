#!/usr/bin/env bash
# Turn-Scherben (turn-leaf-*.npz in data/valuenet/hetzner-turn/) als privates Kaggle-Dataset YOUR_KAGGLE_USER/lynx-vdata-turn
# hochladen. Aufruf aus dem Projektordner:  bash cloud/kaggle-upload-turn.sh create|version [Nachricht]
# Die Kaggle-CLI legt Hilfsdateien unter %TEMP%\.kaggle-uploads\<relativer Ordner> ab; der Ordner muss vorher existieren.
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
