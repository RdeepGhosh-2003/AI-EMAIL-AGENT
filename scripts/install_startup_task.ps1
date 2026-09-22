param(
    [string]$TaskName = "AI Email Agent"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RunPy = Join-Path $ProjectRoot "run.py"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Virtual environment not found at $PythonExe. Run start.bat once to create it."
}

if (-not (Test-Path -LiteralPath $RunPy)) {
    throw "run.py not found at $RunPy"
}

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "-u run.py" -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Runs the AI Email Agent while this Windows desktop user is logged in." `
    -Force | Out-Null

Write-Host "Installed startup task: $TaskName"
Write-Host "The agent will run when this Windows user logs in and the desktop is awake/online."
