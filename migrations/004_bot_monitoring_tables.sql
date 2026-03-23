create table if not exists public.bot_logs (
  id uuid primary key default gen_random_uuid(),
  event text,
  payload jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

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

alter table public.bot_logs
  add column if not exists event text;

alter table public.bot_logs
  add column if not exists payload jsonb default '{}'::jsonb;

alter table public.bot_logs
  add column if not exists created_at timestamptz default now();

alter table public.bot_signals
  add column if not exists user_id uuid null;

alter table public.bot_signals
  add column if not exists symbol text;

alter table public.bot_signals
  add column if not exists direction text;

alter table public.bot_signals
  add column if not exists entry_price numeric;

alter table public.bot_signals
  add column if not exists stop_loss numeric;

alter table public.bot_signals
  add column if not exists take_profit numeric;

alter table public.bot_signals
  add column if not exists signal_quality text;

alter table public.bot_signals
  add column if not exists confidence numeric;

alter table public.bot_signals
  add column if not exists reason jsonb default '{}'::jsonb;

alter table public.bot_signals
  add column if not exists status text default 'pending';

alter table public.bot_signals
  add column if not exists created_at timestamptz default now();
