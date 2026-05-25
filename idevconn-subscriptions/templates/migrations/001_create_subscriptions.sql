-- ============================================================
-- TEMPLATE: 001_create_subscriptions.sql
-- Copy to: supabase/migrations/<YYYYMMDDHHMMSS>_create_subscriptions.sql
-- IMPORTANT: Renumber the timestamp to sort after your last migration.
--
-- PREREQUISITE: The update_updated_at() trigger function must exist before
-- this migration runs. If it doesn't, add it here or in a prior migration:
--   create or replace function update_updated_at() returns trigger as $$
--   begin new.updated_at = now(); return new; end;
--   $$ language plpgsql;
-- ============================================================

create type subscription_status as enum ('active', 'canceled', 'past_due', 'expired', 'incomplete');

create table user_subscriptions (
  id                       uuid                primary key default gen_random_uuid(),
  user_id                  uuid                not null references auth.users(id) on delete cascade,
  plan_id                  text                not null,
  plan_name                text,
  status                   subscription_status not null default 'incomplete',
  payment_provider         text                not null,
  provider_subscription_id text,
  provider_customer_id     text,
  current_period_start     timestamptz,
  current_period_end       timestamptz,
  cancel_at_period_end     boolean             not null default false,
  created_at               timestamptz         not null default now(),
  updated_at               timestamptz         not null default now()
);

create unique index user_subscriptions_one_active_idx
  on user_subscriptions(user_id)
  where status = 'active';

alter table user_subscriptions enable row level security;

create policy "users_read_own_subscription" on user_subscriptions
  for select using (auth.uid() = user_id);

create trigger set_user_subscriptions_updated_at
  before update on user_subscriptions
  for each row execute function update_updated_at();
