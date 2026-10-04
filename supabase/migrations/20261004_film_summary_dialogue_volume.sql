-- Removes the background-music feature entirely ("enleve tout ce qui a
-- trait a la musique de fond, c'est plus pertinent") and replaces it with a
-- single dialogue_volume setting: how loud the film's own original audio
-- plays during original_dialogue segments in the montage, 0-100 (default
-- 20) -- see film_summary_render._build_original_segment_clip's
-- dialogue_volume parameter and update_film_summary_audio_settings_
-- endpoint in app.py. Never applies to voice_over segments: the film's own
-- voice must never be present while the AI narrator speaks ("la voix du
-- film ne dois pas etre presente pendant que le narrateur parle"), so that
-- audio is always fully replaced by the narration, unconditionally.
--
-- music_tracks was added by 20261003_film_summary_multi_track_music.sql;
-- that migration (and 20261003_film_summary_manual_editor_fields.sql
-- before it) is left untouched since it already ran against a real
-- database -- only ever add new migrations, never rewrite history.

alter table if exists public.film_summaries
  drop column if exists music_tracks;

alter table if exists public.film_summaries
  add column if not exists dialogue_volume integer not null default 20
    check (dialogue_volume between 0 and 100);
