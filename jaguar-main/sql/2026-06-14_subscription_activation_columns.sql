alter table public.subscriptions
  add column if not exists amount numeric not null default 0,
  add column if not exists started_at timestamptz not null default now(),
  add column if not exists ended_at timestamptz;

create index if not exists idx_subscriptions_email_lower
  on public.subscriptions (lower(email));

create index if not exists idx_subscriptions_active_expiry
  on public.subscriptions (status, ended_at);
