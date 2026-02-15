"""
DATABASE MIGRATION - Add Pricing Tiers Table
Run in Supabase SQL Editor before deployment
"""

-- Create pricing_tiers table
CREATE TABLE IF NOT EXISTS pricing_tiers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  display_name TEXT NOT NULL,
  price NUMERIC NOT NULL,
  currency TEXT DEFAULT 'NGN',
  billing_cycle TEXT,
  description TEXT,
  features JSONB NOT NULL,
  color TEXT,
  badge TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default pricing tiers
INSERT INTO pricing_tiers (id, name, display_name, price, billing_cycle, description, features, color, badge) VALUES
(
  'free',
  'Free Trial',
  'Trial',
  0,
  NULL,
  'Get started with trading signals',
  '{
    "signals": true,
    "signalQuality": "standard",
    "maxSignalsPerDay": 3,
    "mentorship": false,
    "communityAccess": "limited",
    "lessonAccess": true,
    "lessonFrequency": "weekly",
    "tradingHistory": false,
    "performanceAnalytics": false,
    "prioritySupport": false,
    "botAccess": false,
    "maxConcurrentTrades": 0
  }',
  'yellow',
  'Getting Started'
),
(
  'premium',
  'Premium',
  'Premium',
  90000,
  'monthly',
  'Professional trader toolkit',
  '{
    "signals": true,
    "signalQuality": "premium",
    "maxSignalsPerDay": 15,
    "mentorship": false,
    "communityAccess": "full",
    "lessonAccess": true,
    "lessonFrequency": "daily",
    "tradingHistory": true,
    "performanceAnalytics": true,
    "prioritySupport": true,
    "botAccess": true,
    "maxConcurrentTrades": 5,
    "botUpdates": "weekly"
  }',
  'blue',
  'Most Popular'
),
(
  'vip',
  'VIP',
  'VIP',
  150000,
  'monthly',
  'Elite mentorship & trading',
  '{
    "signals": true,
    "signalQuality": "vip",
    "maxSignalsPerDay": 30,
    "mentorship": true,
    "mentorshipType": "group",
    "groupSessionsPerMonth": 4,
    "communityAccess": "vip",
    "lessonAccess": true,
    "lessonFrequency": "daily",
    "tradingHistory": true,
    "performanceAnalytics": true,
    "prioritySupport": true,
    "botAccess": true,
    "maxConcurrentTrades": 10,
    "botUpdates": "daily",
    "strategyFeedback": true
  }',
  'purple',
  'Elite'
),
(
  'pro',
  'Pro Trader',
  'Pro',
  250000,
  'monthly',
  'Complete professional setup',
  '{
    "signals": true,
    "signalQuality": "pro",
    "maxSignalsPerDay": "unlimited",
    "mentorship": true,
    "mentorshipType": "one-on-one",
    "oneOnOneSessionsPerMonth": 2,
    "groupSessionsPerMonth": 8,
    "communityAccess": "pro",
    "lessonAccess": true,
    "lessonFrequency": "daily",
    "tradingHistory": true,
    "performanceAnalytics": true,
    "advancedAnalytics": true,
    "prioritySupport": true,
    "dedicatedSupport": true,
    "botAccess": true,
    "maxConcurrentTrades": 20,
    "botUpdates": "hourly",
    "strategyFeedback": true,
    "customStrategies": true,
    "apiAccess": true
  }',
  'indigo',
  'Professional'
),
(
  'lifetime',
  'Lifetime',
  'Lifetime',
  500000,
  'one-time',
  'Lifetime access to everything',
  '{
    "signals": true,
    "signalQuality": "pro",
    "maxSignalsPerDay": "unlimited",
    "mentorship": true,
    "mentorshipType": "one-on-one",
    "oneOnOneSessionsPerMonth": "unlimited",
    "groupSessionsPerMonth": "unlimited",
    "communityAccess": "lifetime",
    "lessonAccess": true,
    "lessonFrequency": "daily",
    "tradingHistory": true,
    "performanceAnalytics": true,
    "advancedAnalytics": true,
    "prioritySupport": true,
    "dedicatedSupport": true,
    "botAccess": true,
    "maxConcurrentTrades": "unlimited",
    "botUpdates": "real-time",
    "strategyFeedback": true,
    "customStrategies": true,
    "apiAccess": true,
    "futureUpdates": true
  }',
  'pink',
  'Lifetime'
);

-- Add bot_tier columns to profiles table if not exists
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS bot_tier TEXT DEFAULT 'free';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS bot_max_signals_per_day INTEGER DEFAULT 0;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS bot_max_concurrent_trades INTEGER DEFAULT 0;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS bot_signal_quality TEXT DEFAULT 'none';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS bot_tier_updated_at TIMESTAMP;

-- Create index for pricing tier lookups
CREATE INDEX IF NOT EXISTS idx_pricing_tiers_id ON pricing_tiers(id);
CREATE INDEX IF NOT EXISTS idx_profiles_bot_tier ON profiles(bot_tier);

-- Create bot_signals table for tracking generated signals
CREATE TABLE IF NOT EXISTS bot_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL,
  entry_price NUMERIC NOT NULL,
  stop_loss NUMERIC NOT NULL,
  take_profit NUMERIC NOT NULL,
  signal_quality TEXT NOT NULL,
  confidence NUMERIC,
  reason JSONB,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  executed_at TIMESTAMP,
  closed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bot_signals_user_id ON bot_signals(user_id);
CREATE INDEX IF NOT EXISTS idx_bot_signals_symbol ON bot_signals(symbol);
CREATE INDEX IF NOT EXISTS idx_bot_signals_created_at ON bot_signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bot_signals_status ON bot_signals(status);

-- Create bot_errors table for error logging
CREATE TABLE IF NOT EXISTS bot_errors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  error_type TEXT NOT NULL,
  error_message TEXT,
  stack_trace TEXT,
  context JSONB,
  severity TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bot_errors_type ON bot_errors(error_type);
CREATE INDEX IF NOT EXISTS idx_bot_errors_created_at ON bot_errors(created_at DESC);

-- Create mentorship_sessions table
CREATE TABLE IF NOT EXISTS mentorship_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mentor_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  student_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  session_type TEXT NOT NULL,
  scheduled_at TIMESTAMP NOT NULL,
  duration_minutes INTEGER,
  status TEXT DEFAULT 'scheduled',
  meeting_url TEXT,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mentorship_sessions_mentor ON mentorship_sessions(mentor_id);
CREATE INDEX IF NOT EXISTS idx_mentorship_sessions_student ON mentorship_sessions(student_id);
CREATE INDEX IF NOT EXISTS idx_mentorship_sessions_scheduled ON mentorship_sessions(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_mentorship_sessions_status ON mentorship_sessions(status);

-- Add Column if profile table doesn't have preferred_mentor
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS preferred_mentor UUID REFERENCES auth.users(id) ON DELETE SET NULL;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'UTC';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS receive_notifications BOOLEAN DEFAULT true;

-- Update timestamps automatically
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_pricing_tiers_timestamp ON pricing_tiers;
CREATE TRIGGER update_pricing_tiers_timestamp
BEFORE UPDATE ON pricing_tiers
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

DROP TRIGGER IF EXISTS update_mentorship_sessions_timestamp ON mentorship_sessions;
CREATE TRIGGER update_mentorship_sessions_timestamp
BEFORE UPDATE ON mentorship_sessions
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

-- Verification queries
SELECT 'Pricing Tiers' as table_name, COUNT(*) as count FROM pricing_tiers;
SELECT 'Bot Signals' as table_name, COUNT(*) as count FROM bot_signals;
SELECT 'Bot Errors' as table_name, COUNT(*) as count FROM bot_errors;
SELECT 'Mentorship Sessions' as table_name, COUNT(*) as count FROM mentorship_sessions;
