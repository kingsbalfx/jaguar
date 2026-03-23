$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$taskName = "KingsbalMT5Bot"
$pythonPath = Join-Path $root ".venv\\Scripts\\python.exe"
$scriptPath = Join-Path $root "main.py"
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (-not (Test-Path $pythonPath)) {
  Write-Host "Virtualenv not found at $pythonPath" -ForegroundColor Red
  Write-Host "Run .\\setup_windows.ps1 first." -ForegroundColor Yellow
  exit 1
}

if (-not (Test-Path $scriptPath)) {
  Write-Host "main.py not found at $scriptPath" -ForegroundColor Red
  exit 1
}

$action = New-ScheduledTaskAction -Execute $pythonPath -Argument $scriptPath -WorkingDirectory $root
$triggers = @(
  New-ScheduledTaskTrigger -AtLogOn -User $currentUser
  New-ScheduledTaskTrigger -AtStartup
)

# Run with highest privileges for stability.
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -RunLevel Highest -LogonType Interactive

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

$task = New-ScheduledTask -Action $action -Trigger $triggers -Principal $principal -Settings $settings

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Write-Host "Autostart task created: $taskName" -ForegroundColor Green
Write-Host "It will run at startup and at user logon." -ForegroundColor Cyan
Write-Host "The task was started now for a live test." -ForegroundColor Cyan
Write-Host "To inspect it:" -ForegroundColor Cyan
Write-Host "  Get-ScheduledTask -TaskName $taskName | Get-ScheduledTaskInfo"
Write-Host "To start it manually:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName $taskName"
Write-Host "To stop the running Python process, use Task Manager or:" -ForegroundColor Cyan
Write-Host "  Get-Process python | Stop-Process"
Write-Host "To remove:" -ForegroundColor Cyan
Write-Host "  Unregister-ScheduledTask -TaskName $taskName -Confirm:\$false"
