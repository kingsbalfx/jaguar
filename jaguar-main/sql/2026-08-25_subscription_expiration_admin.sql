-- Subscription expiration controls for the admin dashboard.
-- Run this in Supabase SQL Editor if the dashboard cannot save expiry/status edits.

create table if not exists public.subscriptions (
  email text not null,
  plan text not null,
  status text not null default 'active',
  amount numeric,
  started_at timestamptz default now(),
  ended_at timestamptz
);

alter table public.subscriptions
  add column if not exists status text not null default 'active',
  add column if not exists amount numeric,
  add column if not exists started_at timestamptz default now(),
  add column if not exists ended_at timestamptz;

create index if not exists subscriptions_email_plan_idx
  on public.subscriptions (lower(email), lower(plan));

create index if not exists subscriptions_status_ended_at_idx
  on public.subscriptions (status, ended_at);

update public.subscriptions
set status = 'inactive'
where status is null
  or status not in ('active', 'expired', 'cancelled', 'canceled', 'revoked', 'inactive', 'pending');

update public.subscriptions
set status = 'expired'
where status = 'active'
  and ended_at is not null
  and ended_at <= now();

do $$
begin
  alter table public.subscriptions
    add constraint subscriptions_status_check
    check (status in ('active', 'expired', 'cancelled', 'canceled', 'revoked', 'inactive', 'pending'));
exception
  when duplicate_object then null;
end $$;
