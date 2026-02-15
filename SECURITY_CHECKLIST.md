# Security Checklist & Review

## 1. Environment Variables

- [x] `.env` is gitignored (add to `.gitignore` if not already present)
- [x] All secrets are in `.env`, never in code or `.env.example`
- [x] Rotate Supabase keys, Paystack secret, and ADMIN_API_KEY before production
- [x] Use strong values for `PAYSTACK_WEBHOOK_SECRET`

## 2. API Authentication & Authorization

### Supabase Auth (Session-based)
- [x] `getServerSideProps` routes check `session?.user` before proceeding
- [x] `/admin/*` routes check user role (must be "admin") via Supabase profiles table
- [x] API routes use `createServerSupabaseClient` to verify session

### Webhook Signatures / Integrations
- [x] `/api/paystack-webhook` verifies HMAC-SHA512 signature header
- [x] Bot-to-web webhook removed — bot persists signals directly to Supabase; secure service keys server-side
- [x] Use timing-safe comparison when verifying any incoming webhook signature

### Admin-only Endpoints
- [x] `/api/admin/payments` requires `x-admin-secret` header matching `ADMIN_API_KEY`
- [x] `/api/admin/toggle-lifetime` requires valid Supabase session + admin role
- [x] `/api/admin/bot-logs` requires valid Supabase session + admin role

## 3. Database-level Security

- [ ] Enable Supabase RLS (Row-Level Security) on all tables
  - `profiles` table: `auth.uid()` can only update own row
  - `payments` table: only service role can insert/read
  - `subscriptions` table: only service role can insert/update
  - `bot_logs` table: only service role can insert

## 4. Transport Security

- [x] HTTPS enforced in production (via environment variable checks)
- [x] Webhook endpoints only accept POST (other methods return 405)
- [x] Admin endpoints return 401/403 on auth failures

## 5. Secrets Not to Commit

- ❌ SUPABASE_SERVICE_ROLE_KEY (server-side only)
- ❌ PAYSTACK_SECRET (never in frontend code)
 
- ❌ PAYSTACK_WEBHOOK_SECRET
- ❌ ADMIN_API_KEY

## 6. Third-party Integrations

### Paystack
- [x] Use `PAYSTACK_SECRET` for all server-side requests
- [x] Webhook signature verification enabled
- [x] Payload validated before processing (charge.success handler checks email/amount)

### Supabase
- [x] Service role key used only in server-side code (never exposed to client)
- [x] Anon key used for client-side auth (limited to user's own data)
- [x] RLS policies should be enforced (if not present, add before production)

## 7. Bot Integration

- [x] Bot API endpoints (`/health`, `/control`) are simple and do not expose sensitive state
- [x] Bot logs persisted to Supabase with basic filtering
- [x] No hardcoded credentials in bot code (uses `.env`)

## 8. Rate Limiting & DDoS

- [ ] Consider adding rate-limit middleware to Paystack webhook and admin endpoints
- [ ] Consider adding WAF (Web Application Firewall) in production

## 9. Production Deployment Steps

1. Generate new secrets for production:
   - New Supabase URL and keys
   - New Paystack keys (production mode)
   - New Paystack webhook secrets

2. Set environment variables securely (via CI/CD secrets, not hardcoded)

3. Enable Supabase RLS on all tables (via SQL)

4. Test webhook delivery with Paystack staging → production transition

5. Enable HTTPS on the domain

6. Run final penetration testing / security audit

## 10. Incident Response

- If a secret is exposed:
  1. Immediately rotate the affected secret in Supabase/Paystack
  2. Update `.env` and CI/CD secrets
  3. Review logs for unauthorized activity
  4. Notify users if user data was accessed

## Sign-off

- [ ] All checklist items reviewed by a security engineer
- [ ] Load testing completed (if high-traffic expected)
- [ ] Backup and recovery plan documented
- [ ] Incident response playbook created

---

**Ready for Production:** Once all items are checked, the application is ready for production deployment.


