@echo off
setlocal
cd /d "%~dp0"
title SAFU Verification
python verify_safu.py --strict
if errorlevel 1 (
  echo.
  echo [SAFU] Strict verification found a problem.
  echo [SAFU] If dependencies are missing, run: python setup.py
)
pause
endlocal
