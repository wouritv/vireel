-- Referral program: referral codes/relationships, a generic promotional
-- credits ledger (not referral-specific -- see promotional_credit_batches'
-- "source" column, meant to also cover future promo codes/marketing
-- campaigns/compensations), and a generic in-app notifications table.
--
-- Fully additive: no existing table's columns change shape, no existing
-- balances/transactions are touched. user_data/user_data_history keep
-- working exactly as before; promotional_credit_batches is a new,
-- separate ledger that deduct_user_credits (supabase_request.py) now
-- drains from first, before touching user_data.credit.

-- ----------------------------------------------------------------
-- referral_codes -- one unique shareable code per user, created lazily
-- the first time a user asks for their referral link (mirrors how
-- user_data itself is only created lazily on first credit grant --
-- there is no signup webhook/trigger in this codebase to pre-populate
-- this for every user up front).
-- ----------------------------------------------------------------
create table if not exists public.referral_codes (
    user_id    uuid primary key references auth.users(id) on delete cascade,
    code       text not null unique,
    created_at timestamptz not null default now()
);

-- ----------------------------------------------------------------
-- referrals -- one row per referred user, for the user's whole lifetime.
-- referred_user_id is UNIQUE: a user can never have more than one
-- referrer, and once set it is never changed (enforced here, not just in
-- application code).
-- ----------------------------------------------------------------
create table if not exists public.referrals (
    id                              uuid primary key default gen_random_uuid(),
    created_at                      timestamptz not null default now(),
    referrer_user_id                uuid not null references auth.users(id) on delete cascade,
    referred_user_id                uuid not null unique references auth.users(id) on delete cascade,
    referral_code                   text not null,
    -- pending: signed up, no paid subscription yet.
    -- rewarded: referrer's first-subscription reward has been granted.
    -- invalid: administratively invalidated (fraud/abuse) -- see
    -- invalidated_at/invalidated_reason; no further rewards from it.
    status                          text not null default 'pending'
                                     check (status in ('pending', 'rewarded', 'invalid')),
    signup_reward_granted_at        timestamptz,
    signup_reward_batch_id          uuid,
    first_subscription_type         text check (first_subscription_type in ('month', 'year')),
    first_subscription_souscription_id text,
    subscription_reward_granted_at  timestamptz,
    subscription_reward_batch_id    uuid,
    invalidated_at                  timestamptz,
    invalidated_reason              text,
    constraint referrals_no_self_referral check (referrer_user_id <> referred_user_id)
);

create index if not exists idx_referrals_referrer_user_id on public.referrals(referrer_user_id);

-- ----------------------------------------------------------------
-- promotional_credit_batches -- one independent "lot" per grant. Generic
-- on purpose (source is free-form, referral sources are just the first
-- three values used) so this becomes the shared base for any future
-- promotional-credit mechanism (promo codes, marketing campaigns,
-- goodwill compensation, ...) without a parallel credits system.
-- amount_initial is fixed at grant time from whatever the live config
-- was then -- a later env var change never touches existing batches.
-- ----------------------------------------------------------------
create table if not exists public.promotional_credit_batches (
    id              uuid primary key default gen_random_uuid(),
    created_at      timestamptz not null default now(),
    user_id         uuid not null references auth.users(id) on delete cascade,
    amount_initial  numeric(14, 2) not null check (amount_initial >= 0),
    amount_remaining numeric(14, 2) not null check (amount_remaining >= 0 and amount_remaining <= amount_initial),
    source          text not null,
    source_reference text,
    expires_at      timestamptz not null,
    revoked_at      timestamptz,
    revoked_reason  text
);

create index if not exists idx_promotional_credit_batches_consumable
    on public.promotional_credit_batches(user_id, expires_at)
    where revoked_at is null and amount_remaining > 0;

create index if not exists idx_promotional_credit_batches_source_reference
    on public.promotional_credit_batches(source_reference)
    where source_reference is not null;

-- referrals references these two batch ids, but promotional_credit_batches
-- didn't exist yet when referrals was created above -- added here instead.
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'referrals_signup_reward_batch_id_fkey') then
    alter table public.referrals
      add constraint referrals_signup_reward_batch_id_fkey
      foreign key (signup_reward_batch_id) references public.promotional_credit_batches(id);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'referrals_subscription_reward_batch_id_fkey') then
    alter table public.referrals
      add constraint referrals_subscription_reward_batch_id_fkey
      foreign key (subscription_reward_batch_id) references public.promotional_credit_batches(id);
  end if;
end $$;

-- ----------------------------------------------------------------
-- notifications -- generic in-app notifications (not email). Created by
-- the backend only (service role); a user can only read/mark-read their
-- own. "type" is free-form so this isn't referral-specific either.
-- ----------------------------------------------------------------
create table if not exists public.notifications (
    id         uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    user_id    uuid not null references auth.users(id) on delete cascade,
    type       text not null,
    title      text not null,
    body       text,
    data       jsonb not null default '{}'::jsonb,
    read_at    timestamptz
);

create index if not exists idx_notifications_user_created on public.notifications(user_id, created_at desc);
create index if not exists idx_notifications_user_unread on public.notifications(user_id) where read_at is null;

alter table public.referral_codes enable row level security;
alter table public.referrals enable row level security;
alter table public.promotional_credit_batches enable row level security;
alter table public.notifications enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'referral_codes' and policyname = 'referral_codes_select_own') then
    create policy referral_codes_select_own on public.referral_codes for select using (auth.uid() = user_id);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'referrals' and policyname = 'referrals_select_own') then
    create policy referrals_select_own on public.referrals for select using (auth.uid() = referrer_user_id or auth.uid() = referred_user_id);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'promotional_credit_batches' and policyname = 'promotional_credit_batches_select_own') then
    create policy promotional_credit_batches_select_own on public.promotional_credit_batches for select using (auth.uid() = user_id);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'notifications' and policyname = 'notifications_select_own') then
    create policy notifications_select_own on public.notifications for select using (auth.uid() = user_id);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'notifications' and policyname = 'notifications_update_own') then
    -- Only ever used by the owner to set read_at -- the backend itself
    -- writes (creates/reads/updates) via the service role, which bypasses
    -- RLS entirely, so this policy only matters if a client ever queries
    -- Supabase directly instead of going through the API.
    create policy notifications_update_own on public.notifications for update using (auth.uid() = user_id);
  end if;
end $$;

-- ----------------------------------------------------------------
-- consume_promotional_credits: atomically drains up to p_amount from
-- this user's active (not expired, not revoked) promotional batches,
-- oldest-expiry-first (FEFO), row-locking each batch it touches so two
-- concurrent spends on the same user can never double-consume the same
-- lot. Returns how much was actually consumed and exactly which
-- batches/amounts were drawn from, so a caller whose overall operation
-- subsequently fails (e.g. insufficient standard credits for the
-- remainder) can precisely reverse this via restore_promotional_credits
-- -- without that, a failed deduction would have evaporated a user's
-- promo credits for nothing.
-- ----------------------------------------------------------------
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

  for v_batch in
    select id, amount_remaining
    from public.promotional_credit_batches
    where user_id = p_user_id
      and revoked_at is null
      and expires_at > now()
      and amount_remaining > 0
    order by expires_at asc
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

-- Reverses exactly the {id, amount} pairs consume_promotional_credits
-- returned. Silently skips a batch that was revoked in the meantime
-- (e.g. a chargeback landed between the consume and this compensating
-- call) -- that credit is simply gone, which is the correct outcome: a
-- revoked batch must never grow again regardless of why.
create or replace function public.restore_promotional_credits(p_batches jsonb)
returns void
language plpgsql
as $$
declare
  v_entry jsonb;
begin
  for v_entry in select * from jsonb_array_elements(coalesce(p_batches, '[]'::jsonb))
  loop
    update public.promotional_credit_batches
      set amount_remaining = amount_remaining + (v_entry->>'amount')::numeric
      where id = (v_entry->>'id')::uuid
        and revoked_at is null;
  end loop;
end;
$$;
