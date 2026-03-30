-- ================================================
-- Intelligence System Tables (CIS + Market Data)
-- Project: Jaguar / KingsBalfx
-- Created: March 29, 2026
-- Purpose: Store all CIS decisions, market conditions, 
--          and trading intelligence data
-- ================================================

-- ===============================================
-- TABLE 1: Market Condition Analysis (Per Pair)
-- ===============================================
-- Stores volatility analysis for each trading pair
-- Updated after each market analysis
-- Used for: Market condition scoring, volatility tracking

CREATE TABLE IF NOT EXISTS public.market_conditions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol TEXT NOT NULL,
  analyzed_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Volatility Metrics
  volatility_index NUMERIC(3,2),           -- 0.0 to 1.0
  market_condition TEXT,                   -- 'volatile', 'consolidating', 'stable'
  atr NUMERIC(10,6),                       -- Average True Range value
  atr_percent NUMERIC(6,3),                -- ATR as % of current price
  
  -- Range Analysis
  recent_range NUMERIC(10,6),              -- High-Low of last 20 bars
  recent_range_percent NUMERIC(6,3),      -- Range as % of price
  consolidation_strength NUMERIC(3,2),    -- 0.0-1.0, how tight is range?
  
  -- Trend Analysis
  volatility_trend TEXT,                   -- 'increasing', 'decreasing', 'stable'
  
  -- Trading Recommendations
  opportunity_type TEXT,                   -- 'breakout', 'range', 'balanced'
  position_size_adjustment NUMERIC(3,2),  -- 0.8-1.0 (multiply normal size)
  confidence_adjustment NUMERIC(3,2),     -- -0.1 to +0.1 (add to CIS score)
  trades_should_avoid_in_last_hours INT,  -- 0-4 (if high volatility)
  
  -- Metadata
  timeframe TEXT DEFAULT 'H1',             -- 'H1', 'M15', 'M5', 'D1'
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  CONSTRAINT market_conditions_unique UNIQUE(symbol, timeframe, analyzed_at)
);

CREATE INDEX idx_market_conditions_symbol ON public.market_conditions(symbol);
CREATE INDEX idx_market_conditions_analyzed_at ON public.market_conditions(analyzed_at DESC);
CREATE INDEX idx_market_conditions_volatility ON public.market_conditions(volatility_index);


-- ===============================================
-- TABLE 2: CIS Decisions (Central Intelligence)
-- ===============================================
-- Stores every trading decision made by the CIS system
-- Includes all component scores and reasoning
-- Used for: Decision history, performance tracking, learning

CREATE TABLE IF NOT EXISTS public.cis_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  
  -- Trade Details
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL,                 -- 'BUY' or 'SELL'
  timeframe TEXT DEFAULT 'H1',
  
  -- Prices
  entry_price NUMERIC(12,5),
  stop_loss NUMERIC(12,5),
  take_profit NUMERIC(12,5),
  
  -- Decision Verdict
  final_verdict TEXT NOT NULL,             -- 'TRADE', 'WAIT', 'AVOID'
  confidence_score NUMERIC(3,2),           -- 0.0-1.0 final score
  position_size NUMERIC(8,4),              -- Position size in lots (0.01, 0.1, etc)
  stop_loss_size INT,                      -- Stop loss in pips
  
  -- Component Scores (each 0-1)
  setup_quality_score NUMERIC(3,2),        -- Technical setup quality
  market_condition_score NUMERIC(3,2),    -- Market favorability
  risk_profile_score NUMERIC(3,2),         -- Account safety
  timing_score NUMERIC(3,2),               -- Session/timing appropriateness
  
  -- Risk-Reward Analysis
  risk_reward_ratio NUMERIC(4,2),          -- Calculated R:R (e.g., 1.50)
  account_exposure_percent NUMERIC(5,2),  -- Total account exposure %
  
  -- Reasoning & Flags
  reasoning JSONB DEFAULT '{}'::JSONB,                -- Array of reason strings
  red_flags JSONB DEFAULT '{}'::JSONB,                -- Array of warning strings
  validation_checks JSONB DEFAULT '{}'::JSONB,       -- All validation results
  
  -- Execution Status
  executed BOOLEAN DEFAULT FALSE,
  execution_timestamp TIMESTAMPTZ,
  actual_entry_price NUMERIC(12,5),       -- If executed, actual fill price
  status TEXT DEFAULT 'pending',           -- 'pending', 'executed', 'cancelled', 'expired'
  
  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cis_decisions_symbol ON public.cis_decisions(symbol);
CREATE INDEX idx_cis_decisions_verdict ON public.cis_decisions(final_verdict);
CREATE INDEX idx_cis_decisions_confidence ON public.cis_decisions(confidence_score DESC);
CREATE INDEX idx_cis_decisions_created_at ON public.cis_decisions(created_at DESC);
CREATE INDEX idx_cis_decisions_user_id ON public.cis_decisions(user_id);
CREATE INDEX idx_cis_decisions_executed ON public.cis_decisions(executed);


-- ===============================================
-- TABLE 3: Trade Execution Results
-- ===============================================
-- Tracks actual trade execution and results
-- Links to CIS decision that triggered it
-- Used for: Performance analysis, win rates, learning

CREATE TABLE IF NOT EXISTS public.trade_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cis_decision_id UUID NOT NULL REFERENCES public.cis_decisions(id) ON DELETE CASCADE,
  user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  
  -- Trade Details
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL,
  
  -- Execution Details
  order_id BIGINT,                         -- MT5 order ID
  entry_price NUMERIC(12,5),
  entry_timestamp TIMESTAMPTZ,
  
  stop_loss NUMERIC(12,5),
  take_profit NUMERIC(12,5),
  position_size NUMERIC(8,4),              -- Lots
  
  -- Exit Details
  exit_price NUMERIC(12,5),
  exit_timestamp TIMESTAMPTZ,
  exit_reason TEXT,                        -- 'tp_hit', 'sl_hit', 'manual_close', 'error'
  
  -- Results
  pips_move INT,                           -- How many pips price moved
  profit_loss NUMERIC(12,2),               -- $ P&L
  profit_loss_percent NUMERIC(6,2),        -- % return
  win BOOLEAN,                              -- true if winning trade
  
  -- Duration
  duration_minutes INT,                    -- Time trade was open
  
  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_trade_executions_symbol ON public.trade_executions(symbol);
CREATE INDEX idx_trade_executions_win ON public.trade_executions(win);
CREATE INDEX idx_trade_executions_user_id ON public.trade_executions(user_id);
CREATE INDEX idx_trade_executions_created_at ON public.trade_executions(created_at DESC);
CREATE INDEX idx_trade_executions_cis_id ON public.trade_executions(cis_decision_id);


-- ===============================================
-- TABLE 4: Strategy Performance Metrics
-- ===============================================
-- Aggregated statistics for learning and optimization
-- Updated hourly/daily
-- Used for: Performance dashboard, strategy optimization

CREATE TABLE IF NOT EXISTS public.strategy_performance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  
  -- Time Period
  period_date DATE,                        -- YYYY-MM-DD
  period_type TEXT DEFAULT 'daily',        -- 'hourly', 'daily', 'weekly', 'monthly'
  
  -- Pair-Specific Stats
  symbol TEXT NOT NULL,
  
  -- Volume
  total_trades INT DEFAULT 0,
  winning_trades INT DEFAULT 0,
  losing_trades INT DEFAULT 0,
  win_rate NUMERIC(5,2),                   -- % (e.g., 65.50)
  
  -- Verdict Performance
  trade_verdict_count INT,                 -- How many TRADE verdicts
  trade_verdict_wins INT,                  -- How many won
  trade_verdict_winrate NUMERIC(5,2),     -- Win % on TRADE verdicts
  
  wait_verdict_count INT,
  avoid_verdict_count INT,
  
  -- P&L
  total_profit NUMERIC(12,2),
  total_loss NUMERIC(12,2),
  net_pnl NUMERIC(12,2),
  avg_profit_per_win NUMERIC(10,2),
  avg_loss_per_loss NUMERIC(10,2),
  
  -- Risk Metrics
  largest_loss NUMERIC(12,2),
  largest_win NUMERIC(12,2),
  profit_factor NUMERIC(5,2),              -- Total Wins / Total Losses
  
  -- Confidence Analysis
  avg_confidence_score NUMERIC(3,2),       -- Avg confidence of all trades
  score_vs_winrate NUMERIC(5,2),          -- Correlation between confidence and actual W/L
  
  -- Component Effectiveness
  avg_setup_quality NUMERIC(3,2),
  avg_market_condition NUMERIC(3,2),
  avg_risk_profile NUMERIC(3,2),
  avg_timing NUMERIC(3,2),
  
  -- Metadata
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_strategy_perf_user_symbol ON public.strategy_performance(user_id, symbol);
CREATE INDEX idx_strategy_perf_period ON public.strategy_performance(period_date DESC);
CREATE INDEX idx_strategy_perf_win_rate ON public.strategy_performance(win_rate DESC);


-- ===============================================
-- TABLE 5: Component Score Effectiveness
-- ===============================================
-- Tracks how predictive each component is
-- Used for: Tuning thresholds, learning which factors work best

CREATE TABLE IF NOT EXISTS public.component_effectiveness (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Component
  component_name TEXT NOT NULL,            -- 'setup_quality', 'market_condition', 'risk_profile', 'timing'
  
  -- Score Range (e.g., 0.0-0.2, 0.2-0.4, etc)
  score_min NUMERIC(3,2),
  score_max NUMERIC(3,2),
  
  -- Predictiveness Analysis
  trades_in_range INT DEFAULT 0,
  winning_trades INT DEFAULT 0,
  win_rate NUMERIC(5,2),                   -- Win % when score in this range
  
  -- Profit Impact
  avg_pnl_per_trade NUMERIC(10,2),
  
  -- Assessment
  is_predictive BOOLEAN,                   -- true if win rate correlates with score
  improvement_potential TEXT,              -- 'high', 'medium', 'low'
  
  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_component_effectiveness_name ON public.component_effectiveness(component_name);


-- ===============================================
-- TABLE 6: Validation Check Results
-- ===============================================
-- Detailed record of each validation check performed
-- Used for: Debugging blocked trades, improving validator

CREATE TABLE IF NOT EXISTS public.validation_checks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cis_decision_id UUID NOT NULL REFERENCES public.cis_decisions(id) ON DELETE CASCADE,
  
  -- Check Details
  check_name TEXT NOT NULL,                -- 'broker_connection', 'symbol_valid', etc
  check_result BOOLEAN,                    -- PASS or FAIL
  check_status TEXT,                       -- 'PASS' or 'FAIL'
  message TEXT,                            -- Detailed result message
  
  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_validation_checks_decision ON public.validation_checks(cis_decision_id);
CREATE INDEX idx_validation_checks_result ON public.validation_checks(check_result);


-- ===============================================
-- Auto-Update Timestamps
-- ===============================================

CREATE OR REPLACE FUNCTION update_cis_decisions_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_trade_executions_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_strategy_performance_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_component_effectiveness_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop old triggers if they exist
DROP TRIGGER IF EXISTS update_cis_decisions_timestamp_trigger ON public.cis_decisions;
DROP TRIGGER IF EXISTS update_trade_executions_timestamp_trigger ON public.trade_executions;
DROP TRIGGER IF EXISTS update_strategy_performance_timestamp_trigger ON public.strategy_performance;
DROP TRIGGER IF EXISTS update_component_effectiveness_timestamp_trigger ON public.component_effectiveness;

-- Create triggers
CREATE TRIGGER update_cis_decisions_timestamp_trigger BEFORE UPDATE ON public.cis_decisions
FOR EACH ROW EXECUTE FUNCTION update_cis_decisions_timestamp();

CREATE TRIGGER update_trade_executions_timestamp_trigger BEFORE UPDATE ON public.trade_executions
FOR EACH ROW EXECUTE FUNCTION update_trade_executions_timestamp();

CREATE TRIGGER update_strategy_performance_timestamp_trigger BEFORE UPDATE ON public.strategy_performance
FOR EACH ROW EXECUTE FUNCTION update_strategy_performance_timestamp();

CREATE TRIGGER update_component_effectiveness_timestamp_trigger BEFORE UPDATE ON public.component_effectiveness
FOR EACH ROW EXECUTE FUNCTION update_component_effectiveness_timestamp();


-- ===============================================
-- Row Level Security (RLS)
-- ===============================================

-- Enable RLS on all tables
ALTER TABLE public.market_conditions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cis_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trade_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.strategy_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.component_effectiveness ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.validation_checks ENABLE ROW LEVEL SECURITY;

-- Policy: Users see only their own decisions (if user_id is set)
CREATE POLICY market_conditions_public ON public.market_conditions
  FOR SELECT USING (true);  -- Market data is public

CREATE POLICY cis_decisions_own ON public.cis_decisions
  FOR SELECT USING (user_id = auth.uid() OR user_id IS NULL);

CREATE POLICY cis_decisions_insert ON public.cis_decisions
  FOR INSERT WITH CHECK (user_id = auth.uid() OR user_id IS NULL);

CREATE POLICY trade_executions_own ON public.trade_executions
  FOR SELECT USING (user_id = auth.uid());

CREATE POLICY strategy_performance_own ON public.strategy_performance
  FOR SELECT USING (user_id = auth.uid());

CREATE POLICY validation_checks_own ON public.validation_checks
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.cis_decisions 
      WHERE cis_decisions.id = validation_checks.cis_decision_id 
      AND cis_decisions.user_id = auth.uid()
    )
  );

-- Admin bypass for performance tables
CREATE POLICY component_effectiveness_public ON public.component_effectiveness
  FOR SELECT USING (true);  -- Analytics data is public


-- ===============================================
-- DONE
-- ===============================================
-- Run this entire script in Supabase SQL Editor
-- All tables will be created with indexes and RLS policies
