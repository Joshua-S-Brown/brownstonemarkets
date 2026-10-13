@echo off
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Brownstone's Python environment is missing. See README.md for setup.
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0launch.py"
if errorlevel 1 pause
