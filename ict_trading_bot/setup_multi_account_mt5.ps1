$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $root ".env"

if (-not (Test-Path $envFile)) {
    throw ".env not found at $envFile"
}

function Get-EnvMap {
    param([string]$Path)
    $map = [ordered]@{}
    $lines = Get-Content $Path
    foreach ($line in $lines) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line.TrimStart().StartsWith("#")) { continue }
        $parts = $line -split "=", 2
        if ($parts.Count -eq 2) {
            $map[$parts[0].Trim()] = $parts[1]
        }
    }
    return $map
}

function Set-OrAddEnvLine {
    param(
        [string[]]$Lines,
        [string]$Key,
        [string]$Value
    )
    $updated = $false
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i].StartsWith("$Key=")) {
            $Lines[$i] = "$Key=$Value"
            $updated = $true
            break
        }
    }
    if (-not $updated) {
        $Lines += "$Key=$Value"
    }
    return $Lines
}

function Copy-Mt5Portable {
    param(
        [string]$SourceDir,
        [string]$DestinationDir
    )

    New-Item -ItemType Directory -Force -Path $DestinationDir | Out-Null

    $robocopy = Get-Command robocopy.exe -ErrorAction SilentlyContinue
    if ($robocopy) {
        $excludeDirs = @("Bases", "logs", "temp", "Tester")
        $args = @(
            $SourceDir,
            $DestinationDir,
            "/E",
            "/R:2",
            "/W:2",
            "/NFL",
            "/NDL",
            "/NJH",
            "/NJS",
            "/NP",
            "/XD"
        ) + $excludeDirs

        & $robocopy.Source @args | Out-Null
        $code = $LASTEXITCODE
        if ($code -ge 8) {
            throw "robocopy failed with exit code $code while copying MT5 files to $DestinationDir"
        }
        return
    }

    Copy-Item -Path (Join-Path $SourceDir "*") -Destination $DestinationDir -Recurse -Force
}

function Reset-Mt5AccountState {
    param([string]$AccountDir)

    $configDir = Join-Path $AccountDir "Config"
    if (-not (Test-Path $configDir)) {
        return
    }

    $stateFiles = @(
        (Join-Path $configDir "accounts.dat"),
        (Join-Path $configDir "terminal.ini")
    )

    foreach ($file in $stateFiles) {
        if (Test-Path $file) {
            Remove-Item -Path $file -Force
        }
    }
}

$envMap = Get-EnvMap -Path $envFile
$sourceTerminal = $envMap["MT5_PATH"]
if (-not $sourceTerminal) {
    $sourceTerminal = "C:\Program Files\MetaTrader 5\terminal64.exe"
}

if (-not (Test-Path $sourceTerminal)) {
    throw "MT5 source terminal not found: $sourceTerminal"
}

$sourceDir = Split-Path -Parent $sourceTerminal
$baseDir = Join-Path $env:USERPROFILE "MT5_Multi"
New-Item -ItemType Directory -Force -Path $baseDir | Out-Null

$envLines = Get-Content $envFile
$envLines = Set-OrAddEnvLine -Lines $envLines -Key "MT5_PORTABLE" -Value "true"
$envLines = Set-OrAddEnvLine -Lines $envLines -Key "MULTI_ACCOUNT_ALLOW_SHARED_TERMINAL" -Value "false"

$accountIndex = 1
$createdPaths = @()
while ($true) {
    $enabledKey = "ACCOUNT_${accountIndex}_ENABLED"
    $loginKey = "ACCOUNT_${accountIndex}_LOGIN"
    $enabled = ($envMap[$enabledKey] -as [string])
    $login = ($envMap[$loginKey] -as [string])

    if (-not $enabled -and -not $login) {
        break
    }

    if ($enabled -and $enabled.ToLower() -eq "true" -and $login) {
        $accountDir = Join-Path $baseDir "Account_$login"
        if (-not (Test-Path $accountDir)) {
            Write-Host "Creating MT5 portable copy for account $login ..." -ForegroundColor Yellow
            Copy-Mt5Portable -SourceDir $sourceDir -DestinationDir $accountDir
        } else {
            Write-Host "MT5 portable copy already exists for account $login." -ForegroundColor DarkYellow
        }

        Reset-Mt5AccountState -AccountDir $accountDir

        $accountTerminal = Join-Path $accountDir "terminal64.exe"
        if (-not (Test-Path $accountTerminal)) {
            throw "Expected terminal64.exe not found in $accountDir"
        }

        $pathKey = "ACCOUNT_${accountIndex}_MT5_PATH"
        $envLines = Set-OrAddEnvLine -Lines $envLines -Key $pathKey -Value $accountTerminal
        $createdPaths += "${pathKey}=$accountTerminal"
    }

    $accountIndex += 1
}

$backupFile = Join-Path $root ".env.multi_account.backup"
Copy-Item $envFile $backupFile -Force
Set-Content -Path $envFile -Value $envLines -Encoding UTF8

Write-Host ""
Write-Host "Multi-account MT5 setup complete." -ForegroundColor Green
Write-Host "Updated .env with these account terminal paths:" -ForegroundColor Cyan
foreach ($item in $createdPaths) {
    Write-Host "  $item"
}
Write-Host ""
Write-Host "Backup saved to $backupFile" -ForegroundColor DarkGray
