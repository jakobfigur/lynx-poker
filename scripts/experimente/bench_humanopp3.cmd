@echo off
rem 31.10. abends: Suche greedy / Turn-Netz gegen Menschen-Bot (bench_humanopp3.py), 8 Prozesse, Ausgabe data\bench\humanopp3.txt
setlocal
if "%~1"=="" (
  call "%~f0" protokoll > "<Projektordner>\data\bench\humanopp3.txt" 2>&1
  exit /b
)
set "ROOT=<Projektordner>\"
set "UV_PYTHON_INSTALL_DIR=%ROOT%tools\python"
set "UV_CACHE_DIR=%ROOT%tools\uv-cache"
set "UV_LINK_MODE=copy"
set "UV_PYTHON_PREFERENCE=only-managed"
set "PYTHONIOENCODING=utf-8"
set "OMP_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
cd /d "%ROOT%collector"
"%ROOT%tools\uv\uv.exe" run --quiet --no-sync python "%ROOT%bench_humanopp3.py" 8
endlocal
