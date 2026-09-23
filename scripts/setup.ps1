$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$logPath = Join-Path $projectRoot 'setup.log'
$envPath = Join-Path $projectRoot '.env'
$envExamplePath = Join-Path $projectRoot '.env.example'

function Write-Step([string]$message) {
    Write-Host "`n[AI Email Agent] $message" -ForegroundColor Cyan
    Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format s) $message"
}

function Initialize-EnvFile {
    if (Test-Path -LiteralPath $envPath) { return }
    if (Test-Path -LiteralPath $envExamplePath) {
        Copy-Item -LiteralPath $envExamplePath -Destination $envPath
    } else {
        @(
            'OPENROUTER_API_KEY='
            'OPENROUTER_APP_URL='
            'OPENAI_API_KEY='
            'GEMINI_API_KEY='
            'ANTHROPIC_API_KEY='
            'AZURE_CLIENT_ID='
            'AZURE_TENANT_ID='
            'ALLOWED_OUTLOOK_DOMAINS=durgabrgs.com'
            'DASHBOARD_PIN_SECURITY=false'
            'DASHBOARD_PIN_HASH='
            'DASHBOARD_COOKIE_SECURE=false'
            'DASHBOARD_ALLOWED_HOSTS='
        ) | Set-Content -LiteralPath $envPath -Encoding UTF8
    }
}

function Test-Python([string]$pythonPath, [string[]]$arguments) {
    try {
        $probe = & $pythonPath @arguments -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Find-Python {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe')
    )
    foreach ($candidate in $candidates) {
        if ((Test-Path -LiteralPath $candidate) -and (Test-Python $candidate @())) { return @{ Path = $candidate; Args = @() } }
    }
    try {
        $launcher = (Get-Command 'py.exe' -ErrorAction Stop).Source
        if (Test-Python $launcher @('-3')) { return @{ Path = $launcher; Args = @('-3') } }
    } catch { }
    foreach ($command in @('python.exe')) {
        try {
            $path = (Get-Command $command -ErrorAction Stop).Source
            if (Test-Python $path @()) { return @{ Path = $path; Args = @() } }
        } catch { }
    }
    return $null
}

try {
    Set-Content -LiteralPath $logPath -Value "$(Get-Date -Format s) Setup started"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Initialize-EnvFile

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
        & $python.Path @($python.Args + @('-m', 'venv', (Join-Path $projectRoot '.venv')))
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
