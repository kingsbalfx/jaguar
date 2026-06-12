begin;

alter table public.live_sessions
  add column if not exists room_mode text not null default 'group',
  add column if not exists target_user_ids uuid[] not null default '{}';

alter table public.live_sessions
  drop constraint if exists live_sessions_room_mode_check;
alter table public.live_sessions
  add constraint live_sessions_room_mode_check check (room_mode in ('group', 'one_to_one'));

create table if not exists public.mentorship_messages (
  id uuid primary key default gen_random_uuid(),
  room_key text not null,
  sender_id uuid not null references auth.users(id) on delete cascade,
  sender_name text,
  content text not null check (char_length(content) between 1 and 10000),
  reply_to uuid references public.mentorship_messages(id) on delete set null,
  attachment_url text,
  attachment_type text,
  reactions jsonb not null default '{}'::jsonb,
  edited_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists mentorship_messages_room_created_idx
  on public.mentorship_messages(room_key, created_at);

create table if not exists public.mentorship_message_reactions (
  message_id uuid not null references public.mentorship_messages(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  emoji text not null check (char_length(emoji) between 1 and 16),
  created_at timestamptz not null default now(),
  primary key (message_id, user_id, emoji)
);

create table if not exists public.mentorship_message_reads (
  room_key text not null,
  message_id uuid not null references public.mentorship_messages(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  read_at timestamptz not null default now(),
  primary key (message_id, user_id)
);

alter table public.mentorship_messages enable row level security;
alter table public.mentorship_message_reactions enable row level security;
alter table public.mentorship_message_reads enable row level security;

create or replace function public.mentorship_can_access_room(requested_room text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.live_sessions room
    join public.profiles profile on profile.id = auth.uid()
    where room.room_name = requested_room
      and room.active = true
      and (
        lower(profile.role) = 'admin'
        or auth.uid() = any(room.target_user_ids)
        or (
          coalesce(array_length(room.target_user_ids, 1), 0) = 0
          and case lower(coalesce(room.segment, 'all'))
            when 'all' then true
            when 'free' then lower(profile.role) in ('free', 'premium', 'vip', 'pro', 'lifetime')
            when 'premium' then lower(profile.role) in ('premium', 'vip', 'pro', 'lifetime')
            when 'vip' then lower(profile.role) in ('vip', 'pro', 'lifetime')
            when 'pro' then lower(profile.role) in ('pro', 'lifetime')
            when 'lifetime' then lower(profile.role) = 'lifetime'
            else false
          end
        )
      )
  );
$$;

drop policy if exists "mentorship members read messages" on public.mentorship_messages;
create policy "mentorship members read messages"
on public.mentorship_messages for select to authenticated
using (public.mentorship_can_access_room(room_key));

drop policy if exists "mentorship members send messages" on public.mentorship_messages;
create policy "mentorship members send messages"
on public.mentorship_messages for insert to authenticated
with check (sender_id = auth.uid() and public.mentorship_can_access_room(room_key));

drop policy if exists "message owners update messages" on public.mentorship_messages;
create policy "message owners update messages"
on public.mentorship_messages for update to authenticated
using (
  sender_id = auth.uid()
  or exists (select 1 from public.profiles p where p.id = auth.uid() and lower(p.role) = 'admin')
)
with check (
  (sender_id = auth.uid() and public.mentorship_can_access_room(room_key))
  or exists (select 1 from public.profiles p where p.id = auth.uid() and lower(p.role) = 'admin')
);

drop policy if exists "members read reactions" on public.mentorship_message_reactions;
create policy "members read reactions" on public.mentorship_message_reactions for select to authenticated
using (exists (select 1 from public.mentorship_messages message where message.id = message_id and public.mentorship_can_access_room(message.room_key)));

drop policy if exists "members read receipts" on public.mentorship_message_reads;
create policy "members read receipts" on public.mentorship_message_reads for select to authenticated
using (public.mentorship_can_access_room(room_key));

drop policy if exists "members write receipts" on public.mentorship_message_reads;
create policy "members write receipts" on public.mentorship_message_reads for insert to authenticated
with check (user_id = auth.uid() and public.mentorship_can_access_room(room_key));

drop policy if exists "members update receipts" on public.mentorship_message_reads;
create policy "members update receipts" on public.mentorship_message_reads for update to authenticated
using (user_id = auth.uid() and public.mentorship_can_access_room(room_key));

create or replace function public.toggle_mentorship_reaction(requested_message uuid, requested_emoji text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  message_room text;
begin
  select room_key into message_room from public.mentorship_messages where id = requested_message;
  if message_room is null or not public.mentorship_can_access_room(message_room) then
    raise exception 'not allowed';
  end if;
  if exists (select 1 from public.mentorship_message_reactions where message_id = requested_message and user_id = auth.uid() and emoji = requested_emoji) then
    delete from public.mentorship_message_reactions where message_id = requested_message and user_id = auth.uid() and emoji = requested_emoji;
  else
    insert into public.mentorship_message_reactions(message_id, user_id, emoji) values (requested_message, auth.uid(), requested_emoji);
  end if;
end;
$$;

grant execute on function public.toggle_mentorship_reaction(uuid, text) to authenticated;

insert into storage.buckets (id, name, public)
values ('mentorship-chat', 'mentorship-chat', false)
on conflict (id) do update set public = false;

drop policy if exists "mentorship attachments upload" on storage.objects;
create policy "mentorship attachments upload"
on storage.objects for insert to authenticated
with check (
  bucket_id = 'mentorship-chat'
  and (storage.foldername(name))[2] = auth.uid()::text
  and public.mentorship_can_access_room((storage.foldername(name))[1])
);

drop policy if exists "mentorship attachments read" on storage.objects;
create policy "mentorship attachments read"
on storage.objects for select to authenticated
using (bucket_id = 'mentorship-chat' and public.mentorship_can_access_room((storage.foldername(name))[1]));

drop policy if exists "mentorship attachments delete own" on storage.objects;
create policy "mentorship attachments delete own"
on storage.objects for delete to authenticated
using (bucket_id = 'mentorship-chat' and (storage.foldername(name))[2] = auth.uid()::text);

do $$
declare
  table_name text;
begin
  foreach table_name in array array['mentorship_messages', 'mentorship_message_reads', 'mentorship_message_reactions']
  loop
    if not exists (
      select 1 from pg_publication_tables
      where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = table_name
    ) then
      execute format('alter publication supabase_realtime add table public.%I', table_name);
    end if;
  end loop;
end;
$$;

alter table realtime.messages enable row level security;

drop policy if exists "mentorship realtime read" on realtime.messages;
create policy "mentorship realtime read"
on realtime.messages for select to authenticated
using (
  split_part(realtime.topic(), ':', 1) in ('mentorship-room', 'mentorship-chat')
  and public.mentorship_can_access_room(split_part(realtime.topic(), ':', 2))
);

drop policy if exists "mentorship realtime write" on realtime.messages;
create policy "mentorship realtime write"
on realtime.messages for insert to authenticated
with check (
  split_part(realtime.topic(), ':', 1) in ('mentorship-room', 'mentorship-chat')
  and public.mentorship_can_access_room(split_part(realtime.topic(), ':', 2))
);

commit;
