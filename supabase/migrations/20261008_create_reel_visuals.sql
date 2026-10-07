-- Manual visuals on a Reel: user-uploaded images shown as a split-screen
-- (video + image) during a specific time window, then back to full-screen
-- video. Entirely manual -- no AI involved anywhere in this table or the
-- pipeline that reads it.
--
-- A dedicated child table (not a jsonb column on reels) so each visual is
-- independently addressable (its own id, own CRUD, own S3 key) -- mirrors
-- the existing style_edit_versions pattern (one row per user-configurable
-- "thing" attached to a reel/clip) rather than inventing a new shape.
--
-- V1 is intentionally narrow (visual_type is always 'IMAGE', layout always
-- 'SPLIT', position only 'TOP'/'BOTTOM') but the columns are named/typed so
-- a later version can widen the check constraints (VIDEO/GIF visual_type,
-- OVERLAY layout, LEFT/RIGHT position) without a schema rewrite.
create table if not exists public.reel_visuals (
    id          uuid primary key default gen_random_uuid(),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    reel_id     uuid not null references public.reels(id) on delete cascade,
    user_id     uuid not null references auth.users(id) on delete cascade,
    visual_type text not null default 'IMAGE' check (visual_type in ('IMAGE')),
    layout      text not null default 'SPLIT' check (layout in ('SPLIT')),
    position    text not null check (position in ('TOP', 'BOTTOM')),
    fit         text not null default 'COVER' check (fit in ('COVER')),
    image_s3_key text not null,
    start_time  numeric(10, 3) not null check (start_time >= 0),
    duration    numeric(10, 3) not null check (duration > 0)
);

create index if not exists idx_reel_visuals_reel_id on public.reel_visuals(reel_id);

create or replace function public.set_reel_visual_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_set_reel_visual_updated_at on public.reel_visuals;
create trigger trg_set_reel_visual_updated_at
before update on public.reel_visuals
for each row
execute function public.set_reel_visual_updated_at();

alter table public.reel_visuals enable row level security;

drop policy if exists reel_visuals_select_own on public.reel_visuals;
create policy reel_visuals_select_own
on public.reel_visuals for select to authenticated
using (user_id = auth.uid());

drop policy if exists reel_visuals_insert_own on public.reel_visuals;
create policy reel_visuals_insert_own
on public.reel_visuals for insert to authenticated
with check (user_id = auth.uid());

drop policy if exists reel_visuals_update_own on public.reel_visuals;
create policy reel_visuals_update_own
on public.reel_visuals for update to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists reel_visuals_delete_own on public.reel_visuals;
create policy reel_visuals_delete_own
on public.reel_visuals for delete to authenticated
using (user_id = auth.uid());
