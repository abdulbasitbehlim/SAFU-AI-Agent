@echo off
setlocal
cd /d "%~dp0"
title SAFU Wake Repair

echo ========================================
echo       SAFU - Wake Engine Repair
echo ========================================
python --version
python -c "import sys; print('Python executable:', sys.executable); print('64-bit:', sys.maxsize ^> 2**32)"
echo.
echo Installing a compatible PREBUILT PocketSphinx wheel only...
python -c "import sys,subprocess; m=sys.version_info.minor; spec=('pocketsphinx==5.0.4' if 8^<=m^<=12 else ('pocketsphinx==5.1.1' if m==13 else '')); print('Selected:', spec or 'none'); raise SystemExit(subprocess.call([sys.executable,'-m','pip','install','--only-binary=:all:',spec]) if spec else 2)"
if errorlevel 1 (
  echo.
  echo [SAFU] A local wake wheel is unavailable for this Python build.
  echo [SAFU] This is NOT fatal. Safu can start and use cloud wake fallback.
  echo [SAFU] For fully local wake, use 64-bit CPython 3.11, 3.12, or 3.13.
) else (
  echo.
  echo [SAFU] Local Hey Safu engine repaired successfully.
)
pause
endlocal
