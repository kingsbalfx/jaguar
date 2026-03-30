-- ================================================================
-- COPY THIS ENTIRE SCRIPT INTO SUPABASE SQL EDITOR & RUN
-- Intelligence System Tables for Jaguar Trading Bot
-- ================================================================

-- TABLE 1: Market Conditions (Volatility Analysis)
CREATE TABLE IF NOT EXISTS public.market_conditions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol TEXT NOT NULL,
  analyzed_at TIMESTAMPTZ DEFAULT NOW(),
  volatility_index NUMERIC(3,2),
  market_condition TEXT,
  atr NUMERIC(10,6),
  atr_percent NUMERIC(6,3),
  recent_range NUMERIC(10,6),
  recent_range_percent NUMERIC(6,3),
  consolidation_strength NUMERIC(3,2),
  volatility_trend TEXT,
  opportunity_type TEXT,
  position_size_adjustment NUMERIC(3,2),
  confidence_adjustment NUMERIC(3,2),
  trades_should_avoid_in_last_hours INT,
  timeframe TEXT DEFAULT 'H1',
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT market_conditions_unique UNIQUE(symbol, timeframe, analyzed_at)
);

CREATE INDEX IF NOT EXISTS idx_market_conditions_symbol ON public.market_conditions(symbol);
CREATE INDEX IF NOT EXISTS idx_market_conditions_analyzed_at ON public.market_conditions(analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_market_conditions_volatility ON public.market_conditions(volatility_index);

ALTER TABLE public.market_conditions ENABLE ROW LEVEL SECURITY;
CREATE POLICY market_conditions_public ON public.market_conditions FOR SELECT USING (true);

-- TABLE 2: CIS Decisions (Trading Decisions)
CREATE TABLE IF NOT EXISTS public.cis_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL,
  timeframe TEXT DEFAULT 'H1',
  entry_price NUMERIC(12,5),
  stop_loss NUMERIC(12,5),
  take_profit NUMERIC(12,5),
  final_verdict TEXT NOT NULL,
  confidence_score NUMERIC(3,2),
  position_size NUMERIC(8,4),
  stop_loss_size INT,
  setup_quality_score NUMERIC(3,2),
  market_condition_score NUMERIC(3,2),
  risk_profile_score NUMERIC(3,2),
  timing_score NUMERIC(3,2),
  risk_reward_ratio NUMERIC(4,2),
  account_exposure_percent NUMERIC(5,2),
  reasoning JSONB DEFAULT '{}'::JSONB,
  red_flags JSONB DEFAULT '{}'::JSONB,
  validation_checks JSONB DEFAULT '{}'::JSONB,
  executed BOOLEAN DEFAULT FALSE,
  execution_timestamp TIMESTAMPTZ,
  actual_entry_price NUMERIC(12,5),
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cis_decisions_symbol ON public.cis_decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_cis_decisions_verdict ON public.cis_decisions(final_verdict);
CREATE INDEX IF NOT EXISTS idx_cis_decisions_confidence ON public.cis_decisions(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_cis_decisions_created_at ON public.cis_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cis_decisions_user_id ON public.cis_decisions(user_id);

ALTER TABLE public.cis_decisions ENABLE ROW LEVEL SECURITY;
CREATE POLICY cis_decisions_own ON public.cis_decisions FOR SELECT USING (user_id = auth.uid() OR user_id IS NULL);
CREATE POLICY cis_decisions_insert ON public.cis_decisions FOR INSERT WITH CHECK (user_id = auth.uid() OR user_id IS NULL);

-- TABLE 3: Trade Executions (Actual Trade Results)
CREATE TABLE IF NOT EXISTS public.trade_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cis_decision_id UUID NOT NULL REFERENCES public.cis_decisions(id) ON DELETE CASCADE,
  user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL,
  order_id BIGINT,
  entry_price NUMERIC(12,5),
  entry_timestamp TIMESTAMPTZ,
  stop_loss NUMERIC(12,5),
  take_profit NUMERIC(12,5),
  position_size NUMERIC(8,4),
  exit_price NUMERIC(12,5),
  exit_timestamp TIMESTAMPTZ,
  exit_reason TEXT,
  pips_move INT,
  profit_loss NUMERIC(12,2),
  profit_loss_percent NUMERIC(6,2),
  win BOOLEAN,
  duration_minutes INT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trade_executions_symbol ON public.trade_executions(symbol);
CREATE INDEX IF NOT EXISTS idx_trade_executions_win ON public.trade_executions(win);
CREATE INDEX IF NOT EXISTS idx_trade_executions_user_id ON public.trade_executions(user_id);
CREATE INDEX IF NOT EXISTS idx_trade_executions_created_at ON public.trade_executions(created_at DESC);

ALTER TABLE public.trade_executions ENABLE ROW LEVEL SECURITY;
CREATE POLICY trade_executions_own ON public.trade_executions FOR SELECT USING (user_id = auth.uid());

-- TABLE 4: Strategy Performance (Daily/Hourly Stats)
CREATE TABLE IF NOT EXISTS public.strategy_performance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  period_date DATE,
  period_type TEXT DEFAULT 'daily',
  symbol TEXT NOT NULL,
  total_trades INT DEFAULT 0,
  winning_trades INT DEFAULT 0,
  losing_trades INT DEFAULT 0,
  win_rate NUMERIC(5,2),
  trade_verdict_count INT,
  trade_verdict_wins INT,
  trade_verdict_winrate NUMERIC(5,2),
  wait_verdict_count INT,
  avoid_verdict_count INT,
  total_profit NUMERIC(12,2),
  total_loss NUMERIC(12,2),
  net_pnl NUMERIC(12,2),
  avg_profit_per_win NUMERIC(10,2),
  avg_loss_per_loss NUMERIC(10,2),
  largest_loss NUMERIC(12,2),
  largest_win NUMERIC(12,2),
  profit_factor NUMERIC(5,2),
  avg_confidence_score NUMERIC(3,2),
  score_vs_winrate NUMERIC(5,2),
  avg_setup_quality NUMERIC(3,2),
  avg_market_condition NUMERIC(3,2),
  avg_risk_profile NUMERIC(3,2),
  avg_timing NUMERIC(3,2),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_perf_user_symbol ON public.strategy_performance(user_id, symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_perf_period ON public.strategy_performance(period_date DESC);

ALTER TABLE public.strategy_performance ENABLE ROW LEVEL SECURITY;
CREATE POLICY strategy_performance_own ON public.strategy_performance FOR SELECT USING (user_id = auth.uid());

-- TABLE 5: Component Effectiveness (Learning Data)
CREATE TABLE IF NOT EXISTS public.component_effectiveness (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  component_name TEXT NOT NULL,
  score_min NUMERIC(3,2),
  score_max NUMERIC(3,2),
  trades_in_range INT DEFAULT 0,
  winning_trades INT DEFAULT 0,
  win_rate NUMERIC(5,2),
  avg_pnl_per_trade NUMERIC(10,2),
  is_predictive BOOLEAN,
  improvement_potential TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_component_effectiveness_name ON public.component_effectiveness(component_name);

ALTER TABLE public.component_effectiveness ENABLE ROW LEVEL SECURITY;
CREATE POLICY component_effectiveness_public ON public.component_effectiveness FOR SELECT USING (true);

-- TABLE 6: Validation Checks (Debug Data)
CREATE TABLE IF NOT EXISTS public.validation_checks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cis_decision_id UUID NOT NULL REFERENCES public.cis_decisions(id) ON DELETE CASCADE,
  check_name TEXT NOT NULL,
  check_result BOOLEAN,
  check_status TEXT,
  message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_validation_checks_decision ON public.validation_checks(cis_decision_id);

ALTER TABLE public.validation_checks ENABLE ROW LEVEL SECURITY;
CREATE POLICY validation_checks_own ON public.validation_checks FOR SELECT USING (
  EXISTS (
    SELECT 1 FROM public.cis_decisions 
    WHERE cis_decisions.id = validation_checks.cis_decision_id 
    AND cis_decisions.user_id = auth.uid()
  )
);

-- END OF SCRIPT
