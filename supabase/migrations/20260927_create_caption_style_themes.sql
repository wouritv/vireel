-- User-saved subtitle style presets ("themes") for the CaptionsModal theme
-- picker. Built-in themes are static frontend data (dashboard/src/lib/
-- captionThemes.js) and never stored here -- this table only holds each
-- user's own customized/saved themes.

create extension if not exists pgcrypto;

create table if not exists public.caption_style_themes (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    name text not null,
    style jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint caption_style_themes_user_name_unique unique (user_id, name)
);

create index if not exists idx_caption_style_themes_user
    on public.caption_style_themes (user_id, updated_at desc);

create or replace function public.set_caption_style_themes_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_set_caption_style_themes_updated_at on public.caption_style_themes;
create trigger trg_set_caption_style_themes_updated_at
before update on public.caption_style_themes
for each row
execute function public.set_caption_style_themes_updated_at();

alter table public.caption_style_themes enable row level security;

drop policy if exists caption_style_themes_select_own on public.caption_style_themes;
create policy caption_style_themes_select_own
on public.caption_style_themes
for select
to authenticated
using (user_id = auth.uid());

drop policy if exists caption_style_themes_insert_own on public.caption_style_themes;
create policy caption_style_themes_insert_own
on public.caption_style_themes
for insert
to authenticated
with check (user_id = auth.uid());

drop policy if exists caption_style_themes_update_own on public.caption_style_themes;
create policy caption_style_themes_update_own
on public.caption_style_themes
for update
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists caption_style_themes_delete_own on public.caption_style_themes;
create policy caption_style_themes_delete_own
on public.caption_style_themes
for delete
to authenticated
using (user_id = auth.uid());
