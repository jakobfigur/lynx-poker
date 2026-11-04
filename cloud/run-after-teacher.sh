#!/usr/bin/env bash
# Kette nach der Lehrer-Sammlung (31.10.): wartet auf run-teacher.sh, dann
#   1. Benchmark Suche vs Menschen-Bot mit Folds, 16 Prozesse (cloud/bench_humanopp_srv.py -> data/bench/humanopp_srv.txt)
#   2. erste Turn-Tranche fuer das Turn-Wertnetz (run-vdata.sh turn-leaf 0 10 2000 -> data/valuenet/turn-leaf-*.npz)
# Aufruf: setsid nohup /opt/lynx/cloud/run-after-teacher.sh > /opt/lynx/data/after.log 2>&1 < /dev/null &
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 TORCH_NUM_THREADS=1
export PYTHONIOENCODING=utf-8 POKERCOLLECTOR_DATA=/opt/lynx/data
cd /opt/lynx
BENCH_BLOCKS="${BENCH_BLOCKS:-64}"
echo "$(date -Is) warte auf Lehrer-Sammlung ..."
until grep -q "alle Prozesse fertig" /opt/lynx/data/teacher.log 2>/dev/null; do sleep 60; done
echo "$(date -Is) Lehrer fertig: $(ls /opt/lynx/data/teacher/*.npz 2>/dev/null | wc -l) Dateien"
mkdir -p /opt/lynx/data/bench
echo "$(date -Is) Benchmark Suche vs Menschen-Bot, $BENCH_BLOCKS Bloecke ..."
sed -i "s/^BLOCKS = .*/BLOCKS = $BENCH_BLOCKS/" /opt/lynx/cloud/bench_humanopp_srv.py
uv run --quiet --project /opt/lynx/collector python /opt/lynx/cloud/bench_humanopp_srv.py 16 > /opt/lynx/data/bench/humanopp_srv.txt 2> /opt/lynx/data/bench/humanopp_srv.err.txt
echo "$(date -Is) Benchmark fertig (exit $?)"
echo "$(date -Is) Turn-Tranche turn-leaf 0..9 x 2000 Flop-Seeds ..."
WORKERS=16 /opt/lynx/cloud/run-vdata.sh turn-leaf 0 10 2000 > /opt/lynx/data/vdata-turn.log 2>&1
echo "$(date -Is) Turn-Tranche fertig (exit $?)"
ls -la /opt/lynx/data/valuenet/
echo "KETTE FERTIG $(date -Is)"
