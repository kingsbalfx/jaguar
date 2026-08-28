-- Stamped subscription receipts and lifecycle notification support.
-- Run this in Supabase SQL Editor after deploying the code.

create table if not exists public.email_notifications (
  id uuid primary key default gen_random_uuid(),
  email varchar(254) not null,
  notification_type text not null,
  dedupe_key text not null unique,
  sent_at timestamptz not null default now()
);

create index if not exists idx_email_notifications_email on public.email_notifications(email);
create index if not exists idx_email_notifications_type on public.email_notifications(notification_type);

create table if not exists public.user_notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null,
  body text not null,
  link text,
  notification_type text not null default 'general',
  dedupe_key text unique,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_user_notifications_user_created
  on public.user_notifications(user_id, created_at desc);

create table if not exists public.subscription_receipts (
  id uuid primary key default gen_random_uuid(),
  receipt_id text not null unique,
  email varchar(254) not null,
  plan text not null,
  amount numeric not null default 0,
  currency text not null default 'NGN',
  payment_reference text,
  started_at timestamptz,
  ended_at timestamptz,
  issued_at timestamptz not null default now(),
  signature text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists subscription_receipts_email_idx
  on public.subscription_receipts(lower(email), issued_at desc);

create index if not exists subscription_receipts_reference_idx
  on public.subscription_receipts(payment_reference);

alter table public.email_notifications enable row level security;
alter table public.user_notifications enable row level security;
alter table public.subscription_receipts enable row level security;

drop policy if exists "users read own notifications" on public.user_notifications;
create policy "users read own notifications"
  on public.user_notifications
  for select to authenticated
  using (auth.uid() = user_id);

drop policy if exists "users update own notifications" on public.user_notifications;
create policy "users update own notifications"
  on public.user_notifications
  for update to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "service role writes notifications" on public.user_notifications;
create policy "service role writes notifications"
  on public.user_notifications
  for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
