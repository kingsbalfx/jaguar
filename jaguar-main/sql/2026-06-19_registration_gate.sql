-- Admin-controlled paid registration/payment pause.
-- Free tier account registration remains available while this gate is active.

create table if not exists public.site_settings (
  key text primary key,
  settings jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.site_settings enable row level security;

drop policy if exists "site_settings_admin_all" on public.site_settings;
create policy "site_settings_admin_all"
  on public.site_settings
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

drop policy if exists "site_settings_public_read_registration_gate" on public.site_settings;
create policy "site_settings_public_read_registration_gate"
  on public.site_settings
  for select
  using (key = 'registration_gate');

insert into public.site_settings (key, settings, updated_at)
values (
  'registration_gate',
  jsonb_build_object(
    'paused', false,
    'reopen_at', null,
    'message', 'Application has been closed. A class is already going on. Please wait until the reopening date to apply for paid access. Free tier registration is still open.',
    'updated_at', now()
  ),
  now()
)
on conflict (key) do nothing;
