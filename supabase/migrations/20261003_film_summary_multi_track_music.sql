-- Replaces the manual editor's single music_track_id/music_start_ms/
-- music_end_ms columns (20261003_film_summary_manual_editor_fields.sql)
-- with a list, so a film summary can layer several background tracks,
-- each covering its own range on the final video (e.g. one track under
-- the first act, a different one under the climax) instead of exactly
-- one track for the whole thing.
--
-- Shape: [{"track_id": "tense/epic_theme.mp3", "start_ms": 0, "end_ms": 42000}, ...]
-- (track_id as film_summary_render.MUSIC_DIR-relative paths, start_ms/
-- end_ms on the FINAL assembled video's own timeline, same meaning as the
-- single-entry fields they replace). An empty list means no background
-- music at all, matching the old all-null case.

alter table if exists public.film_summaries
  add column if not exists music_tracks jsonb not null default '[]'::jsonb;

-- Backfill any film summary that already has a single track selected
-- (saved before this migration ran) into the new list shape, so nothing
-- picked during the rollout window is silently dropped.
update public.film_summaries
set music_tracks = jsonb_build_array(
  jsonb_strip_nulls(jsonb_build_object('track_id', music_track_id, 'start_ms', music_start_ms, 'end_ms', music_end_ms))
)
where music_track_id is not null
  and (music_tracks is null or jsonb_array_length(music_tracks) = 0);

alter table if exists public.film_summaries
  drop column if exists music_track_id,
  drop column if exists music_start_ms,
  drop column if exists music_end_ms;
