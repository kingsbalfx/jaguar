# 🚀 QUICK START - RUN EVERYTHING

## ✅ Environment Files Created!

Your `.env` files are now set up with **development test values**.

### Files Created:
```
✅ jaguar-main/.env.local           (Web app config)
✅ ict_trading_bot/.env             (Trading bot config)
```

---

## 🎯 RUN THE WEB APP

Open **Terminal 1** and run:

```bash
cd jaguar-main
npm run dev
```

**You'll see:**
```
> Ready on https://kingsbalfx.name.ng
> WebSocket listening at wss://kingsbalfx.name.ng/ws/live-pen
```

✅ **Web app is running!** Go to: https://kingsbalfx.name.ng

---

## 🤖 RUN THE TRADING BOT

Open **Terminal 2** and run:

```bash
cd ict_trading_bot
python main.py
```

**You'll see:**
```
Bot started successfully ✓
Flask API running on https://your-bot-host:8000
```

✅ **Bot is running!** Available at: https://your-bot-host:8000

---

## ✅ TEST BOTH ARE WORKING

Open **Terminal 3** and run these tests:

### Test 1: Web App Health
```bash
curl https://kingsbalfx.name.ng/health
```
**Expected:** `{"status":"ok"}`

### Test 2: Bot Health
```bash
curl https://your-bot-host:8000/health
```
**Expected:** `{"status":"healthy","uptime":"..."}`

### Test 3: Web App Running
Open browser: https://kingsbalfx.name.ng
**Should see:** Login page

---

## 📝 BEFORE USING REAL CREDENTIALS

⚠️ **Important:** The `.env` files have **TEST VALUES** for development.

To use **REAL** credentials:

### For Web App (jaguar-main/.env.local):
1. Create Supabase project: https://supabase.com
2. Go to: Settings → API
3. Copy your real keys
4. Replace in `.env.local`:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`

### For Trading Bot (ict_trading_bot/.env):
1. Add your MetaTrader5 account details:

---

## 🎮 NEXT STEPS

1. **Run web app**: Terminal 1
   ```bash
   cd jaguar-main && npm run dev
   ```

2. **Run trading bot**: Terminal 2
   ```bash
   cd ict_trading_bot && python main.py
   ```

3. **Test health**: Terminal 3
   ```bash
   curl https://kingsbalfx.name.ng/health
   curl https://your-bot-host:8000/health
   ```

4. **Access web app**: https://kingsbalfx.name.ng

5. **View bot status**: https://your-bot-host:8000/status

---

## 🔑 ENVIRONMENT VARIABLES SUMMARY

### Web App (.env.local):
- `NEXT_PUBLIC_SUPABASE_URL` - Supabase URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Public API key
- `SUPABASE_SERVICE_ROLE_KEY` - Admin API key
- `PAYSTACK_PUBLIC_KEY` - Paystack public
- `PAYSTACK_SECRET_KEY` - Paystack secret
- `ADMIN_API_KEY` - Admin authentication

### Trading Bot (.env):
- `BOT_ENABLED=true` - Enable bot
- `SYMBOLS=EURUSD,...` - Trading pairs
- `RISK_PER_TRADE=1.0` - Risk %
- `SUPABASE_URL` - Database URL
- `SUPABASE_KEY` - Database key
- `JAGUAR_URL` - Web app URL
- `API_PORT=8000` - API port

---

## 🚀 YOU'RE READY!

Both services are now configured and ready to run.

**Just execute the commands above and you're good to go!** ✅


