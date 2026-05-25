-- ============================================================
-- TEMPLATE: 006_add_subscription_expired_notification_type.sql
-- Copy to: supabase/migrations/<YYYYMMDDHHMMSS>_add_subscription_expired_notification_type.sql
-- IMPORTANT: Renumber the timestamp to sort after migration 005.
-- ============================================================

-- Adds the terminal notification type emitted when a subscription crosses
-- T+14 past_due and is moved to 'expired' by the cron.
--
-- ADD VALUE IF NOT EXISTS is idempotent and safe to re-run.

alter type notification_type add value if not exists 'subscription_expired';
