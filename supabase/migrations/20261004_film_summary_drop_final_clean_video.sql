-- Reverses 20261004_film_summary_final_clean_video.sql: the post-
-- completion "add/remove subtitles" feature that column supported has been
-- removed again ("enleve le bloc sous titres dans la page de video finale
-- pour les resumes, garde uniquement les sous titres dans la phase de
-- validation du plan de scene"). Subtitles are now chosen only during the
-- awaiting_review phase (edit_mode/subtitles_enabled/subtitle_style),
-- applied automatically as the final generation step (see app.py's
-- _run_film_summary_render_pipeline_stages and the new
-- FilmSummaryStage.ADDING_SUBTITLES stage) -- nothing left reads or writes
-- final_clean_s3_key, so it's dropped rather than left as dead schema.
--
-- As always, only ever add new migrations -- the one that added this
-- column is left untouched.

alter table if exists public.film_summaries
  drop column if exists final_clean_s3_key;
