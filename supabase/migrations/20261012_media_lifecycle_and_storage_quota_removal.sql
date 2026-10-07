-- Storage quota removal + media lifecycle/retention tracking.
--
-- Storage stops being a commercial quota sold to the user (no more "X Go
-- / Y Go used", no storage add-on, no plan-tied Go allowance -- credits
-- are the only consumption unit the user ever sees). Internally, Vireel
-- still needs to know how long it physically keeps each media file and
-- what that costs -- see retention_config.py (the durations/rate,
-- env-configured) and billing.py's add_retention_cost_to_breakdown (the
-- formula, additive to the existing credit cost, reusing the exact same
-- USD->credits converter -- never a parallel billing system).
--
-- abonnement.stockage (the plan's advertised storage allowance) is
-- dropped outright: it's a pure catalog/commercial-feature column with
-- no per-user history behind it -- removing it loses nothing but the
-- advertised feature itself, which is exactly what's being removed.
-- souscription.plan_stockage and user_data.stockage/stockage_max are
-- NOT touched by this migration: those are historical snapshot/ledger
-- columns on USER rows (subscription history, usage bookkeeping) -- per
-- "sans perdre... historiques de facturation", they stay in place,
-- simply inert now that nothing reads them for enforcement or display
-- (see app.py's removal of _assert_user_has_storage_headroom and the
-- plan-change storage-overage check in this same change).
alter table if exists public.abonnement
  drop column if exists stockage;

-- ---------------------------------------------------------------------
-- media_assets: the physical-lifecycle registry for every media file
-- Vireel stores in S3 -- one row per source upload (projects) or
-- produced deliverable (reels/captions/film_summaries/anonymous_stories).
-- This is intentionally a NEW, separate table rather than bolted onto
-- each of those four differently-shaped content tables: the three
-- lifecycle jobs (expiration, expiry notification, temp-file cleanup --
-- see app.py) need to scan "every media file due for X" in one place
-- regardless of which content table it came from, and a project/reel/
-- caption/etc. row must stay fully readable (history, project listing)
-- even after its physical file is gone -- this table, not the content
-- row itself, is what disappears-in-spirit (media_status) while the
-- content row never does.
--
-- content_kind + content_id link back to the owning row (reels.id,
-- captions.id, film_summaries.id, anonymous_stories.id, or projects.id
-- for a source upload) -- no foreign key across these (different
-- tables), enforced instead by content_kind's check constraint and by
-- application code only ever writing one of those five kinds.
--
-- subscription_status_at_creation / retention_days / retention_started_at
-- / retention_expires_at are fixed FOREVER at insert time (see
-- retention_config.resolve_retention_days + app.py's
-- _finalize_media_retention_billing) -- never recomputed later. A later
-- env var change, or the user subscribing/unsubscribing afterward, never
-- touches an already-created media's row.
--
-- The billing decomposition this table doesn't itself hold (existing AI/
-- processing/S3-operation costs) already lives in jobs.cost_breakdown
-- (see job_manager.py's JobManager.complete_job) -- job_id here is the
-- join key to reconstruct the full picture, rather than duplicating
-- those fields onto this table too.
create table if not exists public.media_assets (
    id                              uuid primary key default gen_random_uuid(),
    created_at                      timestamptz not null default now(),
    user_id                         uuid not null references auth.users(id) on delete cascade,
    content_kind                    text not null check (content_kind in (
                                        'project_source', 'reel', 'caption', 'film_summary', 'anonymous_story'
                                     )),
    content_id                      uuid not null,
    job_id                          text,
    media_type                      text not null check (media_type in ('source', 'produced')),
    s3_bucket                       text,
    s3_key                          text,
    size_bytes                      bigint,
    subscription_status_at_creation text not null check (subscription_status_at_creation in ('active', 'free')),
    retention_days                  integer not null check (retention_days >= 0),
    retention_started_at            timestamptz not null,
    retention_expires_at            timestamptz not null,
    -- Billing snapshot for this media's retention component specifically
    -- (see billing.py's estimate_retention_storage_cost_usd) -- fixed at
    -- the moment the cost was computed, so a later env var change can
    -- never retroactively change how an already-billed media reads in
    -- the audit trail.
    s3_storage_cost_per_gb_day      numeric(14, 8),
    retention_storage_cost_usd      numeric(14, 6),
    retention_storage_credit_cost   numeric(14, 2),
    billing_created_at              timestamptz,
    media_status                    text not null default 'AVAILABLE' check (media_status in (
                                        'AVAILABLE', 'EXPIRED', 'DELETED', 'MISSING'
                                     )),
    media_deleted_at                timestamptz,
    -- Set the first (and only) time the "download it before it's gone"
    -- notification fires for this media -- see
    -- process_media_expiry_notification_jobs in app.py. NULL means not
    -- yet notified; never cleared/reset once set, so a given expiry can
    -- only ever produce one notification.
    notified_before_expiry_at       timestamptz
);

create unique index if not exists idx_media_assets_content
    on public.media_assets(content_kind, content_id);

-- The expiration sweep's own query shape exactly: due AVAILABLE media,
-- soonest-expiring first.
create index if not exists idx_media_assets_due_for_expiration
    on public.media_assets(retention_expires_at)
    where media_status = 'AVAILABLE';

-- The notification sweep only ever considers PRODUCED media that hasn't
-- been notified yet (see the module docstring on
-- process_media_expiry_notification_jobs: source media is never
-- notified, to avoid notification overload).
create index if not exists idx_media_assets_notification_due
    on public.media_assets(retention_expires_at)
    where media_status = 'AVAILABLE' and media_type = 'produced' and notified_before_expiry_at is null;

create index if not exists idx_media_assets_user_created
    on public.media_assets(user_id, created_at desc);

alter table public.media_assets enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'media_assets' and policyname = 'media_assets_select_own'
  ) then
    create policy media_assets_select_own on public.media_assets for select using (auth.uid() = user_id);
  end if;
end $$;

-- ---------------------------------------------------------------------
-- Migration-of-the-existing note (no backfill DML in this migration):
--
-- Every reel/caption/film_summary/anonymous_story/project row created
-- BEFORE this migration has no media_assets row at all, and therefore no
-- retention_expires_at -- it is simply never selected by the expiration/
-- notification sweeps (both scan media_assets, not the content tables),
-- so historical media is retained indefinitely until a deliberate,
-- separate follow-up migration decides to backfill it. This is the
-- explicit, safe strategy required: it is IMPOSSIBLE for historical
-- media to be mass-expired by the first run of the new retention jobs,
-- because none of it is in the table those jobs read from.
