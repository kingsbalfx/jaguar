# 🗄️ COMPLETE SUPABASE DATABASE SETUP GUIDE

## What You're Building

You're creating a **database** that stores:
- 👤 **User information** (profiles table)
- 💳 **Payment history** (payments table)
- 🎁 **Subscriptions** (subscriptions table)
- 🤖 **Bot activity logs** (bot_logs table)

Think of it like a **filing cabinet** with 4 folders:
```
DATABASE (Filing Cabinet)
├── Profiles Folder 📁 (who are the users?)
├── Payments Folder 💳 (who paid what?)
├── Subscriptions Folder 🎁 (who has access?)
└── Bot Logs Folder 🤖 (what did bot do?)
```

---

## QUICK START (5 Minutes)

### Step 1: Go to Supabase

1. Open browser
2. Go to: `https://supabase.com` 🌐
3. Sign in (or create account)
4. Open your project
5. Click **"SQL Editor"** (left side menu)

### Step 2: Copy & Paste ALL SQL Code

**BELOW THIS LINE** → Copy everything → Paste into Supabase SQL Editor → Click **"Run"** ✅

---

## 🔥 COMPLETE SQL CODE (Copy Everything Below!)

```sql
-- ============================================
-- SUPABASE DATABASE SETUP - COMPLETE SCRIPT
-- For: Jaguar Mentorship + ICT Trading Bot
-- Date: 2026
-- ============================================

-- ============================================
-- TABLE 1: PROFILES (Users)
-- ============================================
-- What: Stores user account information
-- Why: Need to know who is using the system
-- Fields: id, email, name, role, lifetime flag

CREATE TABLE IF NOT EXISTS profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email VARCHAR(254) UNIQUE NOT NULL,
  name VARCHAR(255),
  role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('admin', 'user', 'vip', 'premium')),
  lifetime BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Speed up lookups by email and lifetime status
CREATE INDEX idx_profiles_email ON profiles(email);
CREATE INDEX idx_profiles_lifetime ON profiles(lifetime);

-- ============================================
-- TABLE 2: PAYMENTS (Payment History)
-- ============================================
-- What: Stores all payments from Paystack
-- Why: Need proof of who paid and how much
-- Fields: id, event, data, email, amount, status, date

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

-- Speed up payment lookups
CREATE INDEX idx_payments_event ON payments(event);
CREATE INDEX idx_payments_customer_email ON payments(customer_email);
CREATE INDEX idx_payments_received_at ON payments(received_at DESC);

-- ============================================
-- TABLE 3: SUBSCRIPTIONS (User Access)
-- ============================================
-- What: Stores subscription details
-- Why: Track who has access and when access expires
-- Fields: id, email, plan, status, amount, dates

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

-- Speed up subscription lookups
CREATE INDEX idx_subscriptions_email ON subscriptions(email);
CREATE INDEX idx_subscriptions_plan ON subscriptions(plan);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);

-- ============================================
-- TABLE 4: BOT_LOGS (Bot Activity)
-- ============================================
-- What: Stores what the trading bot did
-- Why: Track trades, errors, and bot activity
-- Fields: id, event, payload (JSON), timestamp

CREATE TABLE IF NOT EXISTS bot_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event VARCHAR(255) NOT NULL,
  payload JSONB DEFAULT '{}',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Speed up log lookups
CREATE INDEX idx_bot_logs_event ON bot_logs(event);
CREATE INDEX idx_bot_logs_created_at ON bot_logs(created_at DESC);

-- ============================================
-- SECURITY: ENABLE ROW-LEVEL SECURITY (RLS)
-- ============================================
-- What: Makes sure users only see their own data
-- Why: Privacy! One user shouldn't see another user's payments

-- 1️⃣ Enable RLS on profiles table
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- 2️⃣ Enable RLS on payments table
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

-- 3️⃣ Enable RLS on subscriptions table
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- 4️⃣ Enable RLS on bot_logs table
ALTER TABLE bot_logs ENABLE ROW LEVEL SECURITY;

-- ============================================
-- SECURITY POLICIES: Who Can See What?
-- ============================================

-- POLICY 1: Users can read their own profile
CREATE POLICY "users_read_own_profile" ON profiles
  FOR SELECT USING (auth.uid() = id);

-- POLICY 2: Users can update their own profile
CREATE POLICY "users_update_own_profile" ON profiles
  FOR UPDATE USING (auth.uid() = id);

-- POLICY 3: Admins can read all profiles
CREATE POLICY "admins_read_all_profiles" ON profiles
  FOR SELECT USING (
    auth.role() = 'service_role' OR 
    EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role = 'admin')
  );

-- POLICY 4: Service role (backend) can access payments
CREATE POLICY "service_role_payments" ON payments
  FOR ALL USING (auth.role() = 'service_role');

-- POLICY 5: Service role (backend) can access subscriptions
CREATE POLICY "service_role_subscriptions" ON subscriptions
  FOR ALL USING (auth.role() = 'service_role');

-- POLICY 6: Service role (backend) can access bot logs
CREATE POLICY "service_role_bot_logs" ON bot_logs
  FOR ALL USING (auth.role() = 'service_role');

-- ============================================
-- DONE! Database tables created ✅
-- ============================================
-- 
-- Next steps:
-- 1. Create admin user (see instructions below)
-- 2. Verify tables exist (see verification steps)
-- 3. Test with web app login
--

```

**👆 COPY ALL CODE ABOVE 👆**

---

## 📋 STEP-BY-STEP INSTRUCTIONS

### Step 1: Open Supabase SQL Editor

```
1. Go to: https://supabase.com
2. Click your project name
3. Left sidebar → Click "SQL Editor"
4. You see blank text box ← This is where you paste code
```

### Step 2: Copy the Code Above

```
1. Read the BIG CODE SECTION above ☝️
2. Click and drag to select ALL of it
3. Right-click → "Copy" (or Ctrl+C)
4. Make sure you copied EVERYTHING (very long!)
```

### Step 3: Paste Into Supabase

```
1. Click in the empty text box in Supabase SQL Editor
2. Right-click → "Paste" (or Ctrl+V)
3. You'll see LOTS of code appear
```

### Step 4: Run the Code

```
1. Look for blue button that says "Run"
2. Click it! ▶️
3. Wait 5-10 seconds...
4. You should see: "Success! (4 queries executed)"
5. If you see ERROR, read the error message → fix it → try again
```

---

## ✅ VERIFY IT WORKED

### Check 1: See the Tables

```
1. In Supabase left sidebar
2. Click "Table Editor"
3. You should see 4 tables:
   ✓ profiles
   ✓ payments
   ✓ subscriptions
   ✓ bot_logs
```

### Check 2: Click Each Table

```
For EACH table:
1. Click the table name
2. You see column names:
   - profiles: id, email, name, role, lifetime, created_at, updated_at
   - payments: id, event, data, customer_email, amount, status, received_at
   - subscriptions: id, email, plan, status, amount, started_at, ended_at
   - bot_logs: id, event, payload, created_at
3. If you see these columns → ✅ WORKING!
```

### Check 3: Verify RLS (Security)

```
1. Click "profiles" table
2. Click "Policies" tab
3. You should see policy names:
   - users_read_own_profile
   - users_update_own_profile
   - admins_read_all_profiles
4. If you see them → ✅ SECURITY ON!
```

---

## 🎖️ CREATE YOUR ADMIN USER

**AFTER running the SQL above**, do this:

### Step 1: Create Admin Account in Supabase Auth

```
1. Go to Supabase dashboard
2. Left sidebar → "Authentication"
3. Click "Users" tab
4. Click "Add User" button
5. Email: admin@yourdomain.com (change yourdomain!)
6. Password: Something secure (save it!)
7. Click "Create User"
```

### Step 2: Make Them Admin in Database

```
1. Go back to "SQL Editor"
2. Run this code (change email to your email):

---
```sql
INSERT INTO profiles (id, email, name, role, lifetime) 
SELECT id, email, 'Super Admin', 'admin', true 
FROM auth.users WHERE email = 'admin@yourdomain.com';
```

3. Click "Run" ▶️
4. If you see "1 row inserted" → ✅ Admin created!
```

---

## 🧪 TEST IT WORKS

### Test 1: Check Admin Profile Created

```
1. Go to SQL Editor
2. Run this:

---
```sql
SELECT * FROM profiles WHERE role = 'admin';
```

3. You should see your admin user!
```

### Test 2: Check Security Works

```
1. Go to SQL Editor
2. Run this:

---
```sql
SELECT * FROM payments;
```

3. You should see 0 rows (no payments yet)
4. This is OK! ✅
```

### Test 3: Insert Test Payment

```
1. Go to SQL Editor
2. Run this:

---
```sql
INSERT INTO payments (event, customer_email, amount, status)
VALUES ('charge.success', 'admin@yourdomain.com', 100000, 'success');
```

3. You should see "1 row inserted" ✅
```

---

## 🚨 TROUBLESHOOTING

### Problem: "Error: relation profiles already exists"

**This means:** Table already exists (probably from an old run)

**Fix:**
```
1. Delete old tables first:
   - Go to SQL Editor
   - Run: DROP TABLE IF EXISTS profiles CASCADE;
   - Run: DROP TABLE IF EXISTS payments CASCADE;
   - Run: DROP TABLE IF EXISTS subscriptions CASCADE;
   - Run: DROP TABLE IF EXISTS bot_logs CASCADE;

2. Then paste the full code again

3. Click "Run" ✅
```

### Problem: "Error: syntax error"

**This means:** You copied the code wrong or there's a typo

**Fix:**
```
1. Delete everything in the SQL editor
2. Copy the code above VERY carefully
3. Make sure you got EVERYTHING
4. Paste it again
5. Click "Run" ✅
```

### Problem: "Error: permission denied"

**This means:** Your Supabase account doesn't have permission

**Fix:**
```
1. Make sure you're logged in
2. Make sure it's YOUR project
3. Go to Project Settings → Check you're the owner
4. Try again ✅
```

### Problem: I can see tables but RLS policies missing

**This means:** First part worked, security part didn't

**Fix:**
```
1. Go to SQL Editor
2. Scroll down in the code above
3. Copy ONLY the "SECURITY POLICIES" section
4. Paste and run
5. The cursor at line that failed:

   Look for: CREATE POLICY "users_read_own_profile"
   
   Copy JUST that section:
   
   CREATE POLICY "users_read_own_profile" ON profiles
     FOR SELECT USING (auth.uid() = id);
   
6. Run again ✅
```

---

## 📊 DATABASE DIAGRAM

### What Each Table Does:

```
┌─────────────────────────────────────────────────────┐
│          PROFILES TABLE (Users)                     │
├─────────────────────────────────────────────────────┤
│ id        │ Email ID (unique number)                │
│ email     │ User's email address                    │
│ name      │ User's real name                        │
│ role      │ Is user: admin, user, vip, or premium? │
│ lifetime  │ TRUE = Has lifetime access              │
│ dates     │ When created / last updated             │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│         PAYMENTS TABLE (Money History)              │
├─────────────────────────────────────────────────────┤
│ id               │ Payment ID (unique number)       │
│ event            │ What happened? (charge.success)  │
│ data             │ JSON data from Paystack          │
│ customer_email   │ Who paid?                        │
│ amount           │ How much? (in cents)             │
│ status           │ Is it: success, pending, failed? │
│ received_at      │ When we got the payment?         │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│      SUBSCRIPTIONS TABLE (Who Has Access?)          │
├─────────────────────────────────────────────────────┤
│ id        │ Subscription ID (unique number)         │
│ email     │ Whose subscription?                     │
│ plan      │ What plan? (lifetime, monthly, etc.)    │
│ status    │ Is it: active, revoked, or expired?     │
│ amount    │ How much did they pay?                  │
│ dates     │ When started / when ends?               │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│        BOT_LOGS TABLE (Robot's Activity)            │
├─────────────────────────────────────────────────────┤
│ id        │ Log ID (unique number)                  │
│ event     │ What did bot do? (trade_open, error)    │
│ payload   │ JSON data about what happened          │
│ created_at│ When did this happen?                  │
└─────────────────────────────────────────────────────┘

How Tables Connect:
   
   profiles ──→ payments ──→ (user paid for subscription)
          │
          └──→ subscriptions ──→ (user has access)

   bot_logs ──→ (separate, logs bot trades)
```

---

## 🔐 WHAT IS ROW-LEVEL SECURITY (RLS)?

Like a **lock on each file in your filing cabinet**:

```
Filing Cabinet (Database)
├── John's Folder 🔒 (Only John can open)
│   ├── John's Profile
│   ├── John's Payments
│   └── John's Subscription
│
├── Sarah's Folder 🔒 (Only Sarah can open)
│   ├── Sarah's Profile
│   ├── Sarah's Payments
│   └── Sarah's Subscription
│
└── Payments Folder 🔒 (Only Admin & Bot can see)
    ├── John paid $100
    └── Sarah paid $100
```

**Without RLS:** Anyone can read anyone's data! 😱
**With RLS:** Each person can only see their own data! 😊

---

## ✨ COMPLETE CHECKLIST

Before you're DONE, check these:

```
Supabase Setup:
☐ Created Supabase project (https://supabase.com)
☐ Copied project URL
☐ Copied anon key
☐ Copied service role key

Database Creation:
☐ Went to SQL Editor
☐ Copied code above
☐ Pasted into Supabase
☐ Clicked "Run"
☐ Saw "Success! (X queries executed)"

Verification:
☐ Table Editor shows 4 tables
☐ profiles table has columns
☐ payments table has columns
☐ subscriptions table has columns
☐ bot_logs table has columns
☐ Each table has RLS policies enabled

Admin User:
☐ Created admin@yourdomain.com in Authentication
☐ Ran INSERT query to add to profiles table
☐ Ran SELECT query and saw admin user

Testing:
☐ Inserted test payment
☐ Queried payment and saw it
☐ No errors during any steps

.env File:
☐ Added NEXT_PUBLIC_SUPABASE_URL
☐ Added NEXT_PUBLIC_SUPABASE_ANON_KEY
☐ Added SUPABASE_SERVICE_ROLE_KEY
```

---

## 🎉 YOU'RE DONE!

Your database is now **fully set up** with:
- ✅ 4 tables created
- ✅ Security policies enabled
- ✅ Admin user created
- ✅ Ready for web app!

**Next Steps:**
1. Add Supabase keys to `.env` file
2. Run web app: `npm run dev`
3. Go to login page
4. Sign in with admin account
5. See admin dashboard! 🎊

---

## 💡 REMEMBER

- **Profiles** = Who uses the system
- **Payments** = Proof they paid
- **Subscriptions** = Who has access right now
- **Bot Logs** = What the robot is doing
- **RLS** = Security (lock on files)

**Simple, secure, and ready!** 🚀


