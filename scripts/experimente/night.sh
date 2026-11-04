#!/usr/bin/env bash
# Nachtlauf 26./27.10.2026: Multi-Format-Training pros-r2 in Abschnitten (jeder endet mit Aufnahmepruefung).
# Fortsetzbar: ein erneuter Aufruf macht beim gespeicherten Stand weiter (state.pt).
cd <Projektordner>
RUN=pros-r2
mkdir -p data/rl/$RUN
[ -f data/rl/$RUN/ckpt_000000.pt ] || cp data/rl/pros-r1/ckpt_000300.pt data/rl/$RUN/ckpt_000000.pt
for TARGET in 300 600 900 1200 1500; do
  DONE=$(tail -1 data/rl/$RUN/log.jsonl 2>/dev/null | sed -E 's/.*"iteration": ([0-9]+).*/\1/')
  [ -n "$DONE" ] && [ "$DONE" -ge "$TARGET" ] && continue
  CH=pros-ppo2
  grep -q '"pros-r2"' data/league/players.json && CH=pros-r2
  echo "$(date '+%F %T') Abschnitt bis $TARGET, Titelverteidiger $CH" >> data/rl/$RUN/night.txt
  ./pc.cmd train rl --run $RUN --iterations $TARGET --tournaments 512 --anchor-coef 0.3 --anchor pros-r1:0 \
      --random-share 0.3 --exploit-every 50 --exploit-iters 30 --random-formats \
      --champion $CH --name pros-r2-$TARGET >> data/rl/$RUN/run.txt 2>&1
  echo "$(date '+%F %T') Abschnitt bis $TARGET beendet (Exit $?)" >> data/rl/$RUN/night.txt
done
echo "$(date '+%F %T') NACHTLAUF FERTIG" >> data/rl/$RUN/night.txt
