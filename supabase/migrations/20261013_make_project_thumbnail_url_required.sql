-- Make project thumbnail_url mandatory.
-- Existing rows are backfilled to an empty string first; application code
-- now auto-generates and persists a source-based thumbnail when missing.

alter table if exists public.projects
    alter column thumbnail_url set default '';

update public.projects
set thumbnail_url = ''
where thumbnail_url is null;

alter table if exists public.projects
    alter column thumbnail_url set not null;

