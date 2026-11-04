#!/usr/bin/env bash
# Linux/macOS-Gegenstueck zu pc.cmd, z. B. fuer Trainingslaeufe auf einem Server.
# Einmalig: curl -LsSf https://astral.sh/uv/install.sh | sh   (installiert uv nach ~/.local/bin)
# Beispiel:  ./pc.sh train rl --run pros-3 --iterations 300 --tournaments 512 --anchor-coef 0.3
#            nohup ./pc.sh train deepcfr --run dcfr-2 --iterations 300 > dcfr-2.log 2>&1 &
# Die Windows-Werkzeuge unter tools/ werden hier nicht benutzt; uv legt Python und Pakete selbst an.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
UV="${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}"
export PYTHONIOENCODING=utf-8
export POKERCOLLECTOR_DATA="${POKERCOLLECTOR_DATA:-$ROOT/data}"
exec "$UV" run --quiet --project "$ROOT/collector" pokercollector "$@"
