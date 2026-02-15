# 🚀 SUPABASE SQL - COPY & PASTE ONLY

**⏰ 2 MINUTES - Just copy this entire code block and paste into Supabase SQL Editor!**

---

## 👉 COPY EVERYTHING BELOW THIS LINE 👈

```sql
-- ============================================
-- COMPLETE SUPABASE DATABASE SETUP
-- ============================================

-- TABLE 1: PROFILES (Users)
CREATE TABLE IF NOT EXISTS profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email VARCHAR(254) UNIQUE NOT NULL,
  name VARCHAR(255),
  role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('admin', 'user', 'vip', 'premium')),
  lifetime BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_profiles_email ON profiles(email);
CREATE INDEX idx_profiles_lifetime ON profiles(lifetime);

-- TABLE 2: PAYMENTS
CREATE TABLE IF NOT EXISTS payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event VARCHAR(255) NOT NULL,
  data JSONB DEFAULT '{}',
  customer_email VARCHAR(254),
  amount BIGINT,
  status VARCHAR(50),
  received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_email) REFERENCES profiles(email) ON DELETE SET NULL
);

CREATE INDEX idx_payments_event ON payments(event);
CREATE INDEX idx_payments_customer_email ON payments(customer_email);
CREATE INDEX idx_payments_received_at ON payments(received_at DESC);

-- TABLE 3: SUBSCRIPTIONS
CREATE TABLE IF NOT EXISTS subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(254) NOT NULL,
  plan VARCHAR(100) NOT NULL,
  status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'revoked', 'expired')),
  amount BIGINT DEFAULT 0,
  started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  ended_at TIMESTAMP,
  FOREIGN KEY (email) REFERENCES profiles(email) ON DELETE CASCADE,
  UNIQUE(email, plan)
);

CREATE INDEX idx_subscriptions_email ON subscriptions(email);
CREATE INDEX idx_subscriptions_plan ON subscriptions(plan);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);

-- TABLE 4: BOT_LOGS
CREATE TABLE IF NOT EXISTS bot_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event VARCHAR(255) NOT NULL,
  payload JSONB DEFAULT '{}',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_bot_logs_event ON bot_logs(event);
CREATE INDEX idx_bot_logs_created_at ON bot_logs(created_at DESC);

-- ENABLE ROW-LEVEL SECURITY
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bot_logs ENABLE ROW LEVEL SECURITY;

-- SECURITY POLICIES
CREATE POLICY "users_read_own_profile" ON profiles
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "users_update_own_profile" ON profiles
  FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "admins_read_all_profiles" ON profiles
  FOR SELECT USING (
    auth.role() = 'service_role' OR 
    EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role = 'admin')
  );

CREATE POLICY "service_role_payments" ON payments
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_subscriptions" ON subscriptions
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_bot_logs" ON bot_logs
  FOR ALL USING (auth.role() = 'service_role');

-- ALL DONE! ✅
```

---

## 📋 QUICK STEPS

1. **Open:** https://supabase.com → Click project → SQL Editor
2. **Copy:** All code above
3. **Paste:** Into empty text box
4. **Run:** Click blue "Run" button
5. **Done:** See "Success! (X queries executed)"

---

## ✅ VERIFY (3 seconds)

Left sidebar → Table Editor → See 4 tables:
- ✓ profiles
- ✓ payments
- ✓ subscriptions
- ✓ bot_logs

**If you see all 4 → YOU'RE DONE!** 🎉

---

## 🎖️ CREATE ADMIN USER

**After running SQL above**, run this:

```sql
-- Step 1: Create user in Authentication first!
-- (In Supabase: Authentication → Users → Add User)
-- Email: admin@yourdomain.com
-- Password: [something secure]

-- Step 2: Then run this SQL (change email!):
INSERT INTO profiles (id, email, name, role, lifetime) 
SELECT id, email, 'Super Admin', 'admin', true 
FROM auth.users WHERE email = 'admin@yourdomain.com';
```

---

## 🧪 TEST PAYMENT

```sql
-- Add test payment to verify it works
INSERT INTO payments (event, customer_email, amount, status)
VALUES ('charge.success', 'admin@yourdomain.com', 100000, 'success');

-- Verify it was added
SELECT * FROM payments;
```

---

**That's all!** Ready for web app login! 🚀


