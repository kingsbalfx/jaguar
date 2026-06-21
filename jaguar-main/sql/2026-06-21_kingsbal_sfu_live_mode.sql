-- KINGSBALFX internal SFU live-room mode.
-- Run this after the existing live_sessions migrations if your table is older.

alter table public.live_sessions
  add column if not exists media_type text default 'kingsbal_sfu',
  add column if not exists media_url text,
  add column if not exists room_name text default 'global-room',
  add column if not exists room_mode text not null default 'group',
  add column if not exists target_user_ids uuid[] not null default '{}';

update public.live_sessions
set media_type = 'kingsbal_sfu'
where media_type is null
   or lower(media_type) in ('youtube', 'iframe', 'embed', 'broadcast', 'videosdk', 'twilio_video');

update public.live_sessions
set media_url = null
where lower(coalesce(media_type, '')) = 'kingsbal_sfu';

alter table public.live_sessions
  drop constraint if exists live_sessions_media_type_check;

alter table public.live_sessions
  add constraint live_sessions_media_type_check
  check (lower(media_type) in ('kingsbal_sfu', 'webrtc'));
