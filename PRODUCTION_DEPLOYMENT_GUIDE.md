# 🚀 COMPLETE PRODUCTION DEPLOYMENT GUIDE
# Kings Balfx Trading Platform - kingsbalfx.name.ng
# Updated: Feb 13, 2026

## 📋 PRE-DEPLOYMENT CHECKLIST

### 1️⃣ Environment Configuration Files
```
Required Files (with production credentials):
✓ jaguar-main/.env.production         → Web app production secrets
✓ ict_trading_bot/.env.production    → Bot production secrets
✓ jaguar-main/vercel.json            → Vercel deployment config
✓ jaguar-main/.gitignore             → Prevent accidental commits
```

### 2️⃣ Production Credentials Required
Before deploying, gather:
```
SUPABASE:
  ✓ Production SUPABASE_URL           (https://xxxxx.supabase.co)
  ✓ Production SUPABASE_ANON_KEY      (eyJ...)
  ✓ Production SERVICE_ROLE_KEY       (eyJ...)

PAYSTACK (LIVE MODE - NOT TEST):
  ✓ Live Public Key                   (pk_live_...)
  ✓ Live Secret Key                   (sk_live_...)
  ✓ Webhook Secret                    (your_secure_secret)

MT5 ACCOUNT:
  ✓ Set in Admin panel (stored in Supabase)

API KEYS (Generate strong random strings):
  ✓ ADMIN_API_KEY                     (32+ chars, random)
```

### 3️⃣ Domain & DNS
```
✓ Domain purchased: kingsbalfx.name.ng
✓ DNS configured at registrar
✓ Vercel nameservers set
✓ SSL certificate ready (auto-issued by Vercel)
```

### 4️⃣ Remove All Local/Test Files
```powershell
# Delete before deploying:
Remove-Item jaguar-main/.env.local -Force
Remove-Item ict_trading_bot/.env -Force
Remove-Item jaguar-main/ADMIN_CREDENTIALS.txt -Force
Remove-Item jaguar-main/.vercel/ -Force -Recurse
```

---

## 🔧 DEPLOYMENT STEPS

### Step 1: Fill Environment Files

#### Create jaguar-main/.env.production
```bash
# Copy template and fill with YOUR production credentials
cat > jaguar-main/.env.production << 'EOF'
NODE_ENV=production
PORT=3000
NEXT_PUBLIC_DOMAIN=https://kingsbalfx.name.ng
VERCEL_URL=kingsbalfx.name.ng

# SUPABASE - Get from supabase.com dashboard
NEXT_PUBLIC_SUPABASE_URL=https://your_project_id.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# PAYSTACK - Use LIVE keys
NEXT_PUBLIC_PAYSTACK_KEY=pk_live_xxxxxxxxxxxxx
PAYSTACK_SECRET_KEY=sk_live_xxxxxxxxxxxxx
PAYSTACK_WEBHOOK_SECRET=your_webhook_secret

# TRADING BOT
BOT_API_URL=https://kingsbalfx.name.ng/api/bot
# Note: The trading bot now persists signals to Supabase.

# ADMIN
ADMIN_API_KEY=your_secure_random_admin_key_32_chars_min

# PRICING
PRICING_PREMIUM_PRICE_NGN=90000
PRICING_VIP_PRICE_NGN=150000
PRICING_PRO_PRICE_NGN=250000
PRICING_LIFETIME_PRICE_NGN=500000
EOF
```

#### Create ict_trading_bot/.env.production
```bash
cat > ict_trading_bot/.env.production << 'EOF'
ENVIRONMENT=production
DEBUG=false

# MT5 credentials are stored in Supabase via the Admin panel

# Supabase
SUPABASE_URL=https://your_project_id.supabase.co
SUPABASE_KEY=your_service_role_key_here

# Notes: The trading bot now writes signals directly to Supabase.
# Ensure `SUPABASE_URL` and `SUPABASE_KEY` (service role) are set for server-side inserts.

# Bot API
BOT_API_PORT=8000
BOT_API_HOST=0.0.0.0
EOF
```

### Step 2: Deploy to Vercel

#### Option A: Using Vercel CLI (Recommended)
```powershell
# Install Vercel CLI globally
npm install -g vercel

# Login to Vercel
vercel login

# Navigate to web app
cd jaguar-main

# Deploy to production
vercel --prod --env-file .env.production

# Vercel will:
# ✓ Build Next.js app
# ✓ Load environment variables
# ✓ Deploy to kingsbalfx.name.ng
# ✓ Set up SSL certificate
# ✓ Configure CDN & edge caching
```

#### Option B: GitHub Integration
```bash
# 1. Push to GitHub
git add .
git commit -m "Production deployment setup"
git push origin main

# 2. Connect GitHub to Vercel
#    - Go to vercel.com/dashboard
#    - Add project
#    - Select GitHub repository
#    - Vercel auto-deploys on push

# 3. Set environment variables in Vercel UI
#    - Dashboard → Settings → Environment Variables
#    - Add each .env.production variable
```

#### Option C: Vercel Dashboard
```
1. Go to: https://vercel.com
2. Sign in with account
3. New Project → Import Git Repository
4. Select: kingsbal/jaguar-main
5. Settings → Environment Variables
6. Paste all from .env.production
7. Click "Deploy"
```

### Step 3: Configure Custom Domain

```
1. In Vercel Dashboard:
   - Project Settings → Domains
   - Add: kingsbalfx.name.ng

2. Update DNS at registrar:
   - Remove old nameservers
   - Add Vercel nameservers shown in Vercel UI
   - Wait 24-48 hours for propagation

3. Verify:
   - Visit: https://kingsbalfx.name.ng
   - Should show your app
   - SSL certificate active (green lock)
```

### Step 4: Deploy Trading Bot

#### Option 1: Deploy on Dedicated Server
```bash
# SSH into your server
ssh user@your_server_ip

# Clone project
git clone https://github.com/your_repo/kingsbal.git
cd kingsbal/ict_trading_bot

# Set up Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\Activate

# Install bot dependencies
pip install -r requirements.txt

# Copy production env file
cp .env.production .env

# Run bot
python main.py

# Bot will:
# ✓ Connect to MT5
# ✓ Load trading pairs (forex, crypto, metals)
# ✓ Persist signals directly to Supabase `bot_signals` and logs to `bot_logs`
# ✓ Log activity to Supabase
# ✓ Run API server on configured host/port
```

#### Option 2: Run Locally (Testing)
```powershell
# In ict_trading_bot folder
cd ict_trading_bot

# Ensure .env.production is set
$env:ENVIRONMENT = "production"

# Run bot
python main.py

# Keep terminal open - bot will run continuously
# Logs appear in console and bot_production.log
```

#### Option 3: Deploy with Docker (Production)
```bash
# Build and run bot in Docker
docker build -t kingsbalfx-bot .

# Run container
docker run -d \
  --name kingsbalfx-bot \
  --env-file ict_trading_bot/.env.production \
  kingsbalfx-bot

# Check logs
docker logs -f kingsbalfx-bot
```

---

## ✅ POST-DEPLOYMENT VERIFICATION

### 1️⃣ Web App Health Checks
```powershell
# Check web app is running
curl https://kingsbalfx.name.ng/health
# Response: {"status":"ok","ts":1707...}

# Check web app responds to API
curl https://kingsbalfx.name.ng/api/admin/status `
  -H "Authorization: Bearer $env:ADMIN_API_KEY"
# Response: {"status":"ok","admin":true}

# Check Supabase connection
curl https://kingsbalfx.name.ng/api/get-role `
  -H "Content-Type: application/json"
# Response: {"role":"user"} or {"role":"admin"}
```

### 2️⃣ Bot Health Checks
```powershell
# Check bot API is running
curl https://your-bot-host:8000/health
# Response: {"status":"ok","running":true}

# Check bot status
curl https://your-bot-host:8000/status
# Response: {"trading":true,"symbols":["EURUSD",...]}
```

### 3️⃣ Pricing Sync Verification
```powershell
# Check pricing config
curl https://kingsbalfx.name.ng/api/bot/pricing-sync
# Response: {"status":"ok","tiers":[...]}

# Update user tier pricing (premium user)
curl -X POST https://kingsbalfx.name.ng/api/bot/pricing-sync `
  -H "Content-Type: application/json" `
  -H "x-admin-api-key: $env:ADMIN_API_KEY" `
  -Body '{"userId":"user-uuid","tier":"premium"}'
# Response: {"status":"ok","tier":"premium",...}
```

### 4️⃣ Database Verification
```sql
-- Connect to Supabase dashboard
-- Run these queries:

-- Check users
SELECT COUNT(*) FROM profiles;
-- Should show your users

-- Check payments
SELECT COUNT(*) FROM payments;
-- Should show payment history

-- Check bot logs
SELECT event, COUNT(*) FROM bot_logs GROUP BY event;
-- Should show: trade_opened, trade_closed, signal_generated, etc.

-- Check subscriptions
SELECT plan, COUNT(*) FROM subscriptions GROUP BY plan;
-- Should show active subscriptions
```

---

## 🔒 SECURITY CHECKLIST

### Vercel Security
```
✓ HTTPS/SSL enabled        (Automatic)
✓ Security headers set     (vercel.json)
✓ Rate limiting enabled    (.env.production)
✓ Admin API key protected  (32+ char random)
✓ Paystack webhook signature verified (HMAC-SHA256)
```

### Supabase Security
```
✓ Row-Level Security (RLS) enabled
✓ Service role key protected
✓ Anon key has limited permissions
✓ Auth policies configured
✓ Backups configured
✓ Point-in-time recovery enabled
```

### Bot Security
```
✓ MT5 credentials secure   (Stored in Supabase)
✓ API key authentication
✓ Rate limiting per IP
✓ Logs don't contain secrets
```

### Credentials Management
```
✓ No .env files in git
✓ .gitignore prevents commits
✓ Vercel stores secrets safely
✓ ADMIN_CREDENTIALS.txt removed
✓ Test keys removed
```

---

## 🐛 TROUBLESHOOTING

### Issue 1: "NEXT_PUBLIC_SUPABASE_URL is not set"
**Cause**: Environment variables not loaded  
**Solution**: 
```bash
# Verify .env.production exists
ls -la jaguar-main/.env.production

# Verify Vercel has env vars set
vercel env ls

# Redeploy with env file
vercel --prod --env-file jaguar-main/.env.production
```

### Issue 2: Paystack Webhook Not Received
**Cause**: Webhook URL or signature mismatch  
**Solution**:
```bash
# Verify webhook URL in Paystack dashboard
# Should be: https://kingsbalfx.name.ng/api/paystack/webhook

# Check Paystack webhook secret matches
# Paystack: PAYSTACK_WEBHOOK_SECRET
# Code: process.env.PAYSTACK_WEBHOOK_SECRET

# Test webhook:
curl -X POST https://kingsbalfx.name.ng/api/paystack/webhook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk_live_..." \
  -d '{"event":"charge.success",...}'
```

### Issue 3: Bot Not Connecting to MT5
**Cause**: Wrong credentials or server offline  
**Solution**:
```bash
# Update MT5 credentials in the Admin panel
# Restart the bot to reload credentials
# Check bot logs for connection success
```

### Issue 4: Bot Signals Not Appearing
**Cause**: Pricing tier not synced  
**Solution**:
```powershell
# Sync user's pricing tier
curl -X POST https://kingsbalfx.name.ng/api/bot/pricing-sync `
  -H "x-admin-api-key: $env:ADMIN_API_KEY" `
  -Body '{
    "userId": "user-uuid-here",
    "tier": "vip"
  }'

# Check bot logs
curl https://kingsbalfx.name.ng/api/admin/bot-logs

# Verify signals in database
# Supabase → bot_logs table → Filter event = "signal_generated"
```

### Issue 5: Vercel Deployment Failed
**Cause**: Build error  
**Solution**:
```bash
# Check build logs
vercel logs --follow

# Build locally to find errors
npm run build

# Fix errors, then redeploy
git push origin main  # or: vercel --prod
```

---

## 📊 PRICING TIER STRUCTURE

Website displays these tiers:

| Tier | Price | Signals/Day | Max Trades | Features |
|------|-------|-------------|------------|----------|
| Free | ₦0 | 3 | 0 | Trial signals, limited community |
| Premium | ₦90,000/mo | 15 | 5 | Full signals, community, history |
| VIP | ₦150,000/mo | 30 | 10 | +1:1 mentorship, priority |
| Pro | ₦250,000/mo | Unlimited | 20 | +API access, custom strategies |
| Lifetime | ₦500,000 | Unlimited | Unlimited | Everything forever |

Bot automatically respects these limits via pricing sync.

---

## 🎯 TRADING PAIRS AVAILABLE

### Forex (36 pairs)
- Major: EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD, USDSEK
- Minor: EURJPY, EURGBP, EURCAD, EURCHF, EURAUD, GBPJPY, GBPCHF, GBPAUD, etc.
- Exotic: USDZAR, USDHKD, USDMXN, USDSGD, USDTHB, USDBRL, USDPLN, USDTRY, etc.

### Precious Metals (4)
- XAUUSD (Gold), XAGUSD (Silver), XPTUSD (Platinum), XPDUSD (Palladium)

### Cryptocurrencies (12)
- BTCUSD, ETHUSD, LTCUSD, BCHUSD, XRPUSD, EOSUSD
- ADAUSD, SOLUSD, DOGUSD, MATICUSD, LINKUSD, UNIUSD

### Indices (8)
- US500, NAS100, DJ30, FTSE, DAX40, CAC40, STOXX50, NIKKEI

### Commodities (6)
- CRUNOIL, BRENT, NATGAS, COMUSD, WHEATUSD, CORMUSD

---

## 📞 SUPPORT & MONITORING

### Monitoring Dashboard
```
Access: https://kingsbalfx.name.ng/admin/bot-logs
Shows: All bot activity in real-time
Updates: Every 5 seconds
Filters: By event type, date range, user
```

### Alert Configuration
```
Edit: ict_trading_bot/.env.production

Alert on large trades:
ALERT_ON_LARGE_TRADE=true
ALERT_LARGE_TRADE_SIZE_LOT=0.5

Alert on errors:
ALERT_ON_ERROR=true

Slack notifications:
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

---

## 🎉 DEPLOYMENT COMPLETE!

Your platform is now live at: **https://kingsbalfx.name.ng**

### Next Steps:
1. ✅ Monitor bot logs dashboard
2. ✅ Verify pricing tiers working
3. ✅ Test first trades with demo account
4. ✅ Promote to users
5. ✅ Scale infrastructure as needed

**Happy Trading! 🚀**


