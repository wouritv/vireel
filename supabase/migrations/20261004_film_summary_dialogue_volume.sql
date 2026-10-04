-- Removes the background-music feature entirely ("enleve tout ce qui a
-- trait a la musique de fond, c'est plus pertinent") and replaces it with a
-- single dialogue_volume setting: how loud the film's own original audio
-- is kept under the AI narration during voice_over segments, 0-100
-- (default 20). This also replaces the previous unconditional mute
-- (ORIGINAL_AUDIO_DUCK_VOLUME=0.0 in film_summary_render.py) with a
-- user-chosen value -- see duck_and_mix_narration's original_volume
-- parameter and update_film_summary_audio_settings_endpoint in app.py.
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
