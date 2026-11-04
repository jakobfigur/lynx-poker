@echo off
rem 31.10.: Pruefstand fuer den Lehrer-Schueler lynx-5t (greedy und gesampelt) und greedy lynx-4 auf hu480/mensch480/mix960
setlocal
set "ROOT=<Projektordner>\"
set "UV_PYTHON_INSTALL_DIR=%ROOT%tools\python"
set "UV_CACHE_DIR=%ROOT%tools\uv-cache"
set "UV_LINK_MODE=copy"
set "UV_PYTHON_PREFERENCE=only-managed"
set "PYTHONIOENCODING=utf-8"
cd /d "%ROOT%collector"
echo === lynx-5t-g = nn?run=lynx-5t@1^&greedy=1 %TIME%
"%ROOT%tools\uv\uv.exe" run --quiet --no-sync pokercollector bench run "nn?run=lynx-5t@1&greedy=1" --name lynx-5t-g --sets hu480,mensch480,mix960
echo === lynx-4-300-g = nn?run=lynx-4@300^&greedy=1 %TIME%
"%ROOT%tools\uv\uv.exe" run --quiet --no-sync pokercollector bench run "nn?run=lynx-4@300&greedy=1" --name lynx-4-300-g --sets hu480,mensch480,mix960
echo === lynx-5t-s = nn?run=lynx-5t@1 %TIME%
"%ROOT%tools\uv\uv.exe" run --quiet --no-sync pokercollector bench run "nn?run=lynx-5t@1" --name lynx-5t-s --sets hu480,mensch480,mix960
echo PRUEFSTAND FERTIG %TIME%
endlocal
