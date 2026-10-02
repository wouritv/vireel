-- description (added in 20261002_add_description_fields_to_abonnement.sql
-- as a single text paragraph) is now a JSON array instead, same shape as
-- the existing "features" column -- AbonnementPage.jsx renders its items
-- as a list under the heading "Fonctionnalites IA incluses dans les
-- credits", separate from the plain feature checklist.
--
-- Any plain-text description already entered is preserved as a single-
-- element array rather than discarded, so nothing is silently lost; split
-- it into one value per AI-credit feature per plan afterwards -- same 4
-- features for every plan, each phrased with that plan's own limit, e.g.:
--   update public.abonnement set description = '[
--     "Sous-titrage des videos (duree max 5min / video)",
--     "Clipping / Generation de Reels (duree max. 2H / video)",
--     "Generation des histoires anonymes",
--     "Generation des resumes de films"
--   ]'::jsonb where name ilike '%silver%';
alter table if exists public.abonnement
  alter column description type jsonb
  using case
    when description is null or description = '' then '[]'::jsonb
    else to_jsonb(array[description])
  end;

alter table if exists public.abonnement
  alter column description set default '[]'::jsonb;
