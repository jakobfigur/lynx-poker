@echo off
rem Startet Lynx / Poker Collector. Beispiel: pc.cmd calibrate collector\testdata\pokerth_preflop_hand1.png
rem Erststart auf einem neuen Rechner: sync.cmd (legt die Python-Umgebung an).
setlocal
set "ROOT=%~dp0"
set "PYTHONIOENCODING=utf-8"
rem Portabel: tools\uv\uv.exe mit Python und Paket-Cache unter tools\ (USB-Stick). Sonst ein installiertes uv
rem (https://docs.astral.sh/uv/), das Python und Pakete selbst verwaltet.
set "UV=uv"
if exist "%ROOT%tools\uv\uv.exe" (
  set "UV=%ROOT%tools\uv\uv.exe"
  set "UV_PYTHON_INSTALL_DIR=%ROOT%tools\python"
  set "UV_CACHE_DIR=%ROOT%tools\uv-cache"
  set "UV_LINK_MODE=copy"
  set "UV_PYTHON_PREFERENCE=only-managed"
)
rem --no-sync: Pakete nicht bei jedem Start pruefen (stoert laufende Trainings); Pakete aendern: sync.cmd
"%UV%" run --quiet --no-sync --project "%ROOT%collector" pokercollector %*
endlocal
