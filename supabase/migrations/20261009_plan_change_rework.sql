-- Plan-change rework: separates the paid-billing-period dates from the
-- monthly credit-allocation-cycle dates (previously only implicit via
-- payment_start_date/payment_end_date + next_credit_allocation_at), and
-- adds the bookkeeping for a single pending scheduled plan/periodicity
-- change (section 4/5 of the spec).
--
-- credit_cycle_start_at / credit_cycle_end_at: the current monthly
-- credit-allocation window, distinct from payment_start_date/
-- payment_end_date:
--   * monthly subscription: identical to the payment period (a fresh
--     souscription row -- and so a fresh cycle -- is created every
--     monthly renewal anyway).
--   * annual subscription: a one-month-wide sub-window inside the paid
--     year, advanced by process_annual_credit_refill_jobs on every
--     monthly refill (see _process_due_annual_credit_refills in app.py).
-- Always populated going forward so proration math never has to branch
-- on billing_interval to find "the current credit cycle" -- it just
-- reads these two columns. Nullable for legacy rows that predate this
-- migration.
--
-- scheduled_abonnement_id / scheduled_billing_interval /
-- scheduled_effective_at / scheduled_created_at: the single pending
-- downgrade or periodicity change for this subscription (classification
-- "scheduled_downgrade" / "scheduled_periodicity_change" -- see
-- _classify_plan_change in app.py). Set when the user confirms such a
-- change, cleared on cancel/replace. scheduled_effective_at always
-- equals this row's own payment_end_date at scheduling time (next
-- monthly renewal for a monthly subscription, next ANNUAL renewal for an
-- annual one -- never the monthly credit-allocation anniversary).
--
-- stripe_schedule_id: the Stripe Subscription Schedule id driving the
-- pending change (see _schedule_plan_change in app.py) -- phase 2 of that
-- schedule carries the new plan/interval's price and metadata, so the
-- existing renewal webhook (_handle_subscription_renewal_invoice) applies
-- it unmodified at the correct boundary, with no parallel billing path.
-- Needed to release() the schedule on cancel/replace.
alter table if exists public.souscription
  add column if not exists credit_cycle_start_at timestamptz,
  add column if not exists credit_cycle_end_at timestamptz,
  add column if not exists scheduled_abonnement_id uuid references public.abonnement(id),
  add column if not exists scheduled_billing_interval text,
  add column if not exists scheduled_effective_at timestamptz,
  add column if not exists scheduled_created_at timestamptz,
  add column if not exists stripe_schedule_id text;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'souscription_scheduled_billing_interval_check'
  ) then
    alter table public.souscription
      add constraint souscription_scheduled_billing_interval_check
      check (scheduled_billing_interval is null or scheduled_billing_interval in ('month', 'year'));
  end if;
end $$;

-- Looked up whenever a plan change is requested, to enforce "only one
-- scheduled change at a time" and to drive the subscription-management
-- view's "scheduled change" panel.
create index if not exists idx_souscription_scheduled_change
    on public.souscription(userid)
    where scheduled_abonnement_id is not null;
