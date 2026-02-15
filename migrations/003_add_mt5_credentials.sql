-- Migration 003: Store MT5 credentials in Supabase (admin-managed)

CREATE TABLE IF NOT EXISTS mt5_credentials (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  login TEXT NOT NULL,
  password TEXT NOT NULL,
  server TEXT NOT NULL,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_mt5_credentials_active ON mt5_credentials(active);
CREATE INDEX idx_mt5_credentials_updated_at ON mt5_credentials(updated_at DESC);

ALTER TABLE mt5_credentials ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_mt5_credentials" ON mt5_credentials
  FOR ALL USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');
