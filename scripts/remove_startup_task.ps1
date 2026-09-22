param(
    [string]$TaskName = "AI Email Agent"
)

$ErrorActionPreference = "Stop"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed startup task: $TaskName"
} else {
    Write-Host "Startup task is not installed: $TaskName"
}
