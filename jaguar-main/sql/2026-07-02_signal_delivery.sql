-- Signal delivery audit + tier quota support.
-- Run this in Supabase SQL Editor after the existing bot_signals migration.

create table if not exists public.site_settings (
  key text primary key,
  settings jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.site_settings enable row level security;

drop policy if exists "site_settings_admin_all" on public.site_settings;
create policy "site_settings_admin_all"
  on public.site_settings
  for all
  using (
    exists (
      select 1
      from public.profiles
      where profiles.id = auth.uid()
        and lower(coalesce(profiles.role, '')) = 'admin'
    )
  )
  with check (
    exists (
      select 1
      from public.profiles
      where profiles.id = auth.uid()
        and lower(coalesce(profiles.role, '')) = 'admin'
    )
  );

insert into public.site_settings (key, settings, updated_at)
values (
  'bot_signal_gate',
  jsonb_build_object(
    'paused', false,
    'resume_at', null,
    'message', 'Bot signal delivery is active.',
    'updated_at', now()
  ),
  now()
)
on conflict (key) do nothing;

create table if not exists public.bot_signals (
  id uuid primary key default gen_random_uuid(),
  bot_id uuid not null default '00000000-0000-4000-8000-000000000001'::uuid,
  user_id uuid null,
  signal text not null default '',
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
  add column if not exists bot_id uuid default '00000000-0000-4000-8000-000000000001'::uuid;

update public.bot_signals
set bot_id = '00000000-0000-4000-8000-000000000001'::uuid
where bot_id is null;

alter table public.bot_signals
  alter column bot_id set default '00000000-0000-4000-8000-000000000001'::uuid;

alter table public.bot_signals
  alter column bot_id set not null;

alter table public.bot_signals
  add column if not exists signal text default '';

update public.bot_signals
set signal = trim(coalesce(symbol, '') || ' ' || coalesce(direction, ''))
where signal is null or signal = '';

alter table public.bot_signals
  alter column signal set default '';

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

create table if not exists public.mirror_signals (
  signal_id text primary key,
  expires_at timestamptz,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_mirror_signals_expires_at
  on public.mirror_signals(expires_at desc);

alter table public.mirror_signals enable row level security;

drop policy if exists "service role manages mirror signals" on public.mirror_signals;
create policy "service role manages mirror signals"
  on public.mirror_signals
  for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
