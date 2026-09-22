@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\check_agent_status.ps1"
pause
