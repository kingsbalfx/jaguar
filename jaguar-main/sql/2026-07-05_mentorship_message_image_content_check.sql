-- Allow live chat image messages while keeping text messages protected.
-- Run after 2026-07-03_chat_image_attachments.sql, or run directly because it also ensures the attachment columns exist.

alter table public.mentorship_messages
  add column if not exists attachment_type text,
  add column if not exists attachment_bucket text,
  add column if not exists attachment_path text,
  add column if not exists attachment_name text,
  add column if not exists attachment_size bigint,
  add column if not exists attachment_metadata jsonb not null default '{}'::jsonb;

alter table public.mentorship_messages
  drop constraint if exists mentorship_messages_content_check;

alter table public.mentorship_messages
  add constraint mentorship_messages_content_check
  check (
    char_length(coalesce(content, '')) between 1 and 10000
    or (
      attachment_type = 'image'
      and attachment_path is not null
      and char_length(coalesce(content, '')) <= 10000
    )
  );