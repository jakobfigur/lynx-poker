#!/usr/bin/env bash
#27.10.2026: pros-o1 = pros-r1@300 with opponent model (feat-3). Controlled via the precise testbench:
#every 100 iterations precise sets, paired against pros-r1@300; best state -> data/rl/pros-o1/best.json.
#At the end entry test with fresh cards against pros-r1. Continuable.
cd <Projektordner>
./pc.cmd train rl --run pros-o1 --widen-from pros-r1@300 --features feat-3 --iterations 600 --tournaments 512 \
    --anchor-coef 0.3 --anchor pros-r1:0 --random-share 0.5 --random-formats --exploit-every 100 --exploit-iters 30 \
    --bench-every 100 --bench-sets praezise,pluribus --bench-ref pros-r1@300 \
    --champion pros-r1 --name pros-o1 >> data/rl/pros-o1-run.txt 2>&1
echo "$(date '+%F %T') TRAINING FERTIG (Exit $?)" >> data/rl/pros-o1-run.txt
