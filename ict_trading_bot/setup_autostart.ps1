$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$taskName = "KingsbalMT5Bot"
$pythonPath = Join-Path $root ".venv\\Scripts\\python.exe"
$scriptPath = Join-Path $root "main.py"

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
$trigger = New-ScheduledTaskTrigger -AtLogOn

# Run with highest privileges for stability (no password required for current user on logon)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null

Write-Host "Autostart task created: $taskName" -ForegroundColor Green
Write-Host "It will run at user logon. To remove:" -ForegroundColor Cyan
Write-Host "  Unregister-ScheduledTask -TaskName $taskName -Confirm:\$false"
