-- ordre: explicit display order for the pricing page (AbonnementPage.jsx)
-- and the change-plan picker, replacing the previous implicit
-- created_at ordering (list_abonnements in supabase_request.py), which
-- had nothing to do with how plans should actually be presented.
--
-- Nullable on purpose: a plan with no ordre set is treated as not ready
-- to sell (/api/abonnements filters it out in app.py) without deleting
-- the row -- get_abonnement/supabase_get_abonnement by id still resolves
-- it directly, so an existing subscriber's history/plan name keeps
-- working even after their plan is retired from the public page.
alter table if exists public.abonnement
  add column if not exists ordre integer;

-- Best-effort seed from the existing priorite tier so every current plan
-- stays visible with a sensible relative order immediately after this
-- migration, instead of all going null (and so disappearing from the
-- pricing page) until manually set. Adjust precisely afterwards, e.g.:
--   update public.abonnement set ordre = 1 where name ilike '%discover%';
--   update public.abonnement set ordre = 2 where name ilike '%publish%';
--   update public.abonnement set ordre = 3 where name ilike '%creator%';
--   update public.abonnement set ordre = 4 where name ilike '%studio%';
update public.abonnement set ordre = priorite where ordre is null;
