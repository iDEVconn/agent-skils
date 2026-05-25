-- ============================================================
-- TEMPLATE: 002_extend_user_subscriptions_for_entitlements.sql
-- Copy to: supabase/migrations/<YYYYMMDDHHMMSS>_extend_user_subscriptions_for_entitlements.sql
-- IMPORTANT: Renumber the timestamp to sort after migration 001.
-- ============================================================

-- 1) Rename payment_provider → provider (entitlements pkg adapter expects "provider")
alter table user_subscriptions rename column payment_provider to provider;

-- 2) Add new columns required by the entitlements adapter + renewal flow
alter table user_subscriptions
  add column tenant_id text,
  add column started_at timestamptz,
  add column entitlements jsonb not null default '{}'::jsonb,
  add column last_order_id text,
  add column last_order_approve_url text;

-- Backfill started_at from created_at (no rows yet, but defensive); then enforce NOT NULL.
update user_subscriptions set started_at = coalesce(started_at, created_at);
alter table user_subscriptions alter column started_at set not null;

-- 3) Replace the partial unique index with the pkg-expected one.
--    The pkg upserts on (user_id, tenant_id). With single-tenant deployments tenant_id is NULL.
--    NULLS NOT DISTINCT (PG15+) ensures a unique-per-user row even when tenant_id is null.
drop index if exists user_subscriptions_one_active_idx;
create unique index user_subscriptions_user_tenant_uniq
  on user_subscriptions (user_id, tenant_id) nulls not distinct;

-- 4) Metered-usage table for the entitlements pkg consume() flow.
--    NOTE: No callers yet — pre-staged for future metered features. See reference-known-gaps.md.
create table entitlements_usage (
  id           uuid          primary key default gen_random_uuid(),
  user_id      uuid          not null references auth.users(id) on delete cascade,
  tenant_id    text,
  metric       text          not null,
  period_start timestamptz   not null,
  amount       integer       not null default 0,
  updated_at   timestamptz   not null default now()
);

create unique index entitlements_usage_uniq
  on entitlements_usage (user_id, tenant_id, metric, period_start)
  nulls not distinct;

create index entitlements_usage_user_idx on entitlements_usage(user_id);

-- 5) Capped atomic upsert RPC for future metered features.
--    Raises P0001 'LIMIT_EXCEEDED' when the cap would be breached.
create or replace function entitlements_increment_usage_capped(
  p_user_id      uuid,
  p_tenant_id    text,
  p_metric       text,
  p_period_start timestamptz,
  p_amount       int,
  p_limit        int
) returns int
language plpgsql
security definer
set search_path = public
as $$
declare
  v_new int;
begin
  insert into entitlements_usage (user_id, tenant_id, metric, period_start, amount)
  values (p_user_id, p_tenant_id, p_metric, p_period_start, p_amount)
  on conflict (user_id, tenant_id, metric, period_start)
  do update set
    amount     = entitlements_usage.amount + excluded.amount,
    updated_at = now()
  returning amount into v_new;

  if p_limit is not null and v_new > p_limit then
    raise exception 'LIMIT_EXCEEDED' using errcode = 'P0001';
  end if;

  return v_new;
end;
$$;

revoke all on function entitlements_increment_usage_capped(uuid, text, text, timestamptz, int, int) from public;
grant execute on function entitlements_increment_usage_capped(uuid, text, text, timestamptz, int, int) to service_role;

-- 6) RLS on entitlements_usage.
alter table entitlements_usage enable row level security;

create policy "users_read_own_entitlements_usage"
  on entitlements_usage
  for select
  using (auth.uid() = user_id);
