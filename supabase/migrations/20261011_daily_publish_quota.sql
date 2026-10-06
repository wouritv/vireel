-- Daily publication quota, configurable per plan, snapshotted per user.
--
-- abonnement.max_daily_publications: how many publications (one per
-- account/platform target, counted at request time whether the publish
-- is immediate or scheduled for later) an account on this plan may make
-- per calendar day (UTC). 0 (the default -- every existing plan keeps
-- today's unlimited behaviour) means unlimited; any positive number is
-- the daily cap.
alter table if exists public.abonnement
  add column if not exists max_daily_publications integer not null default 0;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'abonnement_max_daily_publications_check'
  ) then
    alter table public.abonnement
      add constraint abonnement_max_daily_publications_check
      check (max_daily_publications >= 0);
  end if;
end $$;

-- user_data gains the snapshot + the lazily-reset daily counter:
--   max_daily_publications: copied from the active plan at allocation
--     time (purchase/renewal/plan change -- see _allocate_plan_resources
--     in app.py), never re-derived live from abonnement at check time,
--     so it depends on the USER's own history rather than whatever the
--     plan happens to say today. Defaults to 0 (unlimited) for an
--     account that has never had a plan allocate it one yet.
--   publications_today / publications_count_date: how many publications
--     this account has made on publications_count_date (UTC calendar
--     day). Reset is lazy, not a scheduled job: a day mismatch at check
--     time is simply treated as a fresh count of 0 for that day (see
--     consume_publish_quota in supabase_request.py) -- correct without
--     needing a daily cron sweep.
alter table if exists public.user_data
  add column if not exists max_daily_publications integer not null default 0,
  add column if not exists publications_today integer not null default 0,
  add column if not exists publications_count_date date;
