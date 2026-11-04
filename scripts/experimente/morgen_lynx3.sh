#!/usr/bin/env bash
# After the night run (28.10.): predefined confirmations for the last passed lynx-3 state,
# then Slumbot (lynx-2@500 up to 20000 hands, then candidate 10000 hands). Sequentially due to RAM.
cd <Projektordner>
LOG=data/rl/lynx-3/morgen.txt
grep -q "NACHTLAUF FERTIG" data/rl/lynx-3/night.txt || { echo "$(date '+%F %T') Nachtlauf nicht complete" >> $LOG; exit 1; }
N=
for T in 300 600 900 1200 1500; do grep -q "\"lynx-3-$T\"" data/league/players.json && N=$T; done
echo "$(date '+%F %T') Kandidat lynx-3@$N" >> $LOG
if [ ! -f data/rl/lynx-3-bestaetigung-mensch.json ]; then
  (cd collector && PYTHONIOENCODING=utf-8 ../tools/uv/uv.exe run --quiet --no-sync python confirm_lynx3.py lynx-3@$N) >> $LOG 2>&1
fi
if ! grep -q "Liga-Gate fertig" $LOG; then
  ./pc.cmd train gate "nn?run=lynx-3@$N" --champion lynx-2 --schemes 600 --seed 2810 >> $LOG 2>&1
  echo "$(date '+%F %T') Liga-Gate complete" >> $LOG
fi
HAVE=$(wc -l < data/bench/slumbot/lynx-2@500.jsonl)
[ "$HAVE" -lt 20000 ] && ./pc.cmd bench slumbot "nn?run=lynx-2@500" --name lynx-2@500 --hands $((20000-HAVE)) --workers 6 > data/bench/slumbot-lynx2.txt 2>&1
echo "$(date '+%F %T') Slumbot lynx-2 complete: $(tail -3 data/bench/slumbot-lynx2.txt | tr '\n' ' ')" >> $LOG
HAVE=$(cat data/bench/slumbot/lynx-3@$N.jsonl 2>/dev/null | wc -l)
[ "$HAVE" -lt 10000 ] && ./pc.cmd bench slumbot "nn?run=lynx-3@$N" --name lynx-3@$N --hands $((10000-HAVE)) --workers 6 > data/bench/slumbot-lynx3.txt 2>&1
echo "$(date '+%F %T') Slumbot lynx-3@$N complete: $(tail -3 data/bench/slumbot-lynx3.txt | tr '\n' ' ')" >> $LOG
echo "$(date '+%F %T') MORGEN FERTIG" >> $LOG
