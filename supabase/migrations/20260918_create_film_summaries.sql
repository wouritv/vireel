-- Film Summary ("Resume de film"): upload/YouTube movie -> technical +
-- narrative-film validation -> transcript + scene index -> AI-generated
-- edit plan -> user review -> TTS voice-over + FFmpeg assembly.
-- Mirrors the anonymous_stories table shape (20260911_create_anonymous_
-- stories.sql): the source video and transcript are tracked via
-- source_* columns + the existing public.transcriptions table
-- (job_id/clip_index=0); this table owns the editorial/plan content and
-- its lifecycle, same convention as the rest of this codebase.

create extension if not exists pgcrypto;

create table if not exists public.film_summaries (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    project_id uuid,
    title text,
    source_type text not null check (source_type in ('upload', 'youtube')),
    source_url text,
    source_s3_key text,
    source_duration_seconds integer,
    target_duration_seconds integer,
    source_language text,
    narration_language text,
    narration_style text default 'cinematic',
    voice_id text,
    status text not null default 'draft' check (
        status in ('draft', 'queued', 'processing', 'awaiting_review', 'rendering', 'completed', 'failed', 'rejected', 'cancelled')
    ),
    stage text check (
        stage in (
            'uploading', 'validating_media', 'validating_film', 'transcribing', 'detecting_scenes',
            'planning', 'validating_plan', 'awaiting_user_review', 'generating_voice',
            'rendering_preview', 'rendering_final', 'completed', 'rejected', 'failed', 'cancelled'
        )
    ),
    job_id text,
    film_confidence numeric(4, 3),
    classification jsonb not null default '{}'::jsonb,
    transcript_segments jsonb not null default '[]'::jsonb,
    scene_index jsonb not null default '[]'::jsonb,
    edit_plan jsonb not null default '{}'::jsonb,
    validation_report jsonb not null default '{}'::jsonb,
    preview_s3_key text,
    final_s3_key text,
    rejection_reason text,
    error_code text,
    error_message text,
    billing_details jsonb not null default '{}'::jsonb,
    total_cost_usd numeric(14, 6) not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    deleted_at timestamptz
);

create index if not exists idx_film_summaries_user_created
    on public.film_summaries (user_id, created_at desc);
create index if not exists idx_film_summaries_status
    on public.film_summaries (status);
create index if not exists idx_film_summaries_job
    on public.film_summaries (job_id);
create index if not exists idx_film_summaries_deleted
    on public.film_summaries (deleted_at);

create or replace function public.set_film_summaries_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_set_film_summaries_updated_at on public.film_summaries;
create trigger trg_set_film_summaries_updated_at
before update on public.film_summaries
for each row
execute function public.set_film_summaries_updated_at();

alter table public.film_summaries enable row level security;

drop policy if exists film_summaries_select_own on public.film_summaries;
create policy film_summaries_select_own
on public.film_summaries
for select
to authenticated
using (user_id = auth.uid());

drop policy if exists film_summaries_insert_own on public.film_summaries;
create policy film_summaries_insert_own
on public.film_summaries
for insert
to authenticated
with check (user_id = auth.uid());

drop policy if exists film_summaries_update_own on public.film_summaries;
create policy film_summaries_update_own
on public.film_summaries
for update
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists film_summaries_delete_own on public.film_summaries;
create policy film_summaries_delete_own
on public.film_summaries
for delete
to authenticated
using (user_id = auth.uid());

-- Bring film_summaries into the same shared "project" model reels,
-- captions and anonymous_stories already use (see
-- 20260912_link_anonymous_stories_to_projects.sql for the equivalent step).
alter table public.projects
    drop constraint if exists projects_project_type_check;
alter table public.projects
    add constraint projects_project_type_check
    check (project_type in ('reel', 'caption', 'anonymous_story', 'film_summary'));

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'film_summaries_project_id_fkey'
  ) then
    alter table public.film_summaries
      add constraint film_summaries_project_id_fkey
      foreign key (project_id) references public.projects(id) on delete cascade;
  end if;
end $$;
