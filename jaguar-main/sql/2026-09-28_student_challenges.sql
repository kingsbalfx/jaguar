-- Student demo challenges (MT5 / TradingView) built on top of plan subscriptions.
-- Also adds profiles.bot_signals_muted, used by the signal audience resolver.
-- Run this in the Supabase SQL editor.

-- ---------------------------------------------------------------------------
-- 1. Explicit per-user signal mute (used by lib/signal-delivery.js)
-- ---------------------------------------------------------------------------
alter table if exists public.profiles
  add column if not exists bot_signals_muted boolean not null default false;

-- ---------------------------------------------------------------------------
-- 2. Demo account pool that admins hand out to approved students
-- ---------------------------------------------------------------------------
create table if not exists public.challenge_demo_accounts (
  id uuid primary key default gen_random_uuid(),
  platform text not null check (platform in ('mt5', 'tradingview')),
  label text,
  login text,
  server text,
  password_encrypted text,
  password_iv text,
  password_tag text,
  password_last4 text,
  tradingview_url text,
  tradingview_username text,
  status text not null default 'available'
    check (status in ('available', 'assigned', 'retired')),
  assigned_challenge_id uuid,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_challenge_demo_accounts_status
  on public.challenge_demo_accounts(platform, status);

create unique index if not exists idx_challenge_demo_accounts_login
  on public.challenge_demo_accounts(platform, login)
  where login is not null;

-- ---------------------------------------------------------------------------
-- 3. Challenge requests
-- ---------------------------------------------------------------------------
create table if not exists public.challenges (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  email text not null,
  full_name text,
  plan text not null,
  platform text not null check (platform in ('mt5', 'tradingview')),
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'active', 'rejected', 'expired', 'cancelled')),
  duration_days integer not null default 14,
  goal text,
  experience text,
  admin_note text,
  rejection_reason text,
  account_id uuid references public.challenge_demo_accounts(id) on delete set null,
  demo_login text,
  demo_server text,
  demo_password_encrypted text,
  demo_password_iv text,
  demo_password_tag text,
  demo_password_last4 text,
  tradingview_url text,
  tradingview_username text,
  reviewed_by uuid,
  reviewed_at timestamptz,
  started_at timestamptz,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_challenges_user_created
  on public.challenges(user_id, created_at desc);

create index if not exists idx_challenges_status_created
  on public.challenges(status, created_at desc);

-- One open challenge per student at a time (pending/approved/active).
create unique index if not exists idx_challenges_one_open_per_user
  on public.challenges(user_id)
  where user_id is not null and status in ('pending', 'approved', 'active');


-- ---------------------------------------------------------------------------
-- 4. Row level security
-- ---------------------------------------------------------------------------
alter table public.challenges enable row level security;

drop policy if exists "students read own challenges" on public.challenges;
create policy "students read own challenges"
  on public.challenges
  for select
  using (auth.uid() = user_id);

drop policy if exists "admins manage challenges" on public.challenges;
create policy "admins manage challenges"
  on public.challenges
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

drop policy if exists "service role manages challenges" on public.challenges;
create policy "service role manages challenges"
  on public.challenges
  for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

alter table public.challenge_demo_accounts enable row level security;

drop policy if exists "admins manage challenge demo accounts" on public.challenge_demo_accounts;
create policy "admins manage challenge demo accounts"
  on public.challenge_demo_accounts
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

drop policy if exists "service role manages challenge demo accounts" on public.challenge_demo_accounts;
create policy "service role manages challenge demo accounts"
  on public.challenge_demo_accounts
  for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

-- ---------------------------------------------------------------------------
-- 5. Admin overview view
-- ---------------------------------------------------------------------------
create or replace view public.challenge_overview as
select
  status,
  platform,
  count(*) as total,
  count(*) filter (where expires_at is not null and expires_at < now()) as overdue
from public.challenges
group by status, platform;

grant select on public.challenge_overview to service_role;
