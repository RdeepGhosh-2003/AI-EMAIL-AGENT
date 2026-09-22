@echo off
echo Stopping AI Email Agent...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*run.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo AI Email Agent stopped successfully.
pause
