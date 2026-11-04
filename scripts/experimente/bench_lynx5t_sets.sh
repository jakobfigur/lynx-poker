#!/usr/bin/env bash
# 31.10.: Test rig for the teacher-student lynx-5t (greedy and sampled) and greedy lynx-4 on hu480/mensch480/mix960
cd <Projektordner>/collector || exit 1
export UV_PYTHON_INSTALL_DIR=<Projektordner>/tools/python UV_CACHE_DIR=<Projektordner>/tools/uv-cache UV_LINK_MODE=copy UV_PYTHON_PREFERENCE=only-managed PYTHONIOENCODING=utf-8
UV=<Projektordner>/tools/uv/uv.exe
for pair in "nn?run=lynx-5t@1&greedy=1|lynx-5t-g" "nn?run=lynx-4@300&greedy=1|lynx-4-300-g" "nn?run=lynx-5t@1|lynx-5t-s"; do
  spec="${pair%%|*}"; name="${pair##*|}"
  echo "=== $name = $spec $(date +%H:%M)"
  "$UV" run --quiet --no-sync pokercollector bench run "$spec" --name "$name" --sets hu480,mensch480,mix960
done
echo "BENCHMARK COMPLETE $(date +%H:%M)"
