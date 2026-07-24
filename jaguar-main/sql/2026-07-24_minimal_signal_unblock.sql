-- Minimal signal/email unblock.
-- Paste and run this whole file in Supabase SQL Editor.
-- This file avoids DO blocks so partial execution is less likely to fail.

alter table public.bot_signals
  drop constraint if exists bot_signals_bot_id_fkey;

alter table public.bot_signals
  alter column bot_id drop default;

alter table public.bot_signals
  alter column bot_id drop not null;

update public.bot_signals
set bot_id = null
where bot_id is not null;

alter table public.bot_signals
  add column if not exists signal jsonb default '{}'::jsonb;

update public.bot_signals
set signal = '{}'::jsonb
where signal is null;

alter table public.bot_signals
  alter column signal set default '{}'::jsonb;

alter table public.bot_signals
  alter column signal set not null;

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
