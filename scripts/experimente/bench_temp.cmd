@echo off
rem 31.10.: Temperatur-Messung (HU-Cash, Scratchpad-Skript) und Pruefstand fuer lynx-4@300 / lynx-5t mit Temperatur
setlocal
if "%~1"=="" (
  call "%~f0" protokoll > "<Projektordner>\data\bench\temp-pruefstand.txt" 2>&1
  exit /b
)
set "ROOT=<Projektordner>\"
set "UV_PYTHON_INSTALL_DIR=%ROOT%tools\python"
set "UV_CACHE_DIR=%ROOT%tools\uv-cache"
set "UV_LINK_MODE=copy"
set "UV_PYTHON_PREFERENCE=only-managed"
set "PYTHONIOENCODING=utf-8"
cd /d "%ROOT%collector"
echo === HU-Cash Temperatur %TIME%
"%ROOT%tools\uv\uv.exe" run --quiet --no-sync python "<scratchpad>" > "%ROOT%data\bench\temp-hu.txt" 2>&1
echo === Pruefstand lynx-4-300-t05 %TIME%
"%ROOT%tools\uv\uv.exe" run --quiet --no-sync pokercollector bench run "nn?run=lynx-4@300&temp=0.5" --name lynx-4-300-t05 --sets hu480,mensch480,mix960
echo === Pruefstand lynx-4-300-t03 %TIME%
"%ROOT%tools\uv\uv.exe" run --quiet --no-sync pokercollector bench run "nn?run=lynx-4@300&temp=0.3" --name lynx-4-300-t03 --sets hu480,mensch480,mix960
echo === Pruefstand lynx-5t-t05 %TIME%
"%ROOT%tools\uv\uv.exe" run --quiet --no-sync pokercollector bench run "nn?run=lynx-5t@1&temp=0.5" --name lynx-5t-t05 --sets hu480,mensch480,mix960
echo TEMPERATUR-PRUEFSTAND FERTIG %TIME%
endlocal
