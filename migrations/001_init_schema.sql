-- Database Migrations for Supabase
-- Run these migrations in order to initialize the database schema

-- Migration 001: Create profiles table
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

-- Migration 002: Create payments table
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

-- Migration 003: Create subscriptions table
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

-- Migration 004: Create bot_logs table
CREATE TABLE IF NOT EXISTS bot_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event VARCHAR(255) NOT NULL,
  payload JSONB DEFAULT '{}',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_bot_logs_event ON bot_logs(event);
CREATE INDEX idx_bot_logs_created_at ON bot_logs(created_at DESC);

-- Migration 005: Enable RLS (Row-Level Security) on tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bot_logs ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can read their own profile
CREATE POLICY "users_read_own_profile" ON profiles
  FOR SELECT USING (auth.uid() = id);

-- RLS Policy: Users can update their own profile
CREATE POLICY "users_update_own_profile" ON profiles
  FOR UPDATE USING (auth.uid() = id);

-- RLS Policy: Admins can read all profiles
CREATE POLICY "admins_read_all_profiles" ON profiles
  FOR SELECT USING (
    auth.role() = 'service_role' OR 
    EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role = 'admin')
  );

-- RLS Policy: Service role has full access to payments
CREATE POLICY "service_role_payments" ON payments
  FOR SELECT USING (auth.role() = 'service_role');

-- RLS Policy: Service role has full access to subscriptions
CREATE POLICY "service_role_subscriptions" ON subscriptions
  FOR SELECT USING (auth.role() = 'service_role');

-- RLS Policy: Service role has full access to bot_logs
CREATE POLICY "service_role_bot_logs" ON bot_logs
  FOR SELECT USING (auth.role() = 'service_role');

-- Populate a test admin user (CHANGE EMAIL AND PASSWORD IN PRODUCTION)
-- INSERT INTO profiles (id, email, name, role, lifetime) 
-- SELECT id, email, 'Super Admin', 'admin', true 
-- FROM auth.users WHERE email = 'admin@example.com';
