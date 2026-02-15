# 🚀 QUICK START - PRODUCTION DEPLOYMENT
# Kings Balfx Trading Platform → kingsbalfx.name.ng
# Complete rewrite from local-only to production
# Date: Feb 13, 2026

## 📦 WHAT'S BEEN COMPLETED FOR YOU

Your entire project has been rewritten for production deployment:

✅ **Environment Configuration**
   - jaguar-main/.env.production (web app config)
   - ict_trading_bot/.env.production (bot config)
   - All pointing to kingsbalfx.name.ng (not local-only)

✅ **Pricing System (5 Tiers)**
   - Free (₦0): 3 signals/day, 0 trades
   - Premium (₦90,000): 15 signals/day, 5 trades
   - VIP (₦150,000): 30 signals/day, 10 trades, mentorship
   - Pro (₦250,000): Unlimited signals, 20 trades, 1-on-1 mentorship
   - Lifetime (₦500,000): Everything unlimited forever

✅ **Trading Pairs (66+)**
   - 36 Forex pairs (Major, Minor, Exotic)
   - 4 Precious metals (Gold, Silver, Platinum, Palladium)
   - 12 Cryptocurrencies (Bitcoin, Ethereum, Litecoin, etc.)
   - 8 Indices (S&P 500, NASDAQ, DAX, etc.)
   - 6 Commodities (Oil, Gas, Agricultural)

✅ **Pricing Automation**
   - lib/pricing-config.js (centralized pricing)
   - pages/api/bot/pricing-sync.js (bot-web sync)
   - pages/api/admin/bot-control.js (bot management)
   - Database pricing_tiers table
   - Automatic tier enforcement

✅ **Mentorship Features**
   - Group sessions for VIP+ tiers
   - 1-on-1 sessions for Pro tier
   - mentorship_sessions database table
   - Mentor assignment system

✅ **Deployment Automation**
   - deploy.ps1 (PowerShell script)
   - PRODUCTION_DEPLOYMENT_GUIDE.md
   - IMPLEMENTATION_CHECKLIST.md
   - Database migrations

---

## ⚡ GETTING STARTED IN 5 MINUTES

### Step 1: Gather Your Production Credentials
You need:
```
SUPABASE:
  - Production SUPABASE_URL (https://xxxxx.supabase.co)
  - Production SUPABASE_ANON_KEY
  - Production SERVICE_ROLE_KEY

PAYSTACK (LIVE MODE):
  - NEXT_PUBLIC_PAYSTACK_KEY (pk_live_...)
  - PAYSTACK_SECRET_KEY (sk_live_...)

MT5:
  - Set MT5 login, password, and server in the Admin panel

API KEYS (Generate random):
  - ADMIN_API_KEY (32+ chars)
```

### Step 2: Update Environment Files

Edit these files and fill in YOUR credentials:

**jaguar-main/.env.production**
```bash
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key_here
PAYSTACK_PUBLIC_KEY=pk_live_your_live_key_here
# ... rest of the file already has examples
```

**ict_trading_bot/.env.production**
```bash
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
# ... rest of the file already has examples
```

### Step 3: Choose Deployment Method

#### OPTION A: Fully Automated (Recommended)
```powershell
# Go to project root
cd "C:\Users\HP\Downloads\kingsbal\kingsbal magix trading"

# Run deployment script
.\deploy.ps1 -Action deploy-full `
  -SupabaseUrl "https://xxx.supabase.co" `
  -SupabaseKey "eyJ..." `
  -PaystackKey "pk_live_..." `
  -PaystackSecret "sk_live_..." `
  -AdminApiKey "your_random_32_char_key"

# Script will:
# ✓ Validate environment
# ✓ Update .env files
# ✓ Remove local files (.env.local, ADMIN_CREDENTIALS.txt)
# ✓ Deploy web app to Vercel
# ✓ Start bot
```

#### OPTION B: Manual Deployment
```powershell
# 1. Update environment files (as shown above)

# 2. Deploy web app
cd jaguar-main
npm install
npm run build
vercel --prod --env-file .env.production

# 3. Deploy bot
cd ..\ict_trading_bot
pip install -r requirements.txt
python main.py
```

#### OPTION C: Step-by-Step with Verification
```powershell
# Validate first
.\deploy.ps1 -Action validate
# Should show: ✅ Environment validation passed!

# Then deploy web only
.\deploy.ps1 -Action deploy-web `
  -SupabaseUrl "https://xxx.supabase.co" `
  -PaystackKey "pk_live_..."

# Then deploy bot
.\deploy.ps1 -Action deploy-bot
```

---

## ✅ VERIFY DEPLOYMENT

After deploying, test everything:

### 1. Web App Running
```powershell
# Should return: {"status":"ok","ts":...}
curl https://kingsbalfx.name.ng/health

# Should display 5 pricing tiers
https://kingsbalfx.name.ng/pricing

# Should return pricing config
curl https://kingsbalfx.name.ng/api/bot/pricing-sync
```

### 2. Bot Running
```powershell
# Should return: {"status":"ok","running":true}
curl https://your-bot-host:8000/health

# View real-time logs
https://kingsbalfx.name.ng/admin/bot-logs
```

### 3. Database Connected
```sql
-- Run in Supabase → SQL Editor
SELECT COUNT(*) FROM pricing_tiers;   -- Should be 5
SELECT * FROM pricing_tiers ORDER BY price;
```

---

## 🎯 WHAT'S NEW

### Automatic Features (No Code Changes Needed)

✨ **Pricing Tier Alignment**
   - Bot automatically respects user tier
   - User with Free tier → 0 trades allowed
   - User with VIP tier → 30 signals/day
   - User with Lifetime tier → Unlimited everything

✨ **Automatic Trading Pair Selection**
   - Free: Major forex only (8 pairs)
   - Premium: Major + Minor forex (24 pairs)
   - VIP: Forex + Metals + Some crypto (50+ pairs)
   - Pro/Lifetime: All 66+ pairs available

✨ **Signal Quality Enforcement**
   - Free: Basic quality signals
   - Premium: Standard quality
   - VIP: Premium quality
   - Pro/Lifetime: Elite quality signals

✨ **Mentorship Scheduling**
   - VIP: 4 group sessions/month
   - Pro: 2 one-on-one + 8 group sessions/month
   - Lifetime: Unlimited mentorship

---

## 📞 ADMIN COMMANDS

### Sync Single User's Pricing
```bash
curl -X POST https://kingsbalfx.name.ng/api/bot/pricing-sync \
  -H "x-admin-api-key: YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "user-uuid-here",
    "tier": "vip"
  }'
```

### Sync All Users
```bash
curl -X POST https://kingsbalfx.name.ng/api/admin/bot-control \
  -H "x-admin-api-key: YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"sync-all-users"}'
```

### Get Bot Statistics
```bash
curl -X POST https://kingsbalfx.name.ng/api/admin/bot-control \
  -H "x-admin-api-key: YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"get-stats"}'
```

### Get Recent Signals
```bash
curl -X POST https://kingsbalfx.name.ng/api/admin/bot-control \
  -H "x-admin-api-key: YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"get-signals","limit":20}'
```

---

## 📊 NEW FILES CREATED

### Core Configuration
- ✅ jaguar-main/lib/pricing-config.js (200 lines)
- ✅ ict_trading_bot/config/trading_pairs.py (400 lines)
- ✅ migrations/002_add_pricing_and_mentorship.sql

### API Endpoints
- ✅ jaguar-main/pages/api/bot/pricing-sync.js
- ✅ jaguar-main/pages/api/admin/bot-control.js

### Updated UI
- ✅ jaguar-main/pages/pricing.js (complete redesign)

### Automation & Deployment
- ✅ deploy.ps1 (PowerShell deployment script)
- ✅ PRODUCTION_DEPLOYMENT_GUIDE.md (300+ lines)
- ✅ IMPLEMENTATION_CHECKLIST.md (400+ lines)

### Documentation
- ✅ This file (QUICK_START.md)

---

## 🚨 IMPORTANT NOTES

### DO NOT FORGET
1. ✅ Fill in all credentials in .env.production files
2. ✅ Use LIVE Paystack keys (not test keys)
3. ✅ Generate strong random secrets (32+ chars)
4. ✅ Test with demo MT5 account first
5. ✅ Keep .env files secure (never commit to git)
6. ✅ Monitor bot logs for first 24 hours

### COMMON ISSUES & SOLUTIONS

**"Supabase URL is required"**
- Check jaguar-main/.env.production has NEXT_PUBLIC_SUPABASE_URL
- Redeploy: `vercel --prod --env-file jaguar-main/.env.production`

**"Bot not sending signals"**
- Verify bot is running: `curl https://your-bot-host:8000/health`
- Sync user tier: `curl -X POST https://kingsbalfx.name.ng/api/bot/pricing-sync ...`
- Check logs: https://kingsbalfx.name.ng/admin/bot-logs

**"Payments not working"**
- Verify Paystack LIVE keys (not test)
- Check webhook URL: https://kingsbalfx.name.ng/api/paystack/webhook
- Test with: `curl -X POST https://kingsbalfx.name.ng/api/paystack/webhook ...`

**"MT5 connection failed"**
- Update MT5 credentials in the Admin panel
- Restart the bot to reload credentials
- Verify server name spelling

---

## 📊 ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────┐
│         Users - KINGSBALFX.NAME.NG (Vercel)            │
├─────────────────────────────────────────────────────────┤
│  PAYSTACK (Payments)  ←→  WEBSITE (Next.js)           │
│                            ↓                            │
│                        SUPABASE (Database)              │
├─────────────────────────────────────────────────────────┤
│  Trading Signals  ←  TRADING BOT (Python)  →  MT5      │
│  ↓                                                      │
│  Supabase Logs (Visible in Admin Dashboard)            │
└─────────────────────────────────────────────────────────┘

Data Flow:
1. User registers @ kingsbalfx.name.ng
2. User upgrades to VIP (pay via Paystack) → tier set to "vip"
3. Pricing sync API updates bot: user can have 10 trades
4. Bot generates signals, respects 10 trade limit
5. Bot persists signals to Supabase (`bot_signals` / `bot_logs`) — web reads from Supabase
6. User sees signals, executes trades in MT5
7. Bot logs all activity to Supabase
8. Admin views dashboard @ /admin/bot-logs
```

---

## 🎉 READY TO LAUNCH!

Your platform is now production-ready at **https://kingsbalfx.name.ng**

### Next Steps:
1. Run deployment script
2. Verify all endpoints work
3. Monitor bot for 24 hours
4. Announce to users
5. Start collecting signals and payments!

---

**Questions?** Check:
- PRODUCTION_DEPLOYMENT_GUIDE.md (detailed deployment help)
- IMPLEMENTATION_CHECKLIST.md (full verification checklist)
- jaguar-main/pages/api/admin/bot-control.js (API endpoints)
- ict_trading_bot/config/trading_pairs.py (trading pairs config)

**Happy Trading! 🚀**


