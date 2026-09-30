-- max_social_account: how many accounts of EACH social platform a plan
-- allows a user to connect at once (e.g. Gold = 3 means up to 3 Facebook
-- Pages AND up to 3 Instagram accounts AND up to 3 YouTube channels, not
-- 3 total across every platform). Enforced in app.py's
-- _upsert_social_account, checked again in change_souscription_plan
-- before letting a downgrade through.
alter table if exists public.abonnement
  add column if not exists max_social_account integer not null default 1;

-- Best-effort seed: `abonnement` predates this repo's tracked migration
-- history (see 20260908_enable_rls_souscription_abonnement.sql), so its
-- exact row set/casing can't be verified from code. Matches both the
-- existing `priorite` tier (1=Silver, 2=Gold, 3=Ultimate -- see
-- get_user_abonnement's clamp in supabase_request.py) and the plan name,
-- so either signal being off doesn't leave a plan unseeded. Verify with
-- `select name, priorite, max_social_account from abonnement;` afterwards.
update public.abonnement set max_social_account = 1  where priorite = 1 or name ilike '%silver%';
update public.abonnement set max_social_account = 3  where priorite = 2 or name ilike '%gold%';
update public.abonnement set max_social_account = 10 where priorite = 3 or name ilike '%ultimate%';

-- social_accounts previously allowed only one row per (user_id, platform),
-- overwritten on every reconnect. Relaxed to allow several accounts of the
-- same platform (e.g. several Facebook Pages), still deduplicated on the
-- actual external account (platform_user_id) so reconnecting/reauthorizing
-- the same page updates its existing row instead of creating a duplicate.
alter table public.social_accounts
  drop constraint if exists social_accounts_user_platform_key;

alter table public.social_accounts
  add constraint social_accounts_user_platform_account_key
  unique (user_id, platform, platform_user_id);
