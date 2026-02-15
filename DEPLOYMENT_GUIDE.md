# KINGSBALFX PRODUCTION DEPLOYMENT GUIDE

## 🚀 Pre-Deployment Checklist

### 1. Environment Variables Setup

You must set these in Vercel's project environment settings:

**From `jaguar-main/.env.production`:**
```
NEXT_PUBLIC_SUPABASE_URL = your-production-supabase-url.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY = your-production-anon-key
SUPABASE_SERVICE_ROLE_KEY = your-production-service-role-key
PAYSTACK_PUBLIC_KEY = pk_live_xxxxx (NOT test key!)
PAYSTACK_SECRET_KEY = sk_live_xxxxx (NOT test key!)
PAYSTACK_WEBHOOK_SECRET = your_webhook_secret
ADMIN_API_KEY = your_admin_api_key
NEXT_PUBLIC_DOMAIN = https://kingsbalfx.name.ng
NODE_ENV = production
```

**From `ict_trading_bot/.env.production`:**
```
SUPABASE_URL = your-production-supabase-url.supabase.co
SUPABASE_KEY = your-production-service-role-key
MT5 credentials are configured in the Admin panel (stored in Supabase)
```

### 2. Domain Setup (kingsbalfx.name.ng)

In Vercel project settings under **Domains**:
- Add custom domain: `kingsbalfx.name.ng`
- Update your domain registrar's DNS to point to Vercel nameservers
- SSL certificate auto-issued by Vercel

### 3. Remove Local/Test Files

❌ DELETE before deploying:
```
jaguar-main/.env.local
jaguar-main/ADMIN_CREDENTIALS.txt
ict_trading_bot/.env (local version)
.git/secrets (any cached credentials)
```

✅ KEEP for production:
```
jaguar-main/.env.production
ict_trading_bot/.env.production  
```

## 📋 Deployment Steps

### Option A: Vercel CLI (Recommended)

```powershell
# Install Vercel CLI
npm install -g vercel

# Navigate to web app directory
cd 'c:\Users\HP\Downloads\kingsbal\kingsbal magix trading\jaguar-main'

# Deploy (will prompt for environment setup)
s

# Verify deployment
vercel ls
```

### Option B: GitHub Integration (if repo is linked)

1. Commit all changes:
```powershell
git add .
git commit -m "production: configure for kingsbalfx.name.ng deployment"
git push origin main
```

2. Vercel auto-deploys from `main` branch
3. Check deployment status: https://vercel.com/dashboard

### Option C: Vercel Dashboard (Manual)

1. Go to https://vercel.com/dashboard
2. Select your project
3. Go to **Settings → Environment Variables**
4. Add all production variables from `.env.production`
5. Trigger redeploy from **Deployments** tab

## 🔌 Trading Bot Deployment

The trading bot should run on your production MT5 server (not Vercel):

```powershell
# On your production trading server:
cd ict_trading_bot

# Use production environment
$env:ENVIRONMENT = "production"

# Run with production config
python main.py
```

Bot will:
- Connect to production MT5 account
- Log all activity to Supabase

g## ✅ Post-Deployment Verification

### Health Checks

```powershell
# Web app health
curl https://kingsbalfx.name.ng/health

# Supabase connectivity
curl https://kingsbalfx.name.ng/api/health

# Admin API
curl -H "Authorization: Bearer $env:ADMIN_API_KEY" `
     https://kingsbalfx.name.ng/api/admin/status
```

### Expected Responses

**GET /health**
```json
{"status":"ok","ts":1707859200000}
```

**GET /api/health** (Supabase)
```json
{"status":"connected","database":"online"}
```

### Monitor Vercel Logs

```powershell
# Real-time logs
vercel logs --follow
```

## 🔒 Security Checklist

- [ ] All test credentials removed from code
- [ ] `.env.local` added to `.gitignore`
- [ ] Service keys never committed to git
- [ ] SSL/HTTPS enabled (auto by Vercel)
- [ ] CORS properly configured for kingsbalfx.name.ng
- [ ] Paystack webhook signature verification enabled
- [ ] Database backups enabled in Supabase
- [ ] Admin API key rotated and secure
- [ ] Paystack account in LIVE mode (not test)

## 🚨 Troubleshooting

### "NEXT_PUBLIC_SUPABASE_URL is required"
- Environment variables not set in Vercel
- Redeploy after setting variables: `vercel --prod`

### "Cannot connect to MT5"
- Bot credentials in `.env.production` incorrect
- MT5 not running on production server
- Firewall blocking connection

### "Paystack webhook failures"
- `PAYSTACK_WEBHOOK_SECRET` mismatch between web app and Paystack
- Paystack webhook not pointing to new domain

### "Database connection refused"
- Supabase connection string incorrect
- IP not whitelisted in Supabase
- Service role key insufficient permissions

## 📞 Support

For deployment issues:
1. Check Vercel logs: `vercel logs`
2. Check Supabase logs: https://supabase.com/dashboard
3. Verify DNS propagation: `nslookup kingsbalfx.name.ng`
4. Test MT5 connection directly

---

**Deployment Date:** Feb 13, 2026  
**Domain:** https://kingsbalfx.name.ng  
**Platform:** Vercel  
**Live:** ✅ Ready


