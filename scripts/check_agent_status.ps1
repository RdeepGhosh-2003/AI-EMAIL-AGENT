param(
    [int]$Port = 5001,
    [string]$TaskName = "AI Email Agent"
)

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "Task: $($task.TaskName)"
    Write-Host "State: $($task.State)"
    Write-Host "Last run: $($taskInfo.LastRunTime)"
    Write-Host "Last result: $($taskInfo.LastTaskResult)"
} else {
    Write-Host "Task not installed: $TaskName"
}

try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/api/auth/status" -TimeoutSec 5
    Write-Host "Dashboard health: HTTP $($response.StatusCode)"
    Write-Host $response.Content
} catch {
    Write-Host "Dashboard health: not reachable on port $Port"
}
