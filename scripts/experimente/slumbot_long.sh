#!/usr/bin/env bash
#Long Slumbot measurement pros-r1@300 up to 20000 hands (continuable; runs in parallel, minimal CPU).
cd <Projektordner>
while pgrep -f "bench slumbot" >/dev/null 2>&1 || powershell -c "if (Get-CimInstance Win32_Process | ? { \$_.CommandLine -match 'bench slumbot' -and \$_.Name -eq 'pokercollector.exe' }) { exit 0 } else { exit 1 }"; do sleep 60; done
N=$(wc -l < data/bench/slumbot/pros-r1@300.jsonl)
REST=$((20000 - N))
[ $REST -gt 0 ] && ./pc.cmd bench slumbot "nn?run=pros-r1@300" --name pros-r1@300 --hands $REST --workers 6 > data/bench/slumbot-r1-long.txt 2>&1
