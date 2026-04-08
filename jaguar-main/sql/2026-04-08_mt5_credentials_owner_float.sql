alter table public.mt5_credentials
  add column if not exists user_id uuid references auth.users(id) on delete set null,
  add column if not exists email varchar(254);

create index if not exists idx_mt5_credentials_user on public.mt5_credentials(user_id);
create index if not exists idx_mt5_credentials_login on public.mt5_credentials(login);
