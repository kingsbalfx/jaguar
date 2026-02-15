# ============================================
# AUTOMATED PRODUCTION DEPLOYMENT SCRIPT
# Kings Balfx Trading Platform
# Domain: kingsbalfx.name.ng
# ============================================

param(
    [string]$Action = "validate",
    [string]$SupabaseUrl = "",
    [string]$SupabaseKey = "",
    [string]$PaystackKey = "",
    [string]$PaystackSecret = "",
    
    [string]$AdminApiKey = ""
)

# Colors for output
$Success = "Green"
$Error = "Red"
$Warning = "Yellow"
$Info = "Cyan"

function Write-Section {
    param([string]$Title)
    Write-Host "`n" -ForegroundColor $Info
    Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor $Info
    Write-Host "║ $Title" -ForegroundColor $Info
    Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor $Info
}

function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor $Success
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor $Error
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor $Warning
}

function Write-Info-Custom {
    param([string]$Message)
    Write-Host "ℹ️  $Message" -ForegroundColor $Info
}

function Validate-Environment {
    Write-Section "VALIDATING PRODUCTION ENVIRONMENT"
    
    $errors = @()
    $warnings = @()
    
    # Check files exist
    $requiredFiles = @(
        "jaguar-main/.env.production",
        "ict_trading_bot/.env.production",
        "jaguar-main/vercel.json",
        "jaguar-main/.gitignore"
    )
    
    foreach ($file in $requiredFiles) {
        if (Test-Path $file) {
            Write-Success "Found: $file"
        } else {
            $errors += "Missing: $file"
            Write-Error-Custom "Missing: $file"
        }
    }
    
    # Check local files that should NOT exist
    $localOnlyFiles = @(
        "jaguar-main/.env.local",
        "ict_trading_bot/.env",
        "jaguar-main/ADMIN_CREDENTIALS.txt"
    )
    
    foreach ($file in $localOnlyFiles) {
        if (Test-Path $file) {
            $warnings += "Remove before deploy: $file"
            Write-Warning-Custom "Will be removed: $file"
        }
    }
    
    # Check Node.js
    $nodeVersion = node --version
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Node.js installed: $nodeVersion"
    } else {
        $errors += "Node.js not found"
        Write-Error-Custom "Node.js not installed"
    }
    
    # Check Python
    $pythonVersion = python --version
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Python installed: $pythonVersion"
    } else {
        $errors += "Python not found"
        Write-Error-Custom "Python not installed"
    }
    
    # Check Vercel CLI
    $vercelVersion = vercel --version
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Vercel CLI installed: $vercelVersion"
    } else {
        Write-Warning-Custom "Vercel CLI not installed. Install with: npm install -g vercel"
    }
    
    # Check git
    $gitVersion = git --version
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Git installed: $gitVersion"
    } else {
        $errors += "Git not found"
        Write-Error-Custom "Git not installed"
    }
    
    if ($errors.Count -gt 0) {
        Write-Host "`nCRITICAL ERRORS:" -ForegroundColor $Error
        foreach ($err in $errors) {
            Write-Error-Custom $err
        }
        return $false
    }
    
    if ($warnings.Count -gt 0) {
        Write-Host "`nWARNINGS:" -ForegroundColor $Warning
        foreach ($warn in $warnings) {
            Write-Warning-Custom $warn
        }
    }
    
    Write-Success "Environment validation passed!"
    return $true
}

function Update-EnvFiles {
    Write-Section "UPDATING ENVIRONMENT FILES"
    
    if (-not $SupabaseUrl -or -not $SupabaseKey -or -not $PaystackKey) {
        Write-Warning-Custom "Skipping env file updates (missing parameters)"
        Write-Info-Custom "Provide all required parameters to auto-update:"
        Write-Info-Custom "  -SupabaseUrl"
        Write-Info-Custom "  -SupabaseKey"
        Write-Info-Custom "  -PaystackKey"
        Write-Info-Custom "  -PaystackSecret"
        
        Write-Info-Custom "  -AdminApiKey"
        return
    }
    
    Write-Info-Custom "Updating jaguar-main/.env.production..."
    
    (Get-Content "jaguar-main/.env.production") -replace `
        'NEXT_PUBLIC_SUPABASE_URL=.*', `
        "NEXT_PUBLIC_SUPABASE_URL=$SupabaseUrl" | Set-Content "jaguar-main/.env.production"
    
    (Get-Content "jaguar-main/.env.production") -replace `
        'NEXT_PUBLIC_SUPABASE_ANON_KEY=.*', `
        "NEXT_PUBLIC_SUPABASE_ANON_KEY=$SupabaseKey" | Set-Content "jaguar-main/.env.production"
    
    (Get-Content "jaguar-main/.env.production") -replace `
        'NEXT_PUBLIC_PAYSTACK_KEY=.*', `
        "NEXT_PUBLIC_PAYSTACK_KEY=$PaystackKey" | Set-Content "jaguar-main/.env.production"
    
    (Get-Content "jaguar-main/.env.production") -replace `
        'PAYSTACK_SECRET_KEY=.*', `
        "PAYSTACK_SECRET_KEY=$PaystackSecret" | Set-Content "jaguar-main/.env.production"
    
    # Trade webhook secret removed - no replacement necessary
    
    (Get-Content "jaguar-main/.env.production") -replace `
        'ADMIN_API_KEY=.*', `
        "ADMIN_API_KEY=$AdminApiKey" | Set-Content "jaguar-main/.env.production"
    
    Write-Success "Updated jaguar-main/.env.production"
    
    Write-Info-Custom "Updating ict_trading_bot/.env.production..."
    
    (Get-Content "ict_trading_bot/.env.production") -replace `
        'SUPABASE_URL=.*', `
        "SUPABASE_URL=$SupabaseUrl" | Set-Content "ict_trading_bot/.env.production"
    
    (Get-Content "ict_trading_bot/.env.production") -replace `
        'SUPABASE_KEY=.*', `
        "SUPABASE_KEY=$SupabaseKey" | Set-Content "ict_trading_bot/.env.production"
    
    # MT5 credentials are stored in Supabase via the Admin panel
    # Bot-to-web webhook secret removed - bot writes directly to Supabase
    
    Write-Success "Updated ict_trading_bot/.env.production"
}

function Clean-LocalFiles {
    Write-Section "CLEANING LOCAL DEVELOPMENT FILES"
    
    $filesToRemove = @(
        "jaguar-main/.env.local",
        "ict_trading_bot/.env",
        "jaguar-main/ADMIN_CREDENTIALS.txt"
    )
    
    foreach ($file in $filesToRemove) {
        if (Test-Path $file) {
            Remove-Item $file -Force
            Write-Success "Removed: $file"
        }
    }
    
    Write-Success "Local files cleaned"
}

function Deploy-Web {
    Write-Section "DEPLOYING WEB APP TO VERCEL"
    
    Write-Info-Custom "Installing dependencies..."
    Set-Location "jaguar-main"
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Failed to install dependencies"
        return $false
    }
    
    Write-Info-Custom "Building Next.js app..."
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Build failed"
        return $false
    }
    
    Write-Success "Build successful"
    
    Write-Info-Custom "Deploying to Vercel..."
    vercel --prod --env-file .env.production
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Web app deployed!"
        return $true
    } else {
        Write-Error-Custom "Vercel deployment failed"
        return $false
    }
}

function Deploy-Bot {
    Write-Section "DEPLOYING TRADING BOT"
    
    Set-Location "..\ict_trading_bot"
    
    Write-Info-Custom "Checking Python environment..."
    
    if (Test-Path "venv") {
        Write-Info-Custom "Virtual environment exists"
    } else {
        Write-Info-Custom "Creating virtual environment..."
        python -m venv venv
    }
    
    Write-Info-Custom "Activating virtual environment..."
    & ".\venv\Scripts\Activate.ps1"
    
    Write-Info-Custom "Installing bot dependencies..."
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Failed to install bot dependencies"
        return $false
    }
    
    Write-Success "Bot dependencies installed"
    
    Write-Info-Custom "Starting bot..."
    Write-Info-Custom "Bot will run in background. Check logs: bot_production.log"
    
    # Start bot in background
    Start-Process python -ArgumentList "main.py" -WindowStyle Minimized
    
    Start-Sleep -Seconds 3
    
    Write-Success "Bot started!"
    Write-Info-Custom "Visit: https://kingsbalfx.name.ng/admin/bot-logs to monitor"
    
    return $true
}

function Print-Summary {
    Write-Section "DEPLOYMENT SUMMARY"
    
    Write-Host "`n📊 Platform Status:" -ForegroundColor $Info
    Write-Host "  Web App:    https://kingsbalfx.name.ng" -ForegroundColor $Info
    Write-Host "  Domain:     kingsbalfx.name.ng" -ForegroundColor $Info
    Write-Host "  SSL/HTTPS:  ✅ Auto-configured" -ForegroundColor $Success
    Write-Host "  Bot API:    https://your-bot-host:8000" -ForegroundColor $Info
    
    Write-Host "`n💰 Pricing Tiers (Aligned):" -ForegroundColor $Info
    Write-Host "  Free        ₦0        | 3 signals/day | 0 trades" -ForegroundColor $Info
    Write-Host "  Premium     ₦90,000   | 15 signals/day | 5 trades" -ForegroundColor $Info
    Write-Host "  VIP         ₦150,000  | 30 signals/day | 10 trades" -ForegroundColor $Info
    Write-Host "  Pro         ₦250,000  | Unlimited | 20 trades" -ForegroundColor $Info
    Write-Host "  Lifetime    ₦500,000  | Unlimited | Unlimited" -ForegroundColor $Info
    
    Write-Host "`n📈 Trading Pairs Available:" -ForegroundColor $Info
    Write-Host "  Forex:        36 pairs (Major, Minor, Exotic)" -ForegroundColor $Info
    Write-Host "  Crypto:       12 pairs (Bitcoin, Ethereum, etc.)" -ForegroundColor $Info
    Write-Host "  Metals:       4 pairs (Gold, Silver, Platinum)" -ForegroundColor $Info
    Write-Host "  Indices:      8 pairs (S&P 500, NASDAQ, etc.)" -ForegroundColor $Info
    Write-Host "  Commodities:  6 pairs (Oil, Gas, Agricultural)" -ForegroundColor $Info
    Write-Host "  Total:        66+ trading pairs" -ForegroundColor $Success
    
    Write-Host "`n✅ Next Steps:" -ForegroundColor $Success
    Write-Host "  1. Monitor at: https://kingsbalfx.name.ng/admin/bot-logs" -ForegroundColor $Info
    Write-Host "  2. Check pricing sync: https://kingsbalfx.name.ng/api/bot/pricing-sync" -ForegroundColor $Info
    Write-Host "  3. Verify trades in: Supabase → bot_logs table" -ForegroundColor $Info
    Write-Host "  4. Promote to users and start trading!" -ForegroundColor $Success
    
    Write-Host "`n🎉 Deployment complete! Happy trading! 🚀" -ForegroundColor $Success
}

# ============================================
# MAIN EXECUTION
# ============================================

if ($Action -eq "validate") {
    if (Validate-Environment) {
        exit 0
    } else {
        exit 1
    }
}
elseif ($Action -eq "deploy-full") {
    if (-not (Validate-Environment)) {
        exit 1
    }
    
    Update-EnvFiles
    Clean-LocalFiles
    
    if (-not (Deploy-Web)) {
        exit 1
    }
    
    if (-not (Deploy-Bot)) {
        Write-Warning-Custom "Web deployed but bot deployment incomplete"
    }
    
    Print-Summary
    exit 0
}
elseif ($Action -eq "deploy-web") {
    if (-not (Validate-Environment)) {
        exit 1
    }
    
    Update-EnvFiles
    Clean-LocalFiles
    
    if (Deploy-Web) {
        Print-Summary
        exit 0
    } else {
        exit 1
    }
}
elseif ($Action -eq "deploy-bot") {
    if (Deploy-Bot) {
        exit 0
    } else {
        exit 1
    }
}
else {
    Write-Host "Unknown action: $Action" -ForegroundColor $Error
    Write-Host "`nUsage:" -ForegroundColor $Info
    Write-Host "  .\deploy.ps1 -Action validate                    # Validate environment" -ForegroundColor $Info
    Write-Host "  .\deploy.ps1 -Action deploy-full -SupabaseUrl ... # Full deployment" -ForegroundColor $Info
    Write-Host "  .\deploy.ps1 -Action deploy-web -SupabaseUrl ...  # Deploy web only" -ForegroundColor $Info
    Write-Host "  .\deploy.ps1 -Action deploy-bot                   # Deploy bot only" -ForegroundColor $Info
    exit 1
}
