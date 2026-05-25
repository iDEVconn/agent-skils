-- ============================================================
-- TEMPLATE: 003_harden_entitlements_rpc_and_rls.sql
-- Copy to: supabase/migrations/<YYYYMMDDHHMMSS>_harden_entitlements_rpc_and_rls.sql
-- IMPORTANT: Renumber the timestamp to sort after migration 002.
-- ============================================================

-- Hardening on top of migration 002.
--
-- 1) Supabase's PostgREST auto-grants EXECUTE on RPCs to anon/authenticated roles,
--    overriding our `grant execute to service_role` from the previous migration.
--    Without an explicit revoke, anyone with the project's anon key could call
--    `entitlements_increment_usage_capped` via /rest/v1/rpc/... and increment any
--    user's counters or DoS legitimate users with LIMIT_EXCEEDED errors.
revoke execute on function public.entitlements_increment_usage_capped(uuid, text, text, timestamptz, int, int) from anon;
revoke execute on function public.entitlements_increment_usage_capped(uuid, text, text, timestamptz, int, int) from authenticated;

-- 2) Auth-RLS init-plan lint: `auth.uid()` in the policy re-evaluates per row.
--    Wrapping in `(select auth.uid())` lets Postgres compute it once per query.
drop policy if exists "users_read_own_entitlements_usage" on entitlements_usage;
create policy "users_read_own_entitlements_usage"
  on entitlements_usage
  for select
  using ((select auth.uid()) = user_id);
