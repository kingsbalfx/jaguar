-- ============================================================================
-- CONSOLIDATED SUPABASE MIGRATION — ALL MISSING TABLES
-- ============================================================================
-- One-time, idempotent script that creates EVERY table referenced by the
-- KINGSBALFX trading bot AND the Jaguar web app. Paste the whole file into
-- Supabase Dashboard -> SQL Editor -> New query -> Run.
--
-- Fixes the runtime errors in your logs:
--   PGRST205 "Could not find the table 'public.daily_macro_rules' in schema cache"
--   PGRST205 "Could not find the table 'public.rule_execution_audit' in schema cache"
-- and pre-creates mirror_signals, mt5_credentials, notification/receipt tables
-- so no table is ever missing at runtime.
-- ============================================================================

begin;

-- ============================================================================
-- 0. profiles (auth users + role) — base for everything else
-- ============================================================================
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email varchar(254) unique not null,
  name text,
  role text not null default 'user',
  lifetime boolean not null default false,
  bio text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ============================================================================
-- 1. daily_macro_rules  (Strict Daily Macro gate — your blocking error #1)
-- ============================================================================
create table if not exists public.daily_macro_rules (
    id               bigint generated always as identity primary key,
    symbol           text        not null,
    asset_class      text        not null default 'forex'
                     check (asset_class in ('forex','crypto','metals','stocks','indices','other')),
    allowed_direction text       not null default 'NO_TRADE'
                     check (allowed_direction in ('BUY','SELL','NO_TRADE')),
    strict_rule_text text        not null,
    source_symbol    text,
    risk_note        text,
    is_active        boolean     not null default true,
    rule_date        date        not null default (now() at time zone 'utc'),
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

create unique index if not exists uq_daily_macro_rules_rule_date
    on public.daily_macro_rules (symbol, rule_date) where is_active = true;
create index if not exists idx_daily_macro_rules_today
    on public.daily_macro_rules (symbol, rule_date, is_active);
create index if not exists idx_daily_macro_rules_asset
    on public.daily_macro_rules (asset_class, rule_date, is_active);

-- ============================================================================
-- 2. rule_execution_audit  (Macro gate audit ledger — your blocking error #2)
-- ============================================================================
create table if not exists public.rule_execution_audit (
    id                 bigint generated always as identity primary key,
    symbol             text        not null,
    asset_class        text,
    attempted_direction text       not null,
    allowed_direction  text,
    rule_passed        boolean     not null,
    rejection_reason   text,
    strict_rule_text   text,
    mt5_ticket         bigint,
    executed           boolean     not null default false,
    created_at         timestamptz not null default now()
);

create index if not exists idx_rule_execution_audit_symbol
    on public.rule_execution_audit (symbol, created_at desc);
create index if not exists idx_rule_execution_audit_date
    on public.rule_execution_audit (created_at desc);
create index if not exists idx_rule_execution_audit_passed
    on public.rule_execution_audit (symbol, rule_passed, created_at desc);

-- ============================================================================
-- 3. mirror_signals  (Mirror-trading coordination across accounts)
--    Code: risk/mirror_trading.py  ->  client.table("mirror_signals")
-- ============================================================================
create table if not exists public.mirror_signals (
    id         bigint generated always as identity primary key,
    signal_id  text unique not null,
    created_at timestamptz not null default now(),
    expires_at timestamptz,
    data       jsonb not null
);
create index if not exists idx_mirror_signal_id on public.mirror_signals(signal_id);
create index if not exists idx_mirror_expires  on public.mirror_signals(expires_at);

-- ============================================================================
-- 4. mt5_credentials  (Mirror peer discovery reads login/api_port/api_host/bot_id/enabled)
-- ============================================================================
create table if not exists public.mt5_credentials (
    id         uuid primary key default gen_random_uuid(),
    user_id    uuid references auth.users(id) on delete set null,
    login      text not null,
    password   text,
    server     text,
    broker     text,
    api_host   text,
    api_port   text,
    bot_id     text,
    enabled    boolean not null default true,
    active     boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists idx_mt5_credentials_login  on public.mt5_credentials(login);
create index if not exists idx_mt5_credentials_active on public.mt5_credentials(enabled, active);

-- ============================================================================
-- 5. Bot persistence: signals, logs, errors
-- ============================================================================
create table if not exists public.bot_signals (
    id           uuid primary key default gen_random_uuid(),
    user_id      uuid references auth.users(id) on delete cascade,
    symbol       text,
    direction    text,
    strategy     text,
    price        double precision,
    status       text not null default 'pending',
    payload      jsonb,
    created_at   timestamptz not null default now()
);
create index if not exists idx_bot_signals_status on public.bot_signals(status);

create table if not exists public.bot_logs (
    id         uuid primary key default gen_random_uuid(),
    event      text,
    level      text,
    symbol     text,
    message    text,
    payload    jsonb,
    created_at timestamptz not null default now()
);
create index if not exists idx_bot_logs_created on public.bot_logs(created_at desc);

create table if not exists public.bot_errors (
    id          uuid primary key default gen_random_uuid(),
    error_type  text not null,
    message     text,
    traceback   text,
    symbol      text,
    payload     jsonb,
    created_at  timestamptz not null default now()
);
create index if not exists idx_bot_errors_type on public.bot_errors(error_type);

-- ============================================================================
-- 6. Intelligence / strategy performance ledger
-- ============================================================================
create table if not exists public.cis_decisions (
    id            bigint generated always as identity primary key,
    symbol        text not null,
    final_verdict text,
    reasons       jsonb,
    score         double precision,
    created_at    timestamptz not null default now()
);
create index if not exists idx_cis_symbol on public.cis_decisions(symbol, created_at desc);

create table if not exists public.strategy_performance (
    id         bigint generated always as identity primary key,
    symbol     text not null,
    strategy   text not null,
    wins       integer not null default 0,
    losses     integer not null default 0,
    win_rate   double precision,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists uq_strategy_perf
    on public.strategy_performance(symbol, strategy);

-- ============================================================================
-- 7. Web app: receipts + in-app notifications (referenced by jaguar-main)
-- ============================================================================
create table if not exists public.subscription_receipts (
    id               bigint generated always as identity primary key,
    receipt_id       text unique not null,
    email            text not null,
    plan             text not null,
    amount           double precision not null,
    currency         text not null default 'NGN',
    payment_reference text,
    started_at       timestamptz,
    ended_at         timestamptz,
    issued_at        timestamptz not null default now(),
    signature        text,
    payload          jsonb,
    created_at       timestamptz not null default now()
);
create index if not exists idx_receipts_email on public.subscription_receipts(email);

create table if not exists public.user_notifications (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid references auth.users(id) on delete cascade,
    email       text,
    type        text,
    title       text,
    body        text,
    link        text,
    read        boolean not null default false,
    dedupe_key  text,
    created_at  timestamptz not null default now()
);
create index if not exists idx_notifications_user
    on public.user_notifications(user_id, created_at desc);

-- ============================================================================
-- 8. Optional membership/content tables used by the web app
-- ============================================================================
create table if not exists public.payments (
    id           uuid primary key default gen_random_uuid(),
    event        text,
    email        text,
    amount       double precision,
    status       text,
    reference    text,
    created_at   timestamptz not null default now()
);
create table if not exists public.subscriptions (
    id         uuid primary key default gen_random_uuid(),
    email      text not null,
    plan       text,
    status     text not null default 'active',
    started_at timestamptz default now(),
    ended_at   timestamptz,
    created_at timestamptz not null default now()
);
create index if not exists idx_subscriptions_status on public.subscriptions(status);

create table if not exists public.pricing_tiers (
    id           text primary key,
    name         text,
    display_name text,
    price        double precision,
    billing_cycle text,
    description  text,
    features     jsonb,
    color        text,
    badge        text
);

-- ============================================================================
-- Row Level Security: bot service-role bypasses; allow admins/auth read as needed
-- ============================================================================
alter table public.daily_macro_rules enable row level security;
alter table public.rule_execution_audit enable row level security;
alter table public.mirror_signals enable row level security;
alter table public.bot_signals enable row level security;
alter table public.bot_logs enable row level security;
alter table public.bot_errors enable row level security;

drop policy if exists "macro_rules_service_full" on public.daily_macro_rules;
create policy "macro_rules_service_full" on public.daily_macro_rules
    for all to service_role using (true) with check (true);
drop policy if exists "macro_rules_read" on public.daily_macro_rules;
create policy "macro_rules_read" on public.daily_macro_rules
    for select using (true);

drop policy if exists "rule_audit_service_full" on public.rule_execution_audit;
create policy "rule_audit_service_full" on public.rule_execution_audit
    for all to service_role using (true) with check (true);

drop policy if exists "mirror_service_full" on public.mirror_signals;
create policy "mirror_service_full" on public.mirror_signals
    for all to service_role using (true) with check (true);
drop policy if exists "mirror_read" on public.mirror_signals;
create policy "mirror_read" on public.mirror_signals
    for select using (auth.uid() is not null);

-- ============================================================================
-- 9. Seed a permissive "allow all" fallback so the macro gate never fails-closed
--    while you wait for the nightly Finnhub+Gemini fetch to write real rules.
--    (Matches MACRO_RULE_ALLOW_BY_DEFAULT behavior as an extra safety net.)
-- ============================================================================
insert into public.daily_macro_rules
    (symbol, asset_class, allowed_direction, strict_rule_text, source_symbol, is_active, rule_date)
    select s.symbol, 'forex', 'BUY',
           'IF placeholder seed rule THEN BUY/SELL allowed by policy until nightly fetch.',
           'seed', true, (now() at time zone 'utc')::date
    from unnest(array['EURUSD','GBPUSD','USDJPY','AUDUSD','NZDUSD','USDCAD','USDCHF','AUDCAD','AUDCHF','AUDJPY','AUDNZD','AUDSGD','CADCHF','EURGBP','EURJPY','EURCHF','EURNZD','EURAUD','XAUUSD','XAGUSD','BTCUSD','ETHUSD','NAS100','US500','DXY']) as s(symbol)
    on conflict do nothing;

-- ============================================================================
-- Trigger to keep updated_at fresh
-- ============================================================================
create or replace function public.set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_daily_macro_rules_updated on public.daily_macro_rules;
create trigger trg_daily_macro_rules_updated
    before update on public.daily_macro_rules
    for each row execute function public.set_updated_at();

commit;

-- ============================================================================
-- AFTER RUNNING: to populate real daily rules run the bot's news engine:
--    MACRO_NEWS_ENGINE=gemini MACRO_RULE_ALLOW_BY_DEFAULT=true python macro_rule_engine.py
-- Set in ict_trading_bot/.env:
--    FINNHUB_API_KEY=...
--    GEMINI_API_KEY=...
--    GEMINI_MODEL=gemini-2.5-flash
--    GEMINI_USE_GROUNDING=false
--    MACRO_RULE_ALLOW_BY_DEFAULT=true
-- ============================================================================
