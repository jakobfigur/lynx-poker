#!/usr/bin/env bash
# Chain after teacher collection (31.10.): waits for run-teacher.sh, then
#   1. Benchmark search vs human bot with folds, 16 processes (cloud/bench_humanopp_srv.py -> data/bench/humanopp_srv.txt)
#   2. first turn tranche for the turn value network (run-vdata.sh turn-leaf 0 10 2000 -> data/valuenet/turn-leaf-*.npz)
# Call: setsid nohup /opt/lynx/cloud/run-after-teacher.sh > /opt/lynx/data/after.log 2>&1 < /dev/null &
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 TORCH_NUM_THREADS=1
export PYTHONIOENCODING=utf-8 POKERCOLLECTOR_DATA=/opt/lynx/data
cd /opt/lynx
BENCH_BLOCKS="${BENCH_BLOCKS:-64}"
echo "$(date -Is) waiting for teacher collection ..."
until grep -q "alle Prozesse fertig" /opt/lynx/data/teacher.log 2>/dev/null; do sleep 60; done
echo "$(date -Is) Teacher complete: $(ls /opt/lynx/data/teacher/*.npz 2>/dev/null | wc -l) files"
mkdir -p /opt/lynx/data/bench
echo "$(date -Is) Benchmark search vs human model, $BENCH_BLOCKS blocks ..."
sed -i "s/^BLOCKS = .*/BLOCKS = $BENCH_BLOCKS/" /opt/lynx/cloud/bench_humanopp_srv.py
uv run --quiet --project /opt/lynx/collector python /opt/lynx/cloud/bench_humanopp_srv.py 16 > /opt/lynx/data/bench/humanopp_srv.txt 2> /opt/lynx/data/bench/humanopp_srv.err.txt
echo "$(date -Is) Benchmark complete (exit $?)"
echo "$(date -Is) Turn batch turn-leaf 0..9 x 2000 flop seeds ..."
WORKERS=16 /opt/lynx/cloud/run-vdata.sh turn-leaf 0 10 2000 > /opt/lynx/data/vdata-turn.log 2>&1
echo "$(date -Is) Turn batch complete (exit $?)"
ls -la /opt/lynx/data/valuenet/
echo "PIPELINE COMPLETE $(date -Is)"
