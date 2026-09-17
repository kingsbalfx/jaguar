-- ============================================================================
-- mt5_credentials : the single source of truth for accounts submitted
-- either LOCALLY (env / accounts.example.json / data/accounts_local.json) or
-- through the WEB (admin API / dashboard).
--
-- Run this once in Supabase -> SQL Editor. It is safe to re-run.
-- The UNIQUE constraint on login is what makes upsert work; without it the bot
-- falls back to select + insert/update (slower but still functional).
-- ============================================================================

create table if not exists public.mt5_credentials (
    id          bigserial primary key,
    login       text        not null,
    password    text        not null,
    server      text        not null,
    active      boolean     not null default true,
    user_id     text,
    email       text,
    api_host    text,
    api_port    integer,
    bot_id      text,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

-- Optional columns used by the mirror / dashboard (added when missing).
alter table public.mt5_credentials add column if not exists active     boolean not null default true;
alter table public.mt5_credentials add column if not exists user_id    text;
alter table public.mt5_credentials add column if not exists email      text;
alter table public.mt5_credentials add column if not exists api_host   text;
alter table public.mt5_credentials add column if not exists api_port   integer;
alter table public.mt5_credentials add column if not exists bot_id     text;
alter table public.mt5_credentials add column if not exists created_at timestamptz not null default now();
alter table public.mt5_credentials add column if not exists updated_at timestamptz not null default now();

-- Remove duplicate logins (keeps the newest row) before adding the constraint.
delete from public.mt5_credentials a
      using public.mt5_credentials b
      where a.login = b.login
        and a.id < b.id;

-- THE important part: upsert(on_conflict="login") needs this.
alter table public.mt5_credentials
    add constraint mt5_credentials_login_key unique (login);

-- Keep updated_at fresh on writes coming from the bot / dashboard.
create or replace function public.touch_mt5_credentials_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end $$;

drop trigger if exists trg_touch_mt5_credentials on public.mt5_credentials;
create trigger trg_touch_mt5_credentials
    before update on public.mt5_credentials
    for each row execute function public.touch_mt5_credentials_updated_at();

-- Service-role access from the bot backend.
alter table public.mt5_credentials enable row level security;
