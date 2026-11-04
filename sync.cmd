@echo off
rem Pakete installieren/aktualisieren (Erststart oder nach Aenderungen an collector\pyproject.toml).
rem pc.cmd und tests.cmd synchronisieren NICHT selbst, damit laufende Trainings nicht gestoert werden.
rem Nur ausfuehren, wenn kein Training laeuft.
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
"%UV%" sync --project "%ROOT%collector"
endlocal
