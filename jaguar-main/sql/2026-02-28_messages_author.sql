-- Add author and segment metadata for landing messages
alter table public.messages
  add column if not exists segment text default 'all',
  add column if not exists created_by uuid references public.profiles(id) on delete set null;

create index if not exists idx_messages_created_by on public.messages(created_by);
