create table if not exists public.quiz_results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  email text,
  plan text not null check (plan in ('premium', 'vip', 'pro', 'lifetime')),
  quiz_title text not null,
  score integer not null default 0,
  total integer not null default 0,
  completed_at timestamptz not null default now()
);

create table if not exists public.competition_entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  email text,
  plan text not null check (plan in ('premium', 'vip', 'pro', 'lifetime')),
  competition_title text not null,
  points numeric not null default 0,
  rank integer,
  updated_at timestamptz not null default now()
);

create index if not exists quiz_results_plan_completed_idx on public.quiz_results(plan, completed_at desc);
create index if not exists competition_entries_plan_points_idx on public.competition_entries(plan, points desc);

alter table public.quiz_results enable row level security;
alter table public.competition_entries enable row level security;

drop policy if exists "users read own quiz results" on public.quiz_results;
create policy "users read own quiz results" on public.quiz_results for select using (auth.uid() = user_id);

drop policy if exists "users read own competition entries" on public.competition_entries;
create policy "users read own competition entries" on public.competition_entries for select using (auth.uid() = user_id);
