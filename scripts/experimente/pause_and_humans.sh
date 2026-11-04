#!/usr/bin/env bash
# 27.10.2026: nach Abschnitt 900 Training pausieren (spaeter ./train_h1b.sh setzt fort), dann HandHQ-Auswertung
# allein mit 8 Prozessen, danach Mensch-Bots anpassen.
cd <Projektordner>
until grep -q "Abschnitt bis 900 beendet" data/rl/pros-h1/night.txt; do sleep 30; done
powershell -c "Get-CimInstance Win32_Process | ? { \$_.CommandLine -match 'train_h1b.sh|train rl --run pros-h1' } | % { taskkill /T /F /PID \$_.ProcessId 2>\$null | Out-Null }"
echo "$(date '+%F %T') Training nach Abschnitt 900 pausiert (fortsetzen: ./train_h1b.sh)" >> data/rl/pros-h1/night.txt
sleep 5
./pc.cmd data humans --sets PS-2009-07-01_2009-07-23_25NLH_OBFU,PTY-2009-07-01_2009-07-23_25NLH_OBFU \
    --name handhq-25nl --min-hands 300 --workers 8 > data/humans-25nl.txt 2>&1
./pc.cmd train humans-fit --source handhq-25nl --name mensch-25nl > data/humans-fit.txt 2>&1
echo "$(date '+%F %T') MENSCH-BOTS FERTIG" >> data/humans-fit.txt
