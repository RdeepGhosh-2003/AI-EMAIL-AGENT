param(
    [int]$Lines = 80
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogFile = Join-Path $ProjectRoot "logs\activity.jsonl"

if (-not (Test-Path -LiteralPath $LogFile)) {
    Write-Host "No activity log found yet at $LogFile"
    exit 0
}

Get-Content -LiteralPath $LogFile -Tail $Lines
