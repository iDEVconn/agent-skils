-- ============================================================
-- TEMPLATE: 007_create_payment_history.sql
-- Copy to: supabase/migrations/<YYYYMMDDHHMMSS>_create_payment_history.sql
-- IMPORTANT: Renumber the timestamp to sort after migration 006.
-- ============================================================

-- Append-only ledger of paid captures (and future addons/refunds).
--
-- Read by GET /api/subscriptions/orders; written by SubscriptionsService.captureOrder().
-- Unique(provider, provider_order_id) makes the INSERT idempotent — capture retries
-- swallow 23505 conflicts gracefully.

create type payment_kind as enum ('plan', 'addon', 'refund');

create table payment_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  kind payment_kind not null default 'plan',
  provider text not null,
  provider_order_id text,
  plan_id text,
  amount numeric(18, 2) not null,
  currency text not null,
  metadata jsonb not null default '{}',
  captured_at timestamptz not null default now()
);

create index payment_history_user_idx
  on payment_history (user_id, captured_at desc);

create unique index payment_history_dedup_idx
  on payment_history (provider, provider_order_id)
  where provider_order_id is not null;

alter table payment_history enable row level security;

create policy "users read own payment history"
  on payment_history for select
  using (user_id = auth.uid());
