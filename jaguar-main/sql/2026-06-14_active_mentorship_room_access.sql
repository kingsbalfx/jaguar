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
        or (
          auth.uid() = any(room.target_user_ids)
          and exists (
            select 1
            from public.subscriptions subscription
            where lower(subscription.email) = lower(profile.email)
              and subscription.status = 'active'
              and (subscription.ended_at is null or subscription.ended_at > now())
          )
        )
        or (
          coalesce(array_length(room.target_user_ids, 1), 0) = 0
          and (
            lower(coalesce(room.segment, 'all')) in ('all', 'free')
            or exists (
              select 1
              from public.subscriptions subscription
              where lower(subscription.email) = lower(profile.email)
                and subscription.status = 'active'
                and (subscription.ended_at is null or subscription.ended_at > now())
                and case lower(coalesce(room.segment, 'all'))
                  when 'premium' then lower(subscription.plan) in ('premium', 'vip', 'pro', 'lifetime')
                  when 'vip' then lower(subscription.plan) in ('vip', 'pro', 'lifetime')
                  when 'pro' then lower(subscription.plan) in ('pro', 'lifetime')
                  when 'lifetime' then lower(subscription.plan) = 'lifetime'
                  else false
                end
            )
          )
        )
      )
  );
$$;
