# COMPLETE GETTING STARTED GUIDE

This is the final, exhaustive setup and deployment guide for the merged Jaguar + ICT Trading Bot platform.

## Prerequisites

- Docker & Docker Compose installed
- Node 18+ and npm 9+
- Python 3.11+
- Git
- A Supabase account and project
- A Paystack account (test and production keys)

## Phase 1: Local Development Setup (10 min)

### Step 1: Clone and setup environment

```bash
# Navigate to project root
cd kingsbal\ magix\ trading

# Copy environment template
cp .env.example .env

# Edit .env with your secrets
nano .env
# or on Windows:
# notepad .env
```

### Step 2: Fill in environment variables

Create a `.env` file at the root with:

```
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key

# Paystack
PAYSTACK_SECRET=sk_test_xxx (or sk_live_xxx for production)
PAYSTACK_PUBLIC=pk_test_xxx (or pk_live_xxx)
PAYSTACK_WEBHOOK_SECRET=your_webhook_secret

# Security
ADMIN_API_KEY=your_super_secret_admin_key

# Node
NODE_ENV=development
```
MT5 credentials are set in the Admin panel and stored in Supabase (not in `.env`).

### Step 3: Start services with Docker

```bash
# From repo root
docker-compose up --build

# You should see:
# - jaguar_web listening on https://kingsbalfx.name.ng
# - ict_trading_bot listening on https://your-bot-host:8000
```

### Step 4: Verify health endpoints

```bash
# In a new terminal, test endpoints
curl https://kingsbalfx.name.ng/health
# Expected: {"status":"ok","ts":1644444444000}

curl https://your-bot-host:8000/health
# Expected: {"status":"ok","running":true}
```

## Phase 2: Database Setup (Supabase)

### Step 1: Create Supabase project

1. Go to https://supabase.com
2. Create new project
3. Copy URL and anon/service keys to `.env`

### Step 2: Run migrations

1. Open Supabase SQL editor (in dashboard)
2. Copy the entire content of `migrations/001_init_schema.sql`
3. Paste into SQL editor and run

### Step 3: Verify tables created

In Supabase dashboard, confirm these tables exist:
- profiles
- payments
- subscriptions
- bot_logs

## Phase 3: Web App Setup (5 min)

### Step 1: Create admin user

1. In Supabase, go to **Authentication** → **Users**
2. Create a new user with email `admin@yourdomain.com` and password
3. In the Supabase SQL editor, run:

```sql
INSERT INTO profiles (id, email, name, role, lifetime) 
SELECT id, email, 'Super Admin', 'admin', true 
FROM auth.users WHERE email = 'admin@yourdomain.com';
```

### Step 2: Sign in and verify admin dashboard

1. Go to https://kingsbalfx.name.ng/login
2. Sign in with admin email/password
3. You should be redirected to `/admin`
4. Verify these sidebar options appear:
   - Users
   - Payments
   - Bot Logs
   - Analytics

## Phase 4: Test Payment Flow (5 min)

### Step 1: Create a test Paystack account

If not already done:
1. Go to https://paystack.com
2. Sign up and create a business account
3. In settings, find your API keys (test mode)
4. Copy test secret key to `.env`

### Step 2: Test payment initialization

```bash
curl -X POST https://kingsbalfx.name.ng/api/init-paystack \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","amount":500000}'

# Should return authorization_url (or error if keys missing)
```

### Step 3: Simulate webhook

```bash
# From repo root
node scripts/send_paystack_webhook.js

# Check admin dashboard → Payments to see the event logged
```

## Phase 5: Test Bot Integration

### Step 1: Verify bot is running

```bash
curl https://your-bot-host:8000/health
curl https://your-bot-host:8000/status
```

### Step 2: Persist signals and view logs

The bot now writes signals and logs directly to Supabase. To test locally:

```bash
# Ensure Supabase envs are set in your shell
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_KEY=your_service_role_key
python ict_trading_bot/scripts/test_webhook.py
```

Then check the `bot_logs` and `bot_signals` tables in the Supabase dashboard or the admin UI at `https://kingsbalfx.name.ng/admin/bot-logs`.

## Phase 6: Run Tests

### Node Tests

```bash
# Smoke tests (quick health checks)
npm run test:smoke

# Unit tests (if Jest configured)
npm run test:unit

# All tests
npm run test:all
```

### Python Tests

```bash
cd ict_trading_bot
python scripts/smoke_tests.py
```

## Phase 7: Production Checklist

Before deploying to production:

### Security
- [ ] Review `.env` — ensure no hardcoded secrets
- [ ] Rotate all secrets (Supabase keys, Paystack live keys, Paystack webhook secrets)
- [ ] Enable HTTPS on domain
- [ ] Review `SECURITY_CHECKLIST.md` and address all [ ] items
- [ ] Run RLS policies from `RLS_SETUP.sql` in Supabase

### Database
- [ ] Backup Supabase database
- [ ] Verify RLS policies are enabled
- [ ] Test backup restore

### Testing
- [ ] Run all tests locally and pass
- [ ] Test payment flow end-to-end
- [ ] Verify admin pages load
- [ ] Test bot will start if MT5 connected

### Deployment
- [ ] Build Docker images
- [ ] Push to Docker registry
- [ ] Run on production server
- [ ] Test health endpoints on production URL
- [ ] Monitor logs in real-time

## Phase 8: Post-Deployment

### Daily Tasks
- [ ] Monitor `/admin/bot-logs` for errors
- [ ] Check `/admin/analytics` for P&L
- [ ] Review `/admin/payments` for payment issues

### Weekly Tasks
- [ ] Review bot performance by symbol
- [ ] Check drawdown metrics
- [ ] Verify no uncaught exceptions in logs

### Monthly Tasks
- [ ] Rotate secrets
- [ ] Review analytics trends
- [ ] Backtest any rule changes before deploying

## Common Issues & Solutions

### "Connection refused" on kingsbalfx.name.ng
→ Docker container not running. Check: `docker ps` and `docker-compose logs`

### "Supabase connection error"
→ Check NEXT_PUBLIC_SUPABASE_URL and SUPABASE_KEY in `.env`

### "Paystack webhook not processing"
→ Verify PAYSTACK_WEBHOOK_SECRET matches Paystack dashboard

### Bot not trading after deployment
→ Check MT5 connection in bot logs: `/admin/bot-logs`

### Admin pages return "Forbidden"
→ Verify user role is "admin" in profiles table

## Architecture at a Glance

```
┌─ Web App (port:3000)
│  ├─ Login & Auth (Supabase)
│  ├─ Admin Dashboard
│  │  ├─ Users Management
│  │  ├─ Payments Tracking
│  │  ├─ Bot Logs Viewer
│  │  └─ Analytics Dashboard
│  └─ APIs
│     ├─ /api/init-paystack
│     ├─ /api/paystack-webhook
│     └─ /api/admin/*
│
├─ Trading Bot (port:8000)
│  ├─ MT5 Connection
│  ├─ Strategy Engine
│  └─ Signal persistence to Supabase (`bot_signals` / `bot_logs`)
│
└─ Database (Supabase)
   ├─ profiles table
   ├─ payments table
   ├─ subscriptions table
   └─ bot_logs table
```

## Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Project overview |
| `GETTING_STARTED.md` | You are here |
| `ARCHITECTURE.md` | System design & data flows |
| `TRADER_GUIDE.md` | For forex traders using the platform |
| `DEPLOYMENT_CHECKLIST.md` | Local deployment steps |
| `SECURITY_CHECKLIST.md` | Pre-production security review |
| `INTEGRATION_REPORT.md` | Merge status & feature summary |

## Support & Next Steps

1. **Understand the architecture**: Read `ARCHITECTURE.md`
2. **Learn trading best practices**: Read `TRADER_GUIDE.md`
3. **Customize trading rules**: Edit `ict_trading_bot/strategy/*.py`
4. **Monitor performance**: Use `/admin/analytics`
5. **Deploy to production**: Follow production checklist

## Congratulations! 🎉

Your integrated trading platform is now ready to run locally and deploy to production. The merging of Jaguar and ICT Trading Bot is complete with:

✅ Full authentication & authorization
✅ Paystack lifetime subscription system
✅ Admin dashboard with user, payment, and bot log management
✅ Real-time trade analytics
✅ Comprehensive testing & CI/CD
✅ Professional documentation
✅ Security best practices

---

**Setup Time**: ~30-45 minutes
**Next Milestone**: Deploy to production
**Support**: Check logs in `/admin/bot-logs` and error tracking in your Sentry account (if configured)



