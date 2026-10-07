-- Credit consumption order: promotional, then purchased, then subscription.
--
-- promotional_credit_batches already held independent expiring "lots" for
-- promotional credit (referrals, ...), drained first by
-- consume_promotional_credits (FEFO, see the referral-program migration).
-- Credits bought directly as a standalone top-up (_handle_credit_purchase
-- in app.py) used to be added as a plain delta straight into
-- user_data.credit instead -- indistinguishable from subscription credit,
-- with no expiration of their own, and silently WIPED by the next
-- subscription renewal's reset-to-plan-allowance (_reset_user_plan_balance),
-- since that reset always overwrites the whole credit field rather than
-- adding to it.
--
-- tier turns this same table into a two-tier ledger instead of building a
-- parallel one: tier 1 (promotional, the existing default) is always
-- drained before tier 2 (purchased), and each tier is still drained
-- earliest-expiry-first within itself. user_data.credit/credit_max is now
-- reserved for PURE subscription credit only -- a purchased top-up never
-- touches it, so it's never at risk of being wiped by a renewal reset or
-- zeroed by a failed subscription payment (see below).
alter table if exists public.promotional_credit_batches
  add column if not exists tier smallint not null default 1;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'promotional_credit_batches_tier_check'
  ) then
    alter table public.promotional_credit_batches
      add constraint promotional_credit_batches_tier_check
      check (tier in (1, 2));
  end if;
end $$;

drop index if exists idx_promotional_credit_batches_consumable;
create index if not exists idx_promotional_credit_batches_consumable
    on public.promotional_credit_batches(user_id, tier, expires_at)
    where revoked_at is null and amount_remaining > 0;

create or replace function public.consume_promotional_credits(p_user_id uuid, p_amount numeric)
returns jsonb
language plpgsql
as $$
declare
  v_remaining numeric := greatest(p_amount, 0);
  v_consumed  numeric := 0;
  v_batches   jsonb := '[]'::jsonb;
  v_batch     record;
  v_take      numeric;
begin
  if v_remaining <= 0 then
    return jsonb_build_object('consumed', 0, 'batches', v_batches);
  end if;

  -- tier asc first: every tier-1 (promotional) batch is drained before any
  -- tier-2 (purchased) batch is touched at all, regardless of which one
  -- expires sooner -- expires_at only breaks ties WITHIN a tier.
  for v_batch in
    select id, amount_remaining
    from public.promotional_credit_batches
    where user_id = p_user_id
      and revoked_at is null
      and expires_at > now()
      and amount_remaining > 0
    order by tier asc, expires_at asc
    for update
  loop
    exit when v_remaining <= 0;
    v_take := least(v_remaining, v_batch.amount_remaining);

    update public.promotional_credit_batches
      set amount_remaining = amount_remaining - v_take
      where id = v_batch.id;

    v_consumed := v_consumed + v_take;
    v_remaining := v_remaining - v_take;
    v_batches := v_batches || jsonb_build_array(jsonb_build_object('id', v_batch.id, 'amount', v_take));
  end loop;

  return jsonb_build_object('consumed', v_consumed, 'batches', v_batches);
end;
$$;

-- restore_promotional_credits needs no change -- it reverses specific
-- {id, amount} pairs by id, which is already tier-agnostic.
