-- Allow users to submit MT5 credentials for admin activation
create table if not exists public.mt5_submissions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  email varchar(254),
  login text not null,
  password text not null,
  server text not null,
  status text default 'pending',
  created_at timestamp default current_timestamp,
  updated_at timestamp default current_timestamp
);

create index if not exists idx_mt5_submissions_user on public.mt5_submissions(user_id);
create index if not exists idx_mt5_submissions_status on public.mt5_submissions(status);
