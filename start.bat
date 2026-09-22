@echo off
REM AI Email Agent - Background Launcher
REM This script starts the agent completely in the background and closes the terminal.

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [SETUP] Preparing the AI Email Agent...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
    exit /b
)

echo Starting AI Email Agent and opening the dashboard...
wscript.exe "%~dp0Open_Dashboard.vbs"
exit
