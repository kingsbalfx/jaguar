$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "== ICT Trading Bot Windows Setup ==" -ForegroundColor Cyan

$pythonCmd = $null
$pythonArgs = @()

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pyLauncher) {
  $pythonCmd = $pyLauncher.Source
  $pythonArgs = @("-3.11")
} else {
  $pythonExe = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonExe) {
    $pythonCmd = $pythonExe.Source
  }
}

if (-not $pythonCmd) {
  Write-Host "Python not found. Please install Python 3.11 and re-run this script." -ForegroundColor Red
  exit 1
}

if (-not (Test-Path ".venv")) {
  Write-Host "Creating virtual environment..." -ForegroundColor Yellow
  & $pythonCmd @pythonArgs -m venv .venv
}

$venvPython = Join-Path $root ".venv\\Scripts\\python.exe"

Write-Host "Upgrading pip..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip

Write-Host "Installing dependencies..." -ForegroundColor Yellow
& $venvPython -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
  Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
  Copy-Item ".env.example" ".env"
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1) Edit .env and set SUPABASE_URL and SUPABASE_KEY."
Write-Host "2) Open MT5 on Windows and log in to your broker account."
Write-Host "3) Save MT5 credentials in the Admin panel (/admin/settings)."
Write-Host "4) Start the bot:"
Write-Host "   .\\.venv\\Scripts\\python.exe main.py"
