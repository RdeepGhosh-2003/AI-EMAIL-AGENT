$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$logPath = Join-Path $projectRoot 'setup.log'

function Write-Step([string]$message) {
    Write-Host "`n[AI Email Agent] $message" -ForegroundColor Cyan
    Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format s) $message"
}

function Find-Python {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    foreach ($command in @('py.exe', 'python.exe')) {
        try {
            $path = (Get-Command $command -ErrorAction Stop).Source
            & $path --version *> $null
            if ($LASTEXITCODE -eq 0) { return $path }
        } catch { }
    }
    return $null
}

try {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        $python = Find-Python
        if (-not $python) {
            Write-Step 'Python was not found. Downloading the official per-user installer...'
            $installer = Join-Path $env:TEMP 'ai-email-agent-python-installer.exe'
            $download = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'
            Invoke-WebRequest -UseBasicParsing -Uri $download -OutFile $installer
            Write-Step 'Installing Python for this Windows user...'
            $process = Start-Process -FilePath $installer -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0 SimpleInstall=1' -Wait -PassThru
            if ($process.ExitCode -ne 0) { throw "Python installer failed with code $($process.ExitCode)." }
            Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
            $python = Find-Python
            if (-not $python) { throw 'Python installed, but could not be located. Restart Windows and run setup again.' }
        }

        Write-Step 'Creating the private application environment...'
        if ((Split-Path $python -Leaf) -ieq 'py.exe') {
            & $python -3 -m venv (Join-Path $projectRoot '.venv')
        } else {
            & $python -m venv (Join-Path $projectRoot '.venv')
        }
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the application environment.' }
    }

    Write-Step 'Installing the AI Email Agent components...'
    & $venvPython -m pip install --disable-pip-version-check --quiet --upgrade pip
    & $venvPython -m pip install --disable-pip-version-check --quiet -r (Join-Path $projectRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'A required component could not be installed. Check the internet connection.' }

    Write-Step 'Setup complete. Opening the dashboard...'
    Start-Process -FilePath 'wscript.exe' -ArgumentList ('"' + (Join-Path $projectRoot 'Open_Dashboard.vbs') + '"')
    exit 0
} catch {
    $message = $_.Exception.Message
    Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format s) ERROR $message"
    Write-Host "`nSetup could not finish: $message" -ForegroundColor Red
    Write-Host "Details were saved to $logPath"
    Read-Host 'Press Enter to close'
    exit 1
}
