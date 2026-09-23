-- Subscriptions now go through Stripe's own recurring billing (mode
-- "subscription") instead of a one-off Checkout payment per month, so
-- renewal invoices need a way back to the Stripe Subscription/Customer
-- that raised them (see _handle_subscription_renewal_invoice in app.py).

alter table if exists public.souscription
    add column if not exists stripe_subscription_id text,
    add column if not exists stripe_customer_id text;

create index if not exists idx_souscription_stripe_subscription_id
    on public.souscription(stripe_subscription_id)
    where stripe_subscription_id is not null;

create index if not exists idx_souscription_stripe_customer_id
    on public.souscription(stripe_customer_id)
    where stripe_customer_id is not null;
