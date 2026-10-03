-- Foundations for the film-summary manual editor (clip selection ->
-- AI-generated narration, background music on a chosen final-video
-- range, and subtitle styling) -- see film_summary.py/app.py for the
-- endpoints/pipeline that read and write these.

alter table if exists public.film_summaries
  add column if not exists edit_mode text not null default 'automatic'
    check (edit_mode in ('automatic', 'manual')),
  -- The user's manually chosen plans (shots), in final-video order, each
  -- possibly trimmed from the auto-detected scene_index boundaries:
  -- [{"scene_id": "scene_003", "start_ms": 1200, "end_ms": 4800}, ...].
  -- Distinct from edit_plan.segments[].clips, which is the AI's own
  -- selection in automatic mode -- generate_narration_for_selected_clips
  -- (film_summary.py) turns this into a real edit_plan once the user
  -- confirms their selection.
  add column if not exists manual_selection jsonb,
  -- Relative to FILM_SUMMARY_MUSIC_DIR, e.g. "tense/epic_theme.mp3" --
  -- see film_summary_render.resolve_background_music_track, which this
  -- overrides with a specific user-chosen track instead of only an
  -- auto-picked one-per-mood.
  add column if not exists music_track_id text,
  -- Range on the FINAL assembled video's own timeline (milliseconds)
  -- where the music plays -- both null means the whole video (matches
  -- the pre-existing "every voice_over segment" default behavior).
  add column if not exists music_start_ms integer,
  add column if not exists music_end_ms integer,
  add column if not exists subtitles_enabled boolean not null default false,
  -- Same shape as caption_style_themes.style (20260927_create_caption_
  -- style_themes.sql) -- a snapshot, not a foreign key, so a later edit
  -- to a saved theme never silently changes a film summary that was
  -- styled from it.
  add column if not exists subtitle_style jsonb;
