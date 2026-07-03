-- Enable image attachments in live mentorship chat.
-- Run this in Supabase SQL editor before sending chart images through the live chat.

alter table public.mentorship_messages
  add column if not exists attachment_type text,
  add column if not exists attachment_bucket text,
  add column if not exists attachment_path text,
  add column if not exists attachment_name text,
  add column if not exists attachment_size bigint,
  add column if not exists attachment_metadata jsonb not null default '{}'::jsonb;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'mentorship_messages_attachment_type_check'
      and conrelid = 'public.mentorship_messages'::regclass
  ) then
    alter table public.mentorship_messages
      add constraint mentorship_messages_attachment_type_check
      check (attachment_type is null or attachment_type in ('image'));
  end if;
end $$;

create index if not exists mentorship_messages_attachment_path_idx
  on public.mentorship_messages (attachment_bucket, attachment_path)
  where attachment_path is not null;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'chat-attachments',
  'chat-attachments',
  false,
  6291456,
  array['image/png', 'image/jpeg', 'image/webp']
)
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;
