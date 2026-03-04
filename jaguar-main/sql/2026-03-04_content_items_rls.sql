-- Content items (mentorship uploads) + RLS policies

create table if not exists public.content_items (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text,
  segment text default 'all',
  media_type text not null,
  media_url text,
  storage_path text,
  public_url text,
  body text,
  is_published boolean default true,
  created_at timestamp default current_timestamp,
  updated_at timestamp default current_timestamp
);

drop trigger if exists update_content_items_timestamp on public.content_items;
create trigger update_content_items_timestamp
before update on public.content_items
for each row execute function public.update_timestamp();

create index if not exists idx_content_items_segment on public.content_items(segment);
create index if not exists idx_content_items_published on public.content_items(is_published);
create index if not exists idx_content_items_created_at on public.content_items(created_at desc);

alter table public.content_items enable row level security;

drop policy if exists content_items_read_published on public.content_items;
create policy content_items_read_published on public.content_items
  for select using (is_published = true);

drop policy if exists content_items_admin_all on public.content_items;
create policy content_items_admin_all on public.content_items
  for all using (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  )
  with check (
    auth.role() = 'service_role' or
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  );

-- Storage RLS for mentorship uploads (buckets: public, premium, vip, pro, lifetime)
alter table storage.objects enable row level security;

drop policy if exists storage_admin_write on storage.objects;
create policy storage_admin_write on storage.objects
  for all to authenticated
  using (
    bucket_id in ('public','premium','vip','pro','lifetime') and
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  )
  with check (
    bucket_id in ('public','premium','vip','pro','lifetime') and
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
  );

drop policy if exists storage_authenticated_read on storage.objects;
create policy storage_authenticated_read on storage.objects
  for select to authenticated
  using (bucket_id in ('public','premium','vip','pro','lifetime'));
