# Supabase RLS (Row-Level Security) Setup

Run these SQL commands in the Supabase SQL editor to enable RLS on all tables:

```sql
-- Enable RLS on profiles table
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Allow users to read their own profile
CREATE POLICY "users_read_own_profile" ON profiles
  FOR SELECT USING (auth.uid() = id);

-- Allow users to update their own profile
CREATE POLICY "users_update_own_profile" ON profiles
  FOR UPDATE USING (auth.uid() = id);

-- Enable RLS on payments table
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

-- Only service role can access payments (no user access)
CREATE POLICY "service_role_all_payments" ON payments
  FOR SELECT USING (auth.role() = 'service_role');

-- Enable RLS on subscriptions table
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Only service role can access subscriptions
CREATE POLICY "service_role_all_subscriptions" ON subscriptions
  FOR SELECT USING (auth.role() = 'service_role');

-- Enable RLS on bot_logs table
ALTER TABLE bot_logs ENABLE ROW LEVEL SECURITY;

-- Only service role can access bot logs
CREATE POLICY "service_role_all_bot_logs" ON bot_logs
  FOR SELECT USING (auth.role() = 'service_role');
```

After running these policies, test:
1. Sign in as a regular user and verify they can only see their own profile
2. Verify admin users can see all profiles (if admin table access is desired, add another policy)
3. Verify regular users cannot access payments, subscriptions, or bot_logs tables
a 