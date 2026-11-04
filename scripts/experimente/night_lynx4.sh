#!/usr/bin/env bash
# Nacht 28./29.10.2026: lynx-4 = lynx-3-300 weiter mit ICM-Belohnung (Aenderung des Turnier-Eigenkapitals
# statt Chips), Ausbeuter alle 50 It, mehr 3er-/6er-Tische (PokerTH-Format), Lernrate 2e-4.
# Abschnitte 300/600/900/1200, je Aufnahmepruefung (600 frische Turniere) gegen den Liga-Besten.
# Danach: Suche gegen Netz auf hu480 (Entscheidung Live-Standard). Fortsetzbar.
cd <Projektordner>
RUN=lynx-4
mkdir -p data/rl/$RUN
for TARGET in 300 600 900 1200; do
  DONE=$(tail -1 data/rl/$RUN/log.jsonl 2>/dev/null | sed -E 's/.*"iteration": ([0-9]+).*/\1/')
  [ -n "$DONE" ] && [ "$DONE" -ge "$TARGET" ] && continue
  CH=lynx-3-300
  for T in 300 600 900; do grep -q "\"lynx-4-$T\"" data/league/players.json && CH=lynx-4-$T; done
  echo "$(date '+%F %T') Abschnitt bis $TARGET, Titelverteidiger $CH" >> data/rl/$RUN/night.txt
  ./pc.cmd train rl --run $RUN --widen-from lynx-3@300 --iterations $TARGET --tournaments 512 \
      --icm 1.0 --lr 2e-4 \
      --anchor-coef 0.3 --anchor pros-r1:0 --anchor-min-players 4 \
      --human-share 0.4 --random-share 0.1 --self-play-seats 0.3 --random-formats \
      --table-weights "2:3,3:3,4:2,5:2,6:4,7:1,8:1,9:1,10:1" \
      --exploit-every 50 --exploit-iters 30 \
      --bench-every 100 --bench-sets mensch480,praezise,pluribus --bench-ref lynx-3@300 \
      --gate-schemes 600 --seed $((4000 + TARGET)) --champion $CH --name lynx-4-$TARGET >> data/rl/$RUN-run.txt 2>&1
  echo "$(date '+%F %T') Abschnitt bis $TARGET beendet (Exit $?)" >> data/rl/$RUN/night.txt
done
echo "$(date '+%F %T') TRAINING FERTIG" >> data/rl/$RUN/night.txt
# Suche gegen Netz (PokerTH-Format hu480), 6 Worker, niemand spielt
cd collector
../tools/uv/uv.exe run --quiet --no-sync python ../bench_hus_nacht.py > ../data/bench/hus-vs-netz-pokerth.txt 2>&1
echo "$(date '+%F %T') SUCHE-VERGLEICH FERTIG (Exit $?)" >> ../data/rl/$RUN/night.txt
