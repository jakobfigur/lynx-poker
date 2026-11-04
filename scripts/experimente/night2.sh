#!/usr/bin/env bash
#Night run part 2 (27.10.2026, from 03:40): pros-r2 declined from iteration 350 on the testbench (mix96 +20 -> +10).
#New run pros-r3 from pros-r2@350 with half the learning rate and stronger leash. Continuable.
cd <Projektordner>
RUN=pros-r3
mkdir -p data/rl/$RUN
[ -f data/rl/$RUN/ckpt_000000.pt ] || cp data/rl/pros-r2/ckpt_000350.pt data/rl/$RUN/ckpt_000000.pt
for TARGET in 200 400 600; do
  DONE=$(tail -1 data/rl/$RUN/log.jsonl 2>/dev/null | sed -E 's/.*"iteration": ([0-9]+).*/\1/')
  [ -n "$DONE" ] && [ "$DONE" -ge "$TARGET" ] && continue
  CH=pros-ppo2
  grep -q '"pros-r3' data/league/players.json && CH=$(grep -o '"pros-r3-[0-9]*"' data/league/players.json | tail -1 | tr -d '"')
  echo "$(date '+%F %T') Abschnitt bis $TARGET, Titelverteidiger $CH" >> data/rl/$RUN/night.txt
  ./pc.cmd train rl --run $RUN --iterations $TARGET --tournaments 512 --anchor-coef 0.5 --anchor pros-r1:0 \
      --lr 1.5e-4 --random-share 0.3 --exploit-every 50 --exploit-iters 30 --random-formats \
      --champion $CH --name pros-r3-$TARGET >> data/rl/$RUN/run.txt 2>&1
  echo "$(date '+%F %T') Abschnitt bis $TARGET beendet (Exit $?)" >> data/rl/$RUN/night.txt
done
echo "$(date '+%F %T') NACHTLAUF FERTIG" >> data/rl/$RUN/night.txt
