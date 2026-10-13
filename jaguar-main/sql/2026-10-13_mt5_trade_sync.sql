-- MT5 Trade History & Performance Sync (cloud REST bridge).
-- Safe to re-run: every statement is guarded with if-not-exists / drop policy if exists.
--
-- Tables:
--   mt5_account_links - one row per MT5 account the platform syncs in the background.
--                       Credentials are encrypted with lib/mt5-crypto.js (AES-256-GCM).
--   trade_history     - one row per CLOSED position (paired IN + OUT deals).
--   pair_analytics    - pre-aggregated pair performance per link / period.
--   mt5_sync_runs     - audit trail for every sync attempt (cron, manual, admin, api).

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- 1. mt5_account_links - sync subscriptions (credentials + cursor + status)
-- ---------------------------------------------------------------------------
create table if not exists public.mt5_account_links (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  email varchar(254),
  login text not null,
  server text not null,
  label text,
  currency text default 'USD',
  leverage integer,
  provider text not null default 'metaapi',
  bridge_account_id text,
  bridge_region text,
  provisioning_status text not null default 'pending',
  provisioning_error text,
  sync_enabled boolean not null default true,
  sync_status text not null default 'idle',
  sync_error text,
  last_synced_at timestamptz,
  last_deal_time timestamptz,
  last_sync_deals integer not null default 0,
  total_synced_deals integer not null default 0,
  sync_lookback_days integer not null default 120,
  password_encrypted text,
  password_iv text,
  password_tag text,
  password_last4 text,
  source_submission_id uuid references public.mt5_submissions(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.mt5_account_links
  add column if not exists bridge_region text,
  add column if not exists leverage integer,
  add column if not exists total_synced_deals integer not null default 0,
  add column if not exists sync_lookback_days integer not null default 120;

create index if not exists idx_mt5_account_links_user on public.mt5_account_links(user_id);
create index if not exists idx_mt5_account_links_login on public.mt5_account_links(login);
create index if not exists idx_mt5_account_links_sync
  on public.mt5_account_links(sync_enabled, sync_status);

create unique index if not exists idx_mt5_account_links_user_login
  on public.mt5_account_links(user_id, login, server)
  where user_id is not null;

-- ---------------------------------------------------------------------------
-- 2. trade_history - one row per CLOSED position
-- ---------------------------------------------------------------------------
create table if not exists public.trade_history (
  id uuid primary key default gen_random_uuid(),
  link_id uuid references public.mt5_account_links(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  account_login text not null,
  server text,
  position_id text,
  deal_ticket text not null,
  open_ticket text,
  symbol text not null,
  side text not null check (side in ('buy', 'sell')),
  volume numeric(18, 4) default 0,
  open_price numeric(18, 8),
  close_price numeric(18, 8),
  open_time timestamptz,
  close_time timestamptz not null,
  duration_seconds integer,
  pips numeric(18, 2),
  profit numeric(18, 2) default 0,
  commission numeric(18, 2) default 0,
  swap numeric(18, 2) default 0,
  storage numeric(18, 2) default 0,
  net_pnl numeric(18, 2) default 0,
  exit_reason text not null default 'OTHER',
  exit_source text default 'unknown',
  magic integer,
  comment text,
  broker_comment text,
  source text default 'metaapi',
  period varchar(7) not null,
  raw jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_trade_history_link_deal
  on public.trade_history(link_id, deal_ticket);

create index if not exists idx_trade_history_user_time
  on public.trade_history(user_id, close_time desc);
create index if not exists idx_trade_history_link_time
  on public.trade_history(link_id, close_time desc);
create index if not exists idx_trade_history_symbol
  on public.trade_history(user_id, symbol);
create index if not exists idx_trade_history_period
  on public.trade_history(user_id, period);
create index if not exists idx_trade_history_exit_reason
  on public.trade_history(user_id, exit_reason);

-- ---------------------------------------------------------------------------
-- 3. pair_analytics - pre-aggregated pair performance per link / period
-- ---------------------------------------------------------------------------
create table if not exists public.pair_analytics (
  id uuid primary key default gen_random_uuid(),
  link_id uuid references public.mt5_account_links(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  account_login text,
  period varchar(7) not null default 'all',
  symbol text not null,
  trades integer not null default 0,
  wins integer not null default 0,
  losses integer not null default 0,
  breakeven integer not null default 0,
  win_rate numeric(6, 2) default 0,
  volume numeric(18, 4) default 0,
  gross_profit numeric(18, 2) default 0,
  gross_loss numeric(18, 2) default 0,
  net_pnl numeric(18, 2) default 0,
  profit_factor numeric(12, 4),
  pips numeric(18, 2) default 0,
  avg_win numeric(18, 2) default 0,
  avg_loss numeric(18, 2) default 0,
  best_trade numeric(18, 2) default 0,
  worst_trade numeric(18, 2) default 0,
  tp_trades integer not null default 0,
  sl_trades integer not null default 0,
  manual_trades integer not null default 0,
  ea_trades integer not null default 0,
  stop_out_trades integer not null default 0,
  other_trades integer not null default 0,
  first_trade_at timestamptz,
  last_trade_at timestamptz,
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_pair_analytics_unique
  on public.pair_analytics(link_id, period, symbol);
create index if not exists idx_pair_analytics_user
  on public.pair_analytics(user_id, period);
create index if not exists idx_pair_analytics_symbol
  on public.pair_analytics(user_id, symbol);

-- ---------------------------------------------------------------------------
-- 4. mt5_sync_runs - audit trail per sync attempt
-- ---------------------------------------------------------------------------
create table if not exists public.mt5_sync_runs (
  id uuid primary key default gen_random_uuid(),
  link_id uuid references public.mt5_account_links(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  account_login text,
  trigger text not null default 'cron',
  status text not null default 'success',
  provider text,
  window_from timestamptz,
  window_to timestamptz,
  deals_received integer not null default 0,
  trades_inserted integer not null default 0,
  trades_updated integer not null default 0,
  trades_skipped integer not null default 0,
  analytics_rows integer not null default 0,
  duration_ms integer,
  error text,
  context jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_mt5_sync_runs_link
  on public.mt5_sync_runs(link_id, created_at desc);
create index if not exists idx_mt5_sync_runs_status
  on public.mt5_sync_runs(status, created_at desc);

-- ---------------------------------------------------------------------------
-- 5. RLS - users read their own rows, admins read everything.
--    All writes go through the service role (sync service / admin API).
-- ---------------------------------------------------------------------------
alter table public.mt5_account_links enable row level security;
alter table public.trade_history enable row level security;
alter table public.pair_analytics enable row level security;
alter table public.mt5_sync_runs enable row level security;

drop policy if exists "mt5_account_links_select_own" on public.mt5_account_links;
create policy "mt5_account_links_select_own" on public.mt5_account_links
  for select using (user_id = auth.uid() or exists (
    select 1 from public.profiles p where p.id = auth.uid() and lower(coalesce(p.role, '')) = 'admin'
  ));

drop policy if exists "trade_history_select_own" on public.trade_history;
create policy "trade_history_select_own" on public.trade_history
  for select using (user_id = auth.uid() or exists (
    select 1 from public.profiles p where p.id = auth.uid() and lower(coalesce(p.role, '')) = 'admin'
  ));

drop policy if exists "pair_analytics_select_own" on public.pair_analytics;
create policy "pair_analytics_select_own" on public.pair_analytics
  for select using (user_id = auth.uid() or exists (
    select 1 from public.profiles p where p.id = auth.uid() and lower(coalesce(p.role, '')) = 'admin'
  ));

drop policy if exists "mt5_sync_runs_select_own" on public.mt5_sync_runs;
create policy "mt5_sync_runs_select_own" on public.mt5_sync_runs
  for select using (user_id = auth.uid() or exists (
    select 1 from public.profiles p where p.id = auth.uid() and lower(coalesce(p.role, '')) = 'admin'
  ));

comment on table public.mt5_account_links is 'Background MT5 sync subscriptions; passwords are AES-256-GCM encrypted (lib/mt5-crypto.js).';
comment on table public.trade_history is 'Closed MT5 positions (paired IN/OUT deals) synced by services/mt5Sync.js.';
comment on table public.pair_analytics is 'Pre-aggregated per-symbol performance; period = all | YYYY-MM.';
comment on table public.mt5_sync_runs is 'Sync audit log written by services/mt5Sync.js.';
comment on column public.trade_history.deal_ticket is 'Stable sync key: MT5 position id when the bridge provides one, else the final closing deal ticket.';
comment on column public.trade_history.net_pnl is 'profit + commission + swap (swap falls back to storage when the bridge omits swap).';
comment on column public.trade_history.exit_reason is 'SL | TP | MANUAL | EA | STOP_OUT | ROLLOVER | OTHER (lib/mt5-exit-reason.js).';
comment on column public.trade_history.exit_source is 'Classification evidence: trade_reason | label | comment | heuristic | unknown.';
comment on column public.mt5_account_links.last_deal_time is 'Sync cursor: broker time of the newest synced deal.';
comment on column public.mt5_account_links.password_encrypted is 'AES-256-GCM ciphertext (lib/mt5-crypto.js); never returned by any API.';



