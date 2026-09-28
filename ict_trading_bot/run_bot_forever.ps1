<#
.SYNOPSIS
    Keeps the KINGSBALFX MT5 bot running.

.DESCRIPTION
    Starts `python main.py` and restarts it whenever the process exits, logging
    every run to `logs\bot_<timestamp>.log` and every restart to
    `logs\bot_supervisor.log`.

    The bot used to be started once by the Windows scheduled task, so a crash
    (or a closed terminal) silently stopped signal delivery until somebody
    noticed. Run this script instead — it also makes the real reason visible in
    the admin panel through the bot's `bot_started` / `bot_heartbeat` log events.

.PARAMETER RestartDelaySeconds
    Initial delay between restarts (doubles up to -MaxRestartDelaySeconds when the
    bot keeps dying immediately).

.PARAMETER MaxRestartDelaySeconds
    Upper bound for the backoff delay.

.PARAMETER Once
    Run the bot a single time and exit (no supervision).

.EXAMPLE
    .\run_bot_forever.ps1
#>
param(
    [int]$RestartDelaySeconds = 15,
    [int]$MaxRestartDelaySeconds = 300,
    [switch]$Once
)

$ErrorActionPreference = "Continue"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Virtualenv python not found at $python - falling back to 'python' on PATH." -ForegroundColor Yellow
    $python = "python"
}

$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$supervisorLog = Join-Path $logDir "bot_supervisor.log"
$stopFlag = Join-Path $root "STOP_BOT.flag"

if (Test-Path $stopFlag) {
    Write-Host "Stop flag found ($stopFlag). Remove it to start the bot." -ForegroundColor Yellow
}

$delay = $RestartDelaySeconds
$failures = 0

while ($true) {
    if (Test-Path $stopFlag) {
        Write-Host "[supervisor] stop flag present - exiting without restarting." -ForegroundColor Yellow
        break
    }

    $stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
    $runLog = Join-Path $logDir "bot_$stamp.log"
    Write-Host "[supervisor] starting bot at $stamp (console log: $runLog)" -ForegroundColor Cyan

    $startedAt = Get-Date
    & $python main.py *> $runLog
    $exitCode = $LASTEXITCODE
    $ranFor = [int]((Get-Date) - $startedAt).TotalSeconds

    Write-Host "[supervisor] bot exited after ${ranFor}s with code $exitCode" -ForegroundColor Yellow
    Add-Content -Path $supervisorLog -Value "$(Get-Date -Format o) exit=$exitCode uptime_seconds=$ranFor"

    if ($Once) { break }

    if ($ranFor -lt 60) { $failures += 1 } else { $failures = 0 }
    $backoff = [Math]::Pow(2, [Math]::Min($failures, 4))
    $delay = [Math]::Min($MaxRestartDelaySeconds, [int]($RestartDelaySeconds * [Math]::Max(1, $backoff)))

    Write-Host "[supervisor] restarting in $delay seconds (consecutive fast failures: $failures)" -ForegroundColor Cyan
    Start-Sleep -Seconds $delay
}
