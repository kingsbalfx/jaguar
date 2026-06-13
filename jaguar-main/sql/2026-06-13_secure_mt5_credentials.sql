alter table public.mt5_submissions
  add column if not exists consent_accepted boolean default false,
  add column if not exists password_encrypted text,
  add column if not exists password_iv text,
  add column if not exists password_tag text,
  add column if not exists password_last4 text,
  add column if not exists risk_notice_version text,
  add column if not exists submitted_ip text,
  add column if not exists user_agent text;

alter table public.mt5_credentials
  add column if not exists password_encrypted text,
  add column if not exists password_iv text,
  add column if not exists password_tag text,
  add column if not exists password_last4 text;

alter table public.mt5_submissions alter column password drop not null;
alter table public.mt5_credentials alter column password drop not null;

comment on column public.mt5_submissions.password is 'LEGACY: do not write new plaintext passwords; phase out after encrypted migration.';
comment on column public.mt5_credentials.password is 'LEGACY: do not write new plaintext passwords; phase out after encrypted migration.';
