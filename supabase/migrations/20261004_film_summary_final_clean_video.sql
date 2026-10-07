-- Supports adding/removing subtitles on an already-completed film summary
-- ("rajouter aussi le bloc de gestion de sous titres... a la fin il dois
-- pouvoir le faire s'il le desire... s'il ne veut plus de sous titres il
-- dois avoir un bouton pour revenir a la video initiale sans sous-titres").
--
-- final_clean_s3_key holds a backup copy of the final video from BEFORE any
-- post-completion subtitle burn-in, so the "remove subtitles" endpoint can
-- restore it. It is nullable and lazily populated: apply_film_summary_
-- subtitles_endpoint (app.py) only writes it the first time a user applies
-- subtitles post-completion, copying the then-current final_s3_key object
-- before overwriting it with the captioned version. It stays null for any
-- film summary that never goes through that flow.
--
-- 20261004_film_summary_dialogue_volume.sql was the most recent migration
-- against this table; left untouched, as always -- only ever add new
-- migrations, never rewrite history.

alter table if exists public.film_summaries
  add column if not exists final_clean_s3_key text;
