#!/usr/bin/env bash
# 27.10.2026 06:40: Format test rig of the candidates, then continue Deep CFR.
cd <Projektordner>
L=data/rl/morning.txt
for P in "rock rock" "pros-2@300 nn?run=pros-2@300" "pros-r1@300 nn?run=pros-r1@300" \
         "pros-r2@350 nn?run=pros-r2@350" "pros-r3@200 nn?run=pros-r3@200" "pros-r3@450 nn?run=pros-r3@450"; do
  set -- $P
  echo "$(date '+%F %T') Pruefstand $1" >> $L
  ./pc.cmd bench run "$2" --name "$1" --sets formate,fest48,mix96 >> $L 2>&1
done
echo "$(date '+%F %T') BENCHMARK COMPLETE, starte Deep CFR" >> $L
./pc.cmd train deepcfr --run dcfr-1 --iterations 100 --traversals 600 --buffer 1000000 >> data/rl/dcfr-1-run.txt 2>&1
echo "$(date '+%F %T') DEEP CFR beendet (Exit $?)" >> $L
