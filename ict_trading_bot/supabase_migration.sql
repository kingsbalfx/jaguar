-- ============================================================================
-- Strict Daily Macro & Fundamental Rule Engine — Supabase Migration
-- ============================================================================
-- Run this script in the Supabase SQL Editor (Dashboard → SQL → New query)
-- for your EXISTING Supabase project. It is idempotent: safe to re-run.
--
-- Tables created:
--   1. daily_macro_rules    — today's strict, LLM-derived trading rule per symbol
--   2. rule_execution_audit — immutable audit log of every rule validation attempt
-- ============================================================================

begin;

-- ----------------------------------------------------------------------------
-- 1. daily_macro_rules
-- ----------------------------------------------------------------------------
-- Stores the single strict rule that governs trading for a symbol on a given day.
-- Only ONE active rule may exist per (symbol, day); an upsert on symbol + date
-- replaces yesterday's entry so the bot always reads today's directive.
-- ----------------------------------------------------------------------------
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

-- Only one active rule per symbol per day.
create unique index if not exists uq_daily_macro_rules_rule_date
    on public.daily_macro_rules (symbol, rule_date)
    where is_active = true;

-- Fast lookup of today's rule by symbol.
create index if not exists idx_daily_macro_rules_today
    on public.daily_macro_rules (symbol, rule_date, is_active);

-- Helpful indexes for daily batch fetching.
create index if not exists idx_daily_macro_rules_asset
    on public.daily_macro_rules (asset_class, rule_date, is_active);

-- ----------------------------------------------------------------------------
-- 2. rule_execution_audit
-- ----------------------------------------------------------------------------
-- Append-only ledger of every gate the macro engine evaluated. A row is written
-- for EVERY attempt (approved or rejected) so you can audit why each symbol was
-- or was not traded, and cross-reference the resulting MT5 ticket.
-- ----------------------------------------------------------------------------
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

-- Efficient daily / per-symbol audit queries.
create index if not exists idx_rule_execution_audit_symbol
    on public.rule_execution_audit (symbol, created_at desc);

create index if not exists idx_rule_execution_audit_date
    on public.rule_execution_audit (created_at desc);

create index if not exists idx_rule_execution_audit_passed
    on public.rule_execution_audit (symbol, rule_passed, created_at desc);

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
-- The bot uses the service-role key (bypasses RLS). These policies keep the
-- tables readable/writable only by the bot service role and any authenticated
-- admin. Adjust the `auth.uid()` checks to match your admin user model if needed.
-- ----------------------------------------------------------------------------
alter table public.daily_macro_rules enable row level security;
alter table public.rule_execution_audit enable row level security;

drop policy if exists "macro_rules_service_read" on public.daily_macro_rules;
create policy "macro_rules_service_read"
    on public.daily_macro_rules
    for select
    using (true);

drop policy if exists "macro_rules_service_write" on public.daily_macro_rules;
create policy "macro_rules_service_write"
    on public.daily_macro_rules
    for all
    to service_role
    using (true)
    with check (true);

drop policy if exists "rule_audit_service_read" on public.rule_execution_audit;
create policy "rule_audit_service_read"
    on public.rule_execution_audit
    for select
    using (true);

drop policy if exists "rule_audit_service_write" on public.rule_execution_audit;
create policy "rule_audit_service_write"
    on public.rule_execution_audit
    for all
    to service_role
    using (true)
    with check (true);

-- ----------------------------------------------------------------------------
-- Automated "updated_at" maintenance
-- ----------------------------------------------------------------------------
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
    for each row
    execute function public.set_updated_at();

commit;
