-- ============================================
-- SUPABASE FULL DATABASE SETUP (COPY/PASTE)
-- Project: KingsBalfx (Jaguar)
-- Includes: profiles, payments, subscriptions, bot logs,
-- pricing tiers, bot signals/errors, mentorship, MT5 creds,
-- lessons/sections/files, chat/messages, RLS + triggers.
-- ============================================

-- Extensions
create extension if not exists "pgcrypto";

-- Role ranking helper (for lesson access checks)
create or replace function public.role_rank(role text)
returns int as $$
begin
  case lower(role)
    when 'admin' then return 9;
    when 'lifetime' then return 4;
    when 'pro' then return 3;
    when 'vip' then return 2;
    when 'premium' then return 1;
    when 'user' then return 0;
    when 'free' then return 0;
    else return 0;
  end case;
end;
$$ language plpgsql immutable;

-- Auto-update updated_at
create or replace function public.update_timestamp()
returns trigger as $$
begin
  new.updated_at = current_timestamp;
  return new;
end;
$$ language plpgsql;

-- ============================================
-- PROFILES
-- ============================================
  create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email varchar(254) unique not null,
    name varchar(255),
    username varchar(50),
    phone text,
    role varchar(50) default 'user',
  lifetime boolean default false,
  bot_tier text default 'free',
  bot_max_signals_per_day integer default 0,
  bot_max_concurrent_trades integer default 0,
  bot_signal_quality text default 'none',
  bot_tier_updated_at timestamp,
  preferred_mentor uuid references auth.users(id) on delete set null,
  timezone text default 'UTC',
  receive_notifications boolean default true,
  created_at timestamp default current_timestamp,
  updated_at timestamp default current_timestamp
);

alter table public.profiles
  drop constraint if exists profiles_role_check;

alter table public.profiles
  add constraint profiles_role_check
  check (role in ('admin','user','vip','premium','pro','lifetime'));

  create index if not exists idx_profiles_email on public.profiles(email);
  create unique index if not exists idx_profiles_username on public.profiles(username) where username is not null;
  create index if not exists idx_profiles_lifetime on public.profiles(lifetime);
  create index if not exists idx_profiles_bot_tier on public.profiles(bot_tier);

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, email, role, created_at, updated_at)
  values (new.id, new.email, 'user', now(), now())
  on conflict (id) do nothing;
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

-- ============================================
-- PAYMENTS / SUBSCRIPTIONS / LOGS
-- ============================================
create table if not exists public.payments (
  id uuid primary key default gen_random_uuid(),
  event varchar(255) not null,
  data jsonb default '{}'::jsonb,
  customer_email varchar(254),
  amount bigint,
  status varchar(50),
  received_at timestamp default current_timestamp,
  foreign key (customer_email) references public.profiles(email) on delete set null
);

create index if not exists idx_payments_event on public.payments(event);
create index if not exists idx_payments_customer_email on public.payments(customer_email);
create index if not exists idx_payments_received_at on public.payments(received_at desc);

create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  email varchar(254) not null,
  plan varchar(100) not null,
  status varchar(50) default 'active' check (status in ('active','revoked','expired')),
  amount bigint default 0,
  started_at timestamp default current_timestamp,
  ended_at timestamp,
  foreign key (email) references public.profiles(email) on delete cascade,
  unique(email, plan)
);

create index if not exists idx_subscriptions_email on public.subscriptions(email);
create index if not exists idx_subscriptions_plan on public.subscriptions(plan);
create index if not exists idx_subscriptions_status on public.subscriptions(status);

create table if not exists public.bot_logs (
  id uuid primary key default gen_random_uuid(),
  event varchar(255) not null,
  payload jsonb default '{}'::jsonb,
  created_at timestamp default current_timestamp
);

create index if not exists idx_bot_logs_event on public.bot_logs(event);
create index if not exists idx_bot_logs_created_at on public.bot_logs(created_at desc);

-- ============================================
-- PRICING TIERS
-- ============================================
create table if not exists public.pricing_tiers (
  id text primary key,
  name text not null,
  display_name text not null,
  price numeric not null,
  currency text default 'NGN',
  billing_cycle text,
  description text,
  features jsonb not null,
  color text,
  badge text,
  created_at timestamp default current_timestamp,
  updated_at timestamp default current_timestamp
);

drop trigger if exists update_pricing_tiers_timestamp on public.pricing_tiers;
create trigger update_pricing_tiers_timestamp
before update on public.pricing_tiers
for each row execute function public.update_timestamp();

insert into public.pricing_tiers (id, name, display_name, price, billing_cycle, description, features, color, badge)
values
(
  'free','Free Trial','Trial',0,null,'Get started with trading signals',
  '{
    "signals": true,
    "signalQuality": "standard",
    "maxSignalsPerDay": 3,
    "mentorship": false,
    "communityAccess": "limited",
    "lessonAccess": true,
    "lessonFrequency": "weekly",
    "tradingHistory": false,
    "performanceAnalytics": false,
    "prioritySupport": false,
    "botAccess": false,
    "maxConcurrentTrades": 0
  }','yellow','Getting Started'
),
(
  'premium','Premium','Premium',90000,'monthly','Professional trader toolkit',
  '{
    "signals": true,
    "signalQuality": "premium",
    "maxSignalsPerDay": 15,
    "mentorship": false,
    "communityAccess": "full",
    "lessonAccess": true,
    "lessonFrequency": "daily",
    "tradingHistory": true,
    "performanceAnalytics": true,
    "prioritySupport": true,
    "botAccess": true,
    "maxConcurrentTrades": 5,
    "botUpdates": "weekly"
  }','blue','Most Popular'
),
(
  'vip','VIP','VIP',150000,'monthly','Elite mentorship & trading',
  '{
    "signals": true,
    "signalQuality": "vip",
    "maxSignalsPerDay": 30,
    "mentorship": true,
    "mentorshipType": "group",
    "groupSessionsPerMonth": 4,
    "communityAccess": "vip",
    "lessonAccess": true,
    "lessonFrequency": "daily",
    "tradingHistory": true,
    "performanceAnalytics": true,
    "prioritySupport": true,
    "botAccess": true,
    "maxConcurrentTrades": 10,
    "botUpdates": "daily",
    "strategyFeedback": true
  }','purple','Elite'
),
(
  'pro','Pro Trader','Pro',250000,'monthly','Complete professional setup',
  '{
    "signals": true,
    "signalQuality": "pro",
    "maxSignalsPerDay": "unlimited",
    "mentorship": true,
    "mentorshipType": "one-on-one",
    "oneOnOneSessionsPerMonth": 2,
    "groupSessionsPerMonth": 8,
    "communityAccess": "pro",
    "lessonAccess": true,
    "lessonFrequency": "daily",
    "tradingHistory": true,
    "performanceAnalytics": true,
    "advancedAnalytics": true,
    "prioritySupport": true,
    "dedicatedSupport": true,
    "botAccess": true,
    "maxConcurrentTrades": 20,
    "botUpdates": "hourly",
    "strategyFeedback": true,
    "customStrategies": true,
    "apiAccess": true
  }','indigo','Professional'
),
(
  'lifetime','Lifetime','Lifetime',500000,'one-time','Lifetime access to everything',
  '{
    "signals": true,
    "signalQuality": "pro",
    "maxSignalsPerDay": "unlimited",
    "mentorship": true,
    "mentorshipType": "one-on-one",
    "oneOnOneSessionsPerMonth": "unlimited",
    "groupSessionsPerMonth": "unlimited",
    "communityAccess": "lifetime",
    "lessonAccess": true,
    "lessonFrequency": "daily",
    "tradingHistory": true,
    "performanceAnalytics": true,
    "advancedAnalytics": true,
    "prioritySupport": true,
    "dedicatedSupport": true,
    "botAccess": true,
    "maxConcurrentTrades": "unlimited",
    "botUpdates": "real-time",
    "strategyFeedback": true,
    "customStrategies": true,
    "apiAccess": true,
    "futureUpdates": true
  }','pink','Lifetime'
)
on conflict (id) do update set
  name = excluded.name,
  display_name = excluded.display_name,
  price = excluded.price,
  currency = excluded.currency,
  billing_cycle = excluded.billing_cycle,
  description = excluded.description,
  features = excluded.features,
  color = excluded.color,
  badge = excluded.badge,
  updated_at = current_timestamp;

create index if not exists idx_pricing_tiers_id on public.pricing_tiers(id);

-- ============================================
-- BOT SIGNALS / ERRORS
-- ============================================
create table if not exists public.bot_signals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  symbol text not null,
  direction text not null,
  entry_price numeric not null,
  stop_loss numeric not null,
  take_profit numeric not null,
  signal_quality text not null,
  confidence numeric,
  reason jsonb,
  status text default 'pending',
  created_at timestamp default current_timestamp,
  executed_at timestamp,
  closed_at timestamp
);

create index if not exists idx_bot_signals_user_id on public.bot_signals(user_id);
create index if not exists idx_bot_signals_symbol on public.bot_signals(symbol);
create index if not exists idx_bot_signals_created_at on public.bot_signals(created_at desc);
create index if not exists idx_bot_signals_status on public.bot_signals(status);

create table if not exists public.bot_errors (
  id uuid primary key default gen_random_uuid(),
  error_type text not null,
  error_message text,
  stack_trace text,
  context jsonb,
  severity text,
  created_at timestamp default current_timestamp
);

create index if not exists idx_bot_errors_type on public.bot_errors(error_type);
create index if not exists idx_bot_errors_created_at on public.bot_errors(created_at desc);

-- ============================================
-- MENTORSHIP
-- ============================================
create table if not exists public.mentorship_sessions (
  id uuid primary key default gen_random_uuid(),
  mentor_id uuid references auth.users(id) on delete set null,
  student_id uuid references auth.users(id) on delete cascade,
  title text not null,
  description text,
  session_type text not null,
  scheduled_at timestamp not null,
  duration_minutes integer,
  status text default 'scheduled',
  meeting_url text,
  notes text,
  created_at timestamp default current_timestamp,
  updated_at timestamp default current_timestamp
);

drop trigger if exists update_mentorship_sessions_timestamp on public.mentorship_sessions;
create trigger update_mentorship_sessions_timestamp
before update on public.mentorship_sessions
for each row execute function public.update_timestamp();

create index if not exists idx_mentorship_sessions_mentor on public.mentorship_sessions(mentor_id);
create index if not exists idx_mentorship_sessions_student on public.mentorship_sessions(student_id);
create index if not exists idx_mentorship_sessions_scheduled on public.mentorship_sessions(scheduled_at);
create index if not exists idx_mentorship_sessions_status on public.mentorship_sessions(status);

-- ============================================
-- MT5 CREDENTIALS
-- ============================================
create table if not exists public.mt5_credentials (
  id uuid primary key default gen_random_uuid(),
  login text not null,
  password text not null,
  server text not null,
  active boolean default true,
  created_at timestamp default current_timestamp,
  updated_at timestamp default current_timestamp
);

create index if not exists idx_mt5_credentials_active on public.mt5_credentials(active);
create index if not exists idx_mt5_credentials_updated_at on public.mt5_credentials(updated_at desc);

-- ============================================
-- LESSONS / CONTENT
-- ============================================
create table if not exists public.lessons (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text,
  access_tier text not null default 'free',
  published boolean default false,
  cover_url text,
  sort_order integer default 0,
  created_at timestamp default current_timestamp,
  updated_at timestamp default current_timestamp
);

create table if not exists public.lesson_sections (
  id uuid primary key default gen_random_uuid(),
  lesson_id uuid references public.lessons(id) on delete cascade,
  title text not null,
  content text,
  position integer default 0,
  created_at timestamp default current_timestamp,
  updated_at timestamp default current_timestamp
);

create table if not exists public.lesson_files (
  id uuid primary key default gen_random_uuid(),
  lesson_id uuid references public.lessons(id) on delete cascade,
  section_id uuid references public.lesson_sections(id) on delete set null,
  file_type text not null,
  storage_path text not null,
  public_url text,
  duration_seconds integer,
  position integer default 0,
  created_at timestamp default current_timestamp
);

drop trigger if exists update_lessons_timestamp on public.lessons;
create trigger update_lessons_timestamp
before update on public.lessons
for each row execute function public.update_timestamp();

drop trigger if exists update_lesson_sections_timestamp on public.lesson_sections;
create trigger update_lesson_sections_timestamp
before update on public.lesson_sections
for each row execute function public.update_timestamp();

create index if not exists idx_lessons_access_tier on public.lessons(access_tier);
create index if not exists idx_lessons_published on public.lessons(published);
create index if not exists idx_lesson_sections_lesson_id on public.lesson_sections(lesson_id);
create index if not exists idx_lesson_files_lesson_id on public.lesson_files(lesson_id);
create index if not exists idx_lesson_files_section_id on public.lesson_files(section_id);

-- ============================================
-- MESSAGES / CHAT
-- ============================================
  create table if not exists public.messages (
    id uuid primary key default gen_random_uuid(),
    content text not null,
    segment text default 'all',
    created_by uuid references public.profiles(id) on delete set null,
    created_at timestamp default current_timestamp
  );

create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  channel text default 'premium',
  content text not null,
  created_at timestamp default current_timestamp
);

-- ============================================
-- ENABLE RLS
-- ============================================
alter table public.profiles enable row level security;
alter table public.payments enable row level security;
alter table public.subscriptions enable row level security;
alter table public.bot_logs enable row level security;
alter table public.pricing_tiers enable row level security;
alter table public.bot_signals enable row level security;
alter table public.bot_errors enable row level security;
alter table public.mentorship_sessions enable row level security;
alter table public.mt5_credentials enable row level security;
alter table public.lessons enable row level security;
alter table public.lesson_sections enable row level security;
alter table public.lesson_files enable row level security;
alter table public.messages enable row level security;
alter table public.chat_messages enable row level security;

-- ============================================
-- RLS POLICIES
-- ============================================
-- Profiles
drop policy if exists users_read_own_profile on public.profiles;
create policy users_read_own_profile on public.profiles
  for select using (auth.uid() = id);

drop policy if exists users_update_own_profile on public.profiles;
create policy users_update_own_profile on public.profiles
  for update using (auth.uid() = id);

drop policy if exists admins_read_all_profiles on public.profiles;
create policy admins_read_all_profiles on public.profiles
  for select using (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  );

-- Payments / Subscriptions / Bot Logs
drop policy if exists service_role_payments on public.payments;
create policy service_role_payments on public.payments
  for all using (auth.role() = 'service_role');

drop policy if exists service_role_subscriptions on public.subscriptions;
create policy service_role_subscriptions on public.subscriptions
  for all using (auth.role() = 'service_role');

drop policy if exists service_role_bot_logs on public.bot_logs;
create policy service_role_bot_logs on public.bot_logs
  for all using (auth.role() = 'service_role');

-- Pricing tiers (public read)
drop policy if exists pricing_tiers_read on public.pricing_tiers;
create policy pricing_tiers_read on public.pricing_tiers
  for select using (true);

drop policy if exists pricing_tiers_admin_write on public.pricing_tiers;
create policy pricing_tiers_admin_write on public.pricing_tiers
  for all using (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  )
  with check (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  );

-- Bot signals / errors
drop policy if exists bot_signals_read_own on public.bot_signals;
create policy bot_signals_read_own on public.bot_signals
  for select using (auth.uid() = user_id);

drop policy if exists bot_signals_service on public.bot_signals;
create policy bot_signals_service on public.bot_signals
  for all using (auth.role() = 'service_role');

drop policy if exists bot_errors_service on public.bot_errors;
create policy bot_errors_service on public.bot_errors
  for all using (auth.role() = 'service_role');

-- Mentorship sessions
drop policy if exists mentorship_sessions_read on public.mentorship_sessions;
create policy mentorship_sessions_read on public.mentorship_sessions
  for select using (
    auth.role() = 'service_role' or
    mentor_id = auth.uid() or student_id = auth.uid()
  );

drop policy if exists mentorship_sessions_admin_write on public.mentorship_sessions;
create policy mentorship_sessions_admin_write on public.mentorship_sessions
  for all using (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  )
  with check (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  );

-- MT5 credentials (service role only)
drop policy if exists service_role_mt5_credentials on public.mt5_credentials;
create policy service_role_mt5_credentials on public.mt5_credentials
  for all using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

-- Lessons: admin manage, users read if access tier allows
drop policy if exists lessons_read_published on public.lessons;
create policy lessons_read_published on public.lessons
  for select using (
    published = true and (
      auth.role() = 'service_role' or
      exists (
        select 1 from public.profiles p
        where p.id = auth.uid()
          and public.role_rank(p.role) >= public.role_rank(lessons.access_tier)
      )
    )
  );

drop policy if exists lessons_admin_all on public.lessons;
create policy lessons_admin_all on public.lessons
  for all using (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  )
  with check (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  );

drop policy if exists lesson_sections_read on public.lesson_sections;
create policy lesson_sections_read on public.lesson_sections
  for select using (
    exists (
      select 1 from public.lessons l
      where l.id = lesson_sections.lesson_id
        and l.published = true
        and (
          auth.role() = 'service_role' or
          exists (
            select 1 from public.profiles p
            where p.id = auth.uid()
              and public.role_rank(p.role) >= public.role_rank(l.access_tier)
          )
        )
    )
  );

drop policy if exists lesson_sections_admin_all on public.lesson_sections;
create policy lesson_sections_admin_all on public.lesson_sections
  for all using (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  )
  with check (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  );

drop policy if exists lesson_files_read on public.lesson_files;
create policy lesson_files_read on public.lesson_files
  for select using (
    exists (
      select 1 from public.lessons l
      where l.id = lesson_files.lesson_id
        and l.published = true
        and (
          auth.role() = 'service_role' or
          exists (
            select 1 from public.profiles p
            where p.id = auth.uid()
              and public.role_rank(p.role) >= public.role_rank(l.access_tier)
          )
        )
    )
  );

drop policy if exists lesson_files_admin_all on public.lesson_files;
create policy lesson_files_admin_all on public.lesson_files
  for all using (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  )
  with check (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  );

-- Messages (public read, admin write)
drop policy if exists messages_read on public.messages;
create policy messages_read on public.messages
  for select using (true);

drop policy if exists messages_admin_write on public.messages;
create policy messages_admin_write on public.messages
  for all using (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  )
  with check (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  );

-- Chat messages (authenticated users)
drop policy if exists chat_messages_read on public.chat_messages;
create policy chat_messages_read on public.chat_messages
  for select using (auth.uid() is not null);

drop policy if exists chat_messages_insert on public.chat_messages;
create policy chat_messages_insert on public.chat_messages
  for insert with check (auth.uid() is not null);

-- ============================================
-- END
-- ============================================
