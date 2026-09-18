-- ============================================================================
-- RUNTIME STRATEGY SETTINGS  (bot_strategy_settings)
-- ----------------------------------------------------------------------------
-- Lets the admin panel switch strategies ON / OFF while the bot is running.
--
--   bot     : strategy/toggles.py reads this table every ~30s (no restart)
--   admin   : POST /api/admin/bot-control  {"action":"set-strategy", ...}
--             or POST http://<bot-host>:8000/admin/strategies
--   manual  : insert/update rows in the Supabase table editor
--
-- Precedence inside the bot:
--   data/strategy_toggles.json  >  this table  >  .env default
--
-- A missing table is harmless: the bot falls back to the .env defaults.
-- ============================================================================

create table if not exists public.bot_strategy_settings (
    strategy    text primary key,
    enabled     boolean not null default true,
    updated_at  timestamptz not null default now(),
    updated_by  text
);

-- Seed every strategy the bot knows about, all ON.
insert into public.bot_strategy_settings (strategy, enabled, updated_by)
values
    ('ict',        true, 'migration'),
    ('kingsbalfx', true, 'migration'),
    ('fallback3',  true, 'migration'),
    ('fallback4',  true, 'migration'),
    ('fallback5',  true, 'migration'),
    ('mirror',     true, 'migration')
on conflict (strategy) do nothing;

-- Only the service-role key (bot + server-side web API) may read/write.
alter table public.bot_strategy_settings enable row level security;

drop policy if exists "service role full access" on public.bot_strategy_settings;
create policy "service role full access"
    on public.bot_strategy_settings
    for all
    using (auth.role() = 'service_role')
    with check (auth.role() = 'service_role');

-- Handy view: what the admin panel shows.
create or replace view public.bot_strategy_settings_overview as
select strategy, enabled, updated_at, updated_by
from public.bot_strategy_settings
order by strategy;
