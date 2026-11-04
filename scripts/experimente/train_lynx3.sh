#!/usr/bin/env bash
#Night 27/28.10.2026: lynx-3 = Lynx 2 (lynx-2@500) continued, same recipe (40% human bots).
#Sections up to 300/600/900/1200/1500, each with entry test (600 fresh tournaments) against the league best.
#Testbench every 100 iterations: mensch480 + precise, paired against lynx-2@500 (best.json). Continuable.
cd <Projektordner>
RUN=lynx-3
mkdir -p data/rl/$RUN
for TARGET in 300 600 900 1200 1500; do
  DONE=$(tail -1 data/rl/$RUN/log.jsonl 2>/dev/null | sed -E 's/.*"iteration": ([0-9]+).*/\1/')
  [ -n "$DONE" ] && [ "$DONE" -ge "$TARGET" ] && continue
  CH=lynx-2
  for T in 300 600 900 1200; do grep -q "\"lynx-3-$T\"" data/league/players.json && CH=lynx-3-$T; done
  echo "$(date '+%F %T') Abschnitt bis $TARGET, Titelverteidiger $CH" >> data/rl/$RUN/night.txt
  ./pc.cmd train rl --run $RUN --widen-from lynx-2@500 --iterations $TARGET --tournaments 512 \
      --anchor-coef 0.3 --anchor pros-r1:0 --anchor-min-players 4 \
      --human-share 0.4 --random-share 0.05 --self-play-seats 0.3 --random-formats \
      --table-weights "2:3,3:2,4:2,5:2,6:3,7:1,8:1,9:1,10:1" \
      --exploit-every 100 --exploit-iters 30 \
      --bench-every 100 --bench-sets mensch480,praezise,pluribus --bench-ref lynx-2@500 \
      --gate-schemes 600 --seed $TARGET --champion $CH --name lynx-3-$TARGET >> data/rl/$RUN-run.txt 2>&1
  echo "$(date '+%F %T') Abschnitt bis $TARGET beendet (Exit $?)" >> data/rl/$RUN/night.txt
done
echo "$(date '+%F %T') NACHTLAUF FERTIG" >> data/rl/$RUN/night.txt
