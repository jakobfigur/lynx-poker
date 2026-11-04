#!/usr/bin/env bash
# 27.10.2026: pros-h1 = pros-r1@300 aufgeweitet auf feat-3 + act-2 (8 Aktionen: + 1/3 Pot, Min-Raise).
# Staerkere Gegner: 40 % der Plaetze fruehere eigene Versionen, nur 15 % Zufalls-Stilbots, Ausbeuter alle 100.
# Viel mehr Heads-up/3er-Tische, Leine (Pluribus = 6er) erst ab 4 Spielern.
# Gesteuert ueber den praezisen Pruefstand gegen pros-r1@300 (best.json). Fortsetzbar.
cd <Projektordner>
./pc.cmd train rl --run pros-h1 --widen-from pros-r1@300 --features feat-3 --actions 8 --iterations 600 \
    --tournaments 512 --anchor-coef 0.3 --anchor pros-r1:0 --anchor-min-players 4 \
    --random-share 0.15 --self-play-seats 0.4 --random-formats --table-weights "2:4,3:3,4:2,5:1,6:2,7:1,8:1,9:1,10:1" \
    --exploit-every 100 --exploit-iters 30 \
    --bench-every 100 --bench-sets praezise,pluribus --bench-ref pros-r1@300 \
    --champion pros-r1 --name pros-h1 >> data/rl/pros-h1-run.txt 2>&1
echo "$(date '+%F %T') TRAINING FERTIG (Exit $?)" >> data/rl/pros-h1-run.txt
