#!/usr/bin/env bash
# One-time setup of a fresh Hetzner server (Ubuntu 24.04) for Lynx runs.
# Called by cloud/hetzner.py create after code has been copied to /opt/lynx.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
cd /opt/lynx

apt-get update -qq
apt-get install -y -qq --no-install-recommends curl ca-certificates libgl1 libglib2.0-0 htop > /dev/null

if ! command -v uv > /dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null
fi
export PATH="$HOME/.local/bin:$PATH"

# Python + packages (torch-CPU via pyproject index, numba, numpy, headless opencv not enough: pyproject
# requires opencv-python, which runs with libgl1). No dev group (pytest) needed.
cd collector
uv python install 3.12 > /dev/null
uv sync --quiet --no-dev
cd ..

# Smoke test: kernel compiles, solves 20 river situations
./pc.sh train valuedata river --n 20 --seed 999000000 --workers 2 --threads 1 --out /opt/lynx/data/valuenet/smoke.npz
rm -f /opt/lynx/data/valuenet/smoke.npz
echo "Server configured: $(nproc) cores, $(free -g | awk '/Mem/{print $2}') GB RAM"
