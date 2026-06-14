create table if not exists public.email_notifications (
  id uuid primary key default gen_random_uuid(),
  email varchar(254) not null,
  notification_type text not null,
  dedupe_key text not null unique,
  sent_at timestamptz not null default now()
);

create index if not exists idx_email_notifications_email on public.email_notifications(email);
create index if not exists idx_email_notifications_type on public.email_notifications(notification_type);

alter table public.email_notifications enable row level security;

create table if not exists public.subscription_activations (
  id uuid primary key default gen_random_uuid(),
  payment_reference text not null unique,
  email varchar(254) not null,
  plan text not null,
  started_at timestamptz not null,
  ended_at timestamptz,
  created_at timestamptz not null default now()
);

alter table public.subscription_activations enable row level security;
