@echo off
echo Installing AI Email Agent startup task...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_startup_task.ps1"
pause
