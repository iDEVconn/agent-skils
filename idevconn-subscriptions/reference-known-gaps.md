# Known Gaps & Production Hardening

This skill ports a working implementation from the warranty project. These are its known
shortcomings — document them upfront so the implementation team can make informed decisions.

---

## Gap 1 — No webhook-driven payment capture (closed-tab risk)

**Problem**: Payment capture is initiated by the browser redirect to `/subscriptions/success`.
If the user closes the tab after approving on PayPal but before the redirect completes, their
payment succeeds on PayPal but `user_subscriptions` is never upgraded. The `last_order_id` stash
mitigates double-capture, but there is no automatic recovery for the missed user.

**Current mitigation**: `last_order_id` is stored so a user who retries the success URL gets
their capture. Ops can look up uncaptured orders in PayPal and backfill manually.

**Production fix**: See [docs/future-paypal-subscriptions-api.md](docs/future-paypal-subscriptions-api.md).
Migration to PayPal Subscriptions API + `BILLING.SUBSCRIPTION.ACTIVATED` webhook closes this gap entirely.

---

## Gap 2 — Dormant metered usage RPC

**Problem**: `entitlements_usage` table and `entitlements_increment_usage_capped` SQL RPC
exist and are deployed, but no application code calls `entitlements.consume()` yet. If you
introduce metered features (e.g. AI API calls, storage quota), you must wire up the consumption
path in your feature endpoints.

**How to activate**:
1. Add `@RequireSubscription({ feature: 'your_metered_slug', consume: 1 })` to the endpoint
   (or call `entitlements.for({ userId }).consume('your_metered_slug')` programmatically).
2. The `@idevconn/isubscribe-entitlements` package calls `entitlements_increment_usage_capped`
   atomically — no extra code needed beyond the config in `entitlements.config.ts`.
3. The `entitlements_usage` table resets per billing period automatically (configured via the RPC's `period_start` param).

---

## Gap 3 — No PayPal recurring billing (manual renewal required)

**Problem**: This implementation uses PayPal Orders v2 (one-shot payments). Every renewal
requires a user to manually click an "approve" link sent via in-app notification. Industry data
puts manual-renewal completion rates 30–50% below auto-debit.

**Current mitigation**: The `SubscriptionsRenewalService` cron sends up to 4 dunning notifications
(stages 1–4 at T-1, T+1, T+3, T+7) and creates a fresh PayPal order for each. After T+14 the
subscription expires and falls back to Starter.

**Production fix**: Migrate to PayPal Subscriptions API. Full spec in
[docs/future-paypal-subscriptions-api.md](docs/future-paypal-subscriptions-api.md).
Estimated scope: ~20 engineering days.

---

## Gap 4 — In-process subscription cache is disabled

**Problem**: `cacheTtlMs: 0` in `entitlements.config.ts` forces the entitlements package to
hit Supabase on every gated API request. This ensures consistency in multi-process deployments
(no stale cache after a subscription change) but adds latency and DB load.

**Production fix**: Provide a Redis cache adapter to the entitlements package with a short TTL
(e.g. 5 minutes) and an invalidation event on `saveSubscription`. Not implemented yet.

---

## Gap 5 — No plan downgrade data handling

**Problem**: If a user downgrades from a high-limit plan (e.g. unlimited items) to a low-limit
plan (e.g. 5 items max) while having more items than the new limit, the system allows reads but
blocks new creates. Existing over-limit items are not archived, flagged, or pruned.

**Current behavior**: Gate `@RequireSubscription` on create endpoints only; reads are always
allowed regardless of plan limit.

**Production fix**: Implement a downgrade handler that marks over-limit rows as "locked" or
"read-only" and surfaces an archiving flow to the user.

---

## Gap 6 — No multi-currency support

**Problem**: `PaypalStrategy` creates single-currency orders. iSubscribe may serve plans in
multiple currencies, but the current code passes `plan.effectiveCurrency` directly to PayPal —
it does not normalize to a single target currency or handle per-user currency preferences.

**Impact**: If iSubscribe returns a plan in a currency not supported by the merchant's PayPal
account, the order creation will fail with a PayPal API error.

---

## Gap 7 — Admin bypass is hardcoded to `authService.isAdmin()`

**Problem**: `EntitlementsOrAdminGuard` calls `this.authService.isAdmin(userId)` — a warranty-specific
method. Every target project must implement this method or adapt the guard.

**How to adapt**: See PLACEHOLDER comment in `entitlements-or-admin.guard.ts.template`. If the
target project uses JWT role claims, replace with a synchronous check on `req.user.role`.

---

## Gap 8 — Renewal notifications require a `NotificationsService`

**Problem**: `SubscriptionsService` and `SubscriptionsRenewalService` inject `NotificationsService`
and call `this.notifications.create({ user_id, type, message, channel })`. This service and its
module must exist in the target project.

**If the target project has no notifications system**: stub `NotificationsService` with a no-op
`create()` method, or remove the notification calls and log to console instead.
