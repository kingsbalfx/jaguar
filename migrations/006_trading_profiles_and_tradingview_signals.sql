-- Migration 006: Trading profiles + TradingView webhook signals

-- 1) Per-user trading profile (aggressive/balanced/conservative)
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS trading_profile TEXT DEFAULT 'balanced';

-- 2) Per-user TradingView webhook token (used to map unauthenticated webhooks -> user_id)
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS tradingview_webhook_token TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_tradingview_webhook_token
  ON public.profiles(tradingview_webhook_token)
  WHERE tradingview_webhook_token IS NOT NULL;

-- 3) TradingView signal inbox (website receives -> bot consumes)
CREATE TABLE IF NOT EXISTS public.tradingview_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL, -- 'BUY' or 'SELL'
  payload JSONB DEFAULT '{}'::JSONB,
  status TEXT DEFAULT 'pending', -- 'pending' | 'processed' | 'rejected'
  received_at TIMESTAMPTZ DEFAULT NOW(),
  processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tradingview_signals_user_id ON public.tradingview_signals(user_id);
CREATE INDEX IF NOT EXISTS idx_tradingview_signals_status ON public.tradingview_signals(status);
CREATE INDEX IF NOT EXISTS idx_tradingview_signals_received_at ON public.tradingview_signals(received_at DESC);

ALTER TABLE public.tradingview_signals ENABLE ROW LEVEL SECURITY;

-- Service role can fully manage signals (webhook receiver + bot engine)
CREATE POLICY "service_role_tradingview_signals" ON public.tradingview_signals
  FOR ALL USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- Optional: users can read their own signals (dashboard visibility)
CREATE POLICY "users_read_own_tradingview_signals" ON public.tradingview_signals
  FOR SELECT USING (auth.uid() = user_id);

