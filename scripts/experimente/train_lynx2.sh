#!/usr/bin/env bash
#27.10.2026 evening: lynx-2 = Lynx (pros-h1@600) continued, now with 40% human bots (real player types
#from HandHQ) at the table. Testbench every 100 iterations: mensch480 + precise, paired against pros-h1@600 (= Lynx).
#End: entry test 600 fresh schemas against lynx. Continuable.
cd <Projektordner>
./pc.cmd train rl --run lynx-2 --widen-from pros-h1@600 --iterations 600 --tournaments 512 \
    --anchor-coef 0.3 --anchor pros-r1:0 --anchor-min-players 4 \
    --human-share 0.4 --random-share 0.05 --self-play-seats 0.3 --random-formats \
    --table-weights "2:3,3:2,4:2,5:2,6:3,7:1,8:1,9:1,10:1" \
    --exploit-every 100 --exploit-iters 30 \
    --bench-every 100 --bench-sets mensch480,praezise,pluribus --bench-ref pros-h1@600 \
    --gate-schemes 600 --champion lynx --name lynx-2 >> data/rl/lynx-2-run.txt 2>&1
echo "$(date '+%F %T') TRAINING FERTIG (Exit $?)" >> data/rl/lynx-2-run.txt
