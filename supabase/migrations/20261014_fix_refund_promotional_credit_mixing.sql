-- ============================================================
-- Fixes a billing bug: refund_user_credits (used both for a job's full
-- reservation refund on failure/cancellation, and for the settlement
-- delta when a job's actual cost came in under its reservation) always
-- credited the refunded amount straight into user_data.credit, even when
-- the original deduction had drawn from the user's promotional_credit_
-- batches pool first (deduct_user_credits always drains promo before
-- subscription credit -- see consume_promotional_credits).
--
-- That silently and permanently converted promotional credit into
-- subscription credit on every job whose reservation overshot its actual
-- cost -- e.g. reserve 50 credits (draining a 50-credit promo batch to
-- 0), actual cost 41, refund 9: the user ended up with their promo batch
-- stuck at amount_remaining=0 (should be 9) and their subscription
-- balance up by 9 credits it was never entitled to gain (500 -> 509).
--
-- restore_promotional_credits_headroom reverses a refund the same way
-- consume_promotional_credits drains one (tier ascending, then
-- soonest-expiry-first), refilling only the HEADROOM each batch already
-- has below its own amount_initial -- so it can never grow a batch past
-- what it originally held. Whatever the pool can't absorb is what the
-- caller still credits to user_data.credit.
--
-- undo_promotional_credits_headroom_restore is its exact-reversal pair,
-- used only on the rare path where the surrounding user_data update
-- ultimately fails after the restore already happened (mirrors how
-- consume_promotional_credits / restore_promotional_credits are already
-- paired for the deduction side).
-- ============================================================

create or replace function public.restore_promotional_credits_headroom(p_user_id uuid, p_amount numeric)
returns jsonb
language plpgsql
as $$
declare
  v_remaining numeric := greatest(p_amount, 0);
  v_restored  numeric := 0;
  v_batches   jsonb := '[]'::jsonb;
  v_batch     record;
  v_give      numeric;
begin
  if v_remaining <= 0 then
    return jsonb_build_object('restored', 0, 'batches', v_batches);
  end if;

  for v_batch in
    select id, amount_initial, amount_remaining
    from public.promotional_credit_batches
    where user_id = p_user_id
      and revoked_at is null
      and expires_at > now()
      and amount_remaining < amount_initial
    order by tier asc, expires_at asc
    for update
  loop
    exit when v_remaining <= 0;
    v_give := least(v_remaining, v_batch.amount_initial - v_batch.amount_remaining);
    if v_give <= 0 then
      continue;
    end if;

    update public.promotional_credit_batches
      set amount_remaining = amount_remaining + v_give
      where id = v_batch.id;

    v_restored := v_restored + v_give;
    v_remaining := v_remaining - v_give;
    v_batches := v_batches || jsonb_build_array(jsonb_build_object('id', v_batch.id, 'amount', v_give));
  end loop;

  return jsonb_build_object('restored', v_restored, 'batches', v_batches);
end;
$$;

create or replace function public.undo_promotional_credits_headroom_restore(p_batches jsonb)
returns void
language plpgsql
as $$
declare
  v_entry jsonb;
begin
  for v_entry in select * from jsonb_array_elements(coalesce(p_batches, '[]'::jsonb))
  loop
    update public.promotional_credit_batches
      set amount_remaining = greatest(0, amount_remaining - (v_entry->>'amount')::numeric)
      where id = (v_entry->>'id')::uuid;
  end loop;
end;
$$;
