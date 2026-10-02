-- Plan-page content fields for AbonnementPage.jsx's redesigned cards:
--   commentaire : how many comments a publication made under this plan is
--                 allowed to have (shown as a stat line on the plan card).
--   statistique : whether social-media metrics are shown on the dashboard
--                 home page for this plan (shown as an included/excluded
--                 feature line).
--   cible       : short tagline describing who the plan is aimed at
--                 (e.g. "Createurs solo", "Agences"), shown under the
--                 plan name.
--   description : short paragraph describing the plan, shown under cible.
--
-- No safe default exists for the marketing copy (cible/description) or
-- the real per-plan comment allowance -- unlike max_social_account's
-- migration (20260930), these aren't derivable from existing columns.
-- Added nullable/zero-valued and must be filled in per plan afterwards,
-- e.g.:
--   update public.abonnement set commentaire = 10,  cible = '...', description = '...' where name ilike '%silver%';
--   update public.abonnement set commentaire = 50,  cible = '...', description = '...' where name ilike '%gold%';
--   update public.abonnement set commentaire = 200, cible = '...', description = '...' where name ilike '%ultimate%';
--   update public.abonnement set commentaire = ...,  cible = '...', description = '...' where name ilike '%<4th plan>%';
alter table if exists public.abonnement
  add column if not exists commentaire integer not null default 0,
  add column if not exists statistique boolean not null default false,
  add column if not exists cible text,
  add column if not exists description text;
