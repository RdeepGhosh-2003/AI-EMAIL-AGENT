@echo off
REM AI Email Agent - Background Launcher
REM This script starts the agent completely in the background and closes the terminal.

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment...
    python -m venv "%~dp0.venv"
    echo [SETUP] Installing dependencies...
    "%~dp0.venv\Scripts\pip" install -r "%~dp0requirements.txt" --quiet
)

echo Starting AI Email Agent and opening the dashboard...
wscript.exe "%~dp0Open_Dashboard.vbs"
exit
