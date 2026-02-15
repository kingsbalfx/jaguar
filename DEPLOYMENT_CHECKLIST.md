# Local deployment & testing checklist

1. Copy `.env.example` -> `.env` and fill keys: Supabase, Paystack, ADMIN_API_KEY.
2. Start Docker services:

```powershell
docker-compose up --build
```

3. Verify web app health: `https://kingsbalfx.name.ng/health` should return status ok.
4. Verify bot health: `https://kingsbalfx.name.ng/api/health` or `https://your-bot-host:8000/health` depending on setup.
5. Initialize a Paystack transaction via the UI at `/subscribe` or call `/api/init-paystack`.
6. Simulate webhook locally:

```powershell
# from repo root
node scripts/send_paystack_webhook.js
```

7. Check admin payments: sign in as an admin and open `/admin/payments` to view persisted webhook events.
8. To test bot control endpoints: call `POST /control` on bot API (https://your-bot-host:8000/control) with `{action: "stop"}`.
9. Run security checklist: ensure `.env` not committed, rotate keys before production, enable HTTPS.10. Run smoke tests:

```powershell
# Node smoke tests (web)
node jaguar-main/scripts/smoke-tests.js

# Python smoke tests (bot)
python ict_trading_bot/scripts/smoke_tests.py
```

11. Check admin pages:
- Admin users: `/admin/users` to list and toggle lifetime access.
- Admin payments: `/admin/payments` to view payment history.
- Admin bot logs: `/admin/bot-logs` to view bot activity logs.

