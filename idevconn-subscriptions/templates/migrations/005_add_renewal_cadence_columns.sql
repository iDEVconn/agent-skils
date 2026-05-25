-- ============================================================
-- TEMPLATE: 005_add_renewal_cadence_columns.sql
-- Copy to: supabase/migrations/<YYYYMMDDHHMMSS>_add_renewal_cadence_columns.sql
-- IMPORTANT: Renumber the timestamp to sort after migration 004.
-- ============================================================

-- Track renewal-reminder progress for the dunning cadence cron.
--
-- renewal_attempts:              how many T-1/T+1/T+3/T+7 nudges have been sent
--                                for the current billing period. Reset to 0 by
--                                SubscriptionsService.captureOrder() on success.
-- last_renewal_notification_at:  timestamp of the most recent notification.
--                                Used as an 18h throttle against accidental
--                                double-runs of the cron in the same day.

alter table user_subscriptions
  add column renewal_attempts int not null default 0,
  add column last_renewal_notification_at timestamptz;

-- Partial index: the cron only ever queries rows in active/past_due.
-- The WHERE clause keeps the index tiny as expired/canceled rows accumulate.
create index user_subscriptions_renewal_idx
  on user_subscriptions (status, current_period_end, last_renewal_notification_at)
  where status in ('active', 'past_due');
