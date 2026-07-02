-- Signal delivery audit + tier quota support.
-- Run this in Supabase SQL Editor after the existing bot_signals migration.

create table if not exists public.bot_signals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid null,
  symbol text,
  direction text,
  entry_price numeric,
  stop_loss numeric,
  take_profit numeric,
  signal_quality text,
  confidence numeric,
  reason jsonb default '{}'::jsonb,
  status text default 'pending',
  created_at timestamptz default now()
);

alter table public.bot_signals
  add column if not exists reason jsonb default '{}'::jsonb;

alter table public.bot_signals
  add column if not exists confidence numeric;

alter table public.bot_signals
  add column if not exists signal_quality text;

alter table public.bot_signals
  add column if not exists status text default 'pending';

alter table public.bot_signals
  add column if not exists created_at timestamptz default now();

create table if not exists public.signal_deliveries (
  id uuid primary key default gen_random_uuid(),
  signal_id uuid references public.bot_signals(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  email text not null,
  plan text not null,
  daily_limit integer not null default 0,
  used_today_before integer not null default 0,
  channel text not null default 'email,in_app',
  status text not null default 'sent',
  delivered_at timestamptz not null default now()
);

create unique index if not exists idx_signal_deliveries_signal_user
  on public.signal_deliveries(signal_id, user_id);

create index if not exists idx_signal_deliveries_user_delivered
  on public.signal_deliveries(user_id, delivered_at desc);

create index if not exists idx_signal_deliveries_plan_delivered
  on public.signal_deliveries(plan, delivered_at desc);

alter table public.signal_deliveries enable row level security;

drop policy if exists "users read own signal deliveries" on public.signal_deliveries;
create policy "users read own signal deliveries"
  on public.signal_deliveries
  for select
  using (auth.uid() = user_id);

drop policy if exists "service role manages signal deliveries" on public.signal_deliveries;
create policy "service role manages signal deliveries"
  on public.signal_deliveries
  for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
