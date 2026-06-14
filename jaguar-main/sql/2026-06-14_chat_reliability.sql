begin;

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
            when 'free' then true
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

grant select, insert, update on public.mentorship_messages to authenticated;
grant select, insert, update, delete on public.mentorship_message_reactions to authenticated;
grant select, insert, update on public.mentorship_message_reads to authenticated;
grant execute on function public.mentorship_can_access_room(text) to authenticated;

do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'mentorship_messages'
  ) then
    alter publication supabase_realtime add table public.mentorship_messages;
  end if;
end;
$$;

commit;
