-- Annual subscription billing.
--
-- abonnement.reduction_annuelle: discount RATE (fraction 0..1, e.g. 0.05 =
-- 5%) applied when a plan is billed annually instead of monthly.
--   annual_price = monthly_price * 12 * (1 - reduction_annuelle)
-- Defaults to 0 (no discount) so every existing plan keeps its current
-- monthly-only pricing until a rate is set explicitly, e.g.:
--   update public.abonnement set reduction_annuelle = 0.05 where name ilike '%creator%';
alter table if exists public.abonnement
  add column if not exists reduction_annuelle numeric(5, 4) not null default 0;

-- souscription gains:
--   billing_interval: 'month' (default, unchanged behaviour) or 'year'.
--   plan_credit / plan_stockage: the plan's credit/storage allowance,
--     snapshotted onto the row at the moment it was created (purchase,
--     renewal, or plan change) -- used instead of a live lookup on
--     abonnement so a later change to the plan catalog never retroactively
--     changes what an already-in-progress subscription grants (monthly or
--     annual alike). Nullable: legacy rows predating this migration have
--     no snapshot and are never read by the new monthly-refill job below
--     (it only looks at billing_interval = 'year' rows, all of which are
--     created with a snapshot going forward).
--   next_credit_allocation_at: for an annual subscription only, the next
--     calendar-month anniversary at which credit/storage must be reset to
--     the snapshot values (see process_annual_credit_refill_jobs in
--     app.py) -- Stripe itself only raises a renewal invoice once a year
--     for this subscription, so this column drives the monthly refill
--     independently of Stripe's own billing cycle. Null for monthly
--     subscriptions, which already get a fresh souscription row (and a
--     fresh allocation) every month via the existing renewal webhook.
alter table if exists public.souscription
  add column if not exists billing_interval text not null default 'month',
  add column if not exists plan_credit numeric(14, 2),
  add column if not exists plan_stockage numeric(14, 6),
  add column if not exists next_credit_allocation_at timestamptz;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'souscription_billing_interval_check'
  ) then
    alter table public.souscription
      add constraint souscription_billing_interval_check
      check (billing_interval in ('month', 'year'));
  end if;
end $$;

create index if not exists idx_souscription_annual_credit_allocation_due
    on public.souscription(next_credit_allocation_at)
    where billing_interval = 'year' and next_credit_allocation_at is not null;
