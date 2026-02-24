-- Add extended profile fields for registration completion
alter table public.profiles
  add column if not exists address text,
  add column if not exists country text,
  add column if not exists age_confirmed boolean default false;
