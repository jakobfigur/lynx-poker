#!/usr/bin/env bash
# Linux/macOS counterpart to pc.cmd, e.g. for training runs on a server.
# One-time: curl -LsSf https://astral.sh/uv/install.sh | sh   (installs uv to ~/.local/bin)
# Example:  ./pc.sh train rl --run pros-3 --iterations 300 --tournaments 512 --anchor-coef 0.3
#            nohup ./pc.sh train deepcfr --run dcfr-2 --iterations 300 > dcfr-2.log 2>&1 &
# The Windows tools under tools/ are not used here; uv sets up Python and packages itself.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
UV="${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}"
export PYTHONIOENCODING=utf-8
export POKERCOLLECTOR_DATA="${POKERCOLLECTOR_DATA:-$ROOT/data}"
exec "$UV" run --quiet --project "$ROOT/collector" pokercollector "$@"
