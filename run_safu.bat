@echo off
setlocal
cd /d "%~dp0"
title SAFU Personal AI

REM Core first-run repair. PocketSphinx is OPTIONAL and is intentionally not
REM part of this import check; Safu can launch with its guarded cloud wake fallback.
python -c "import PyQt6, sounddevice, google.genai, numpy, psutil" >nul 2>&1
if errorlevel 1 (
  echo [SAFU] First-run core components are missing. Installing lightweight runtime...
  python setup.py
  if errorlevel 1 (
    echo.
    echo [SAFU] Core setup failed. Run: python --version
    echo [SAFU] Preferred for fully local wake: 64-bit CPython 3.11-3.13. Python 3.14+ uses cloud wake fallback.
    echo [SAFU] Then run: python setup.py
    pause
    exit /b 1
  )
)

REM v0.0.1 verifies Safu identity, multilingual input, English output, low-latency settings, and Qt construction. Run it once per fresh build
REM before launching the full assistant so stale signal/timer callbacks and other
REM GUI constructor errors are caught here instead of crashing after startup.
if not exist ".safu_verified_0_0_1" (
  echo [SAFU] Running first-launch verification...
  python verify_safu.py --strict
  if errorlevel 1 (
    echo.
    echo [SAFU] Verification failed. Please copy the FAIL lines when asking for help.
    pause
    exit /b 1
  )
  > ".safu_verified_0_0_1" echo verified
)

python main.py
if errorlevel 1 pause
endlocal
