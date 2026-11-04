#!/usr/bin/env bash
# Einmalige Einrichtung eines frischen Hetzner-Servers (Ubuntu 24.04) fuer Lynx-Rechenlaeufe.
# Wird von cloud/hetzner.py create aufgerufen, nachdem der Code nach /opt/lynx kopiert wurde.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
cd /opt/lynx

apt-get update -qq
apt-get install -y -qq --no-install-recommends curl ca-certificates libgl1 libglib2.0-0 htop > /dev/null

if ! command -v uv > /dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null
fi
export PATH="$HOME/.local/bin:$PATH"

# Python + Pakete (torch-CPU ueber den pyproject-Index, numba, numpy, opencv headless reicht nicht: pyproject
# verlangt opencv-python, das mit libgl1 laeuft). Kein dev-Gruppe (pytest) noetig.
cd collector
uv python install 3.12 > /dev/null
uv sync --quiet --no-dev
cd ..

# Rauchtest: Kernel kompiliert, 20 River-Situationen loesen
./pc.sh train valuedata river --n 20 --seed 999000000 --workers 2 --threads 1 --out /opt/lynx/data/valuenet/smoke.npz
rm -f /opt/lynx/data/valuenet/smoke.npz
echo "Server eingerichtet: $(nproc) Kerne, $(free -g | awk '/Mem/{print $2}') GB RAM"
