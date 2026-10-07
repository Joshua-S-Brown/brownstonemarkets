@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0drop-scans.ps1"
set "drop_exit=%errorlevel%"
pause
exit /b %drop_exit%
