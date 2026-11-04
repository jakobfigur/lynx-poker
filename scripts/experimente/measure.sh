#!/usr/bin/env bash
# 27.10.2026: Precise test rig (mix960, pokerth480, hu480, 10max240), then search at runtime.
cd <Projektordner>
L=data/bench/measure.txt
for P in "rock rock" "pros-r1@300 nn?run=pros-r1@300" "pros-r3@200 nn?run=pros-r3@200" \
         "pros-r2@350 nn?run=pros-r2@350" "pros-2@300 nn?run=pros-2@300"; do
  set -- $P
  echo "$(date '+%F %T') praezise $1" >> $L
  ./pc.cmd bench run "$2" --name "$1" --sets praezise >> $L 2>&1
done
echo "$(date '+%F %T') Suche: search?bp=pros-r1@300,worlds=16 auf mix96,pokerth48,hu48" >> $L
./pc.cmd bench run "search?bp=pros-r1@300,worlds=16" --name "search-r1@300" --sets mix96,pokerth48,hu48 >> $L 2>&1
./pc.cmd bench compare search-r1@300 pros-r1@300 >> $L 2>&1
echo "$(date '+%F %T') MESSUNG FERTIG" >> $L
