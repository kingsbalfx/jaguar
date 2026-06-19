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

alter table public.user_notifications enable row level security;

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
