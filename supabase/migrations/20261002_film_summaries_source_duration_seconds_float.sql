-- _persist_film_summary_row (app.py) stores the full-precision float
-- duration instead of truncating to a whole second -- a deliberate fix
-- for a precision-loss bug where a segment valid against the
-- full-precision duration used at plan-generation time could later fail
-- render_film_summary_endpoint's "timecode hors limites" check, which
-- recomputes source_duration_ms from this same stored value.
--
-- That fix assumed the column could hold a float, but it was declared
-- integer (20260918_create_film_summaries.sql) -- inserting a value like
-- 2667.903129 fails outright with "invalid input syntax for type
-- integer" (22P02), breaking every new film summary at creation.
alter table if exists public.film_summaries
  alter column source_duration_seconds type double precision;
