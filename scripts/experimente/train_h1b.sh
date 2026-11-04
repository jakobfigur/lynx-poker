#!/usr/bin/env bash
# 27.10.2026 abends: pros-h1 weiter ab @600 (gleiches Rezept), Abschnitte bis 900/1200/1500.
# Pruefstand alle 100 It praezise gegen pros-h1@600 (best.json); am Abschnittsende Aufnahmepruefung mit
# 600 frischen Schemata gegen den aktuellen Liga-Besten (pros-h1 bzw. spaeter eingetragene pros-h1-<N>).
cd <Projektordner>
for TARGET in 900 1200 1500; do
  DONE=$(tail -1 data/rl/pros-h1/log.jsonl 2>/dev/null | sed -E 's/.*"iteration": ([0-9]+).*/\1/')
  [ -n "$DONE" ] && [ "$DONE" -ge "$TARGET" ] && continue
  CH=pros-h1
  for T in 900 1200; do grep -q "\"pros-h1-$T\"" data/league/players.json && CH=pros-h1-$T; done
  echo "$(date '+%F %T') Abschnitt bis $TARGET, Titelverteidiger $CH" >> data/rl/pros-h1/night.txt
  ./pc.cmd train rl --run pros-h1 --iterations $TARGET --tournaments 512 \
      --anchor-coef 0.3 --anchor pros-r1:0 --anchor-min-players 4 \
      --random-share 0.15 --self-play-seats 0.4 --random-formats --table-weights "2:4,3:3,4:2,5:1,6:2,7:1,8:1,9:1,10:1" \
      --exploit-every 100 --exploit-iters 30 \
      --bench-every 100 --bench-sets praezise,pluribus --bench-ref pros-h1@600 \
      --gate-schemes 600 --seed $TARGET --champion $CH --name pros-h1-$TARGET >> data/rl/pros-h1-run.txt 2>&1
  echo "$(date '+%F %T') Abschnitt bis $TARGET beendet (Exit $?)" >> data/rl/pros-h1/night.txt
done
echo "$(date '+%F %T') LAUF FERTIG" >> data/rl/pros-h1/night.txt
