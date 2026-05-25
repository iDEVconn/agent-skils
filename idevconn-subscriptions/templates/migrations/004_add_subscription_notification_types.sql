-- ============================================================
-- TEMPLATE: 004_add_subscription_notification_types.sql
-- Copy to: supabase/migrations/<YYYYMMDDHHMMSS>_add_subscription_notification_types.sql
-- IMPORTANT: Renumber the timestamp to sort after migration 003.
--
-- PREREQUISITE: A `notification_type` enum must already exist in your schema.
-- If it does not exist, replace the ALTER statements below with:
--   create type notification_type as enum (
--     'subscription_renewal',
--     'subscription_cancelled',
--     'subscription_reactivated'
--   );
-- And create a notifications table if SubscriptionsService needs one.
-- See reference-validation.md for the full stub.
--
-- PLACEHOLDER: Remove notification types that don't apply to your product,
-- or add additional ones your product needs.
-- ============================================================

-- Extend notification_type enum with subscription-lifecycle events.
-- ADD VALUE IF NOT EXISTS is idempotent and safe to re-run.

alter type notification_type add value if not exists 'subscription_renewal';
alter type notification_type add value if not exists 'subscription_cancelled';
alter type notification_type add value if not exists 'subscription_reactivated';
