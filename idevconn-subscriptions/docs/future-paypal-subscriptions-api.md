# Migration to PayPal Subscriptions API — Design (Planning Only)

> **Status: design / planning only.** No implementation work approved yet.
> The Reminder Cadence design (`2026-05-20-renewal-cadence-design.md`) ships
> first as a tactical fix; this spec sketches the strategic replacement.

## Context

The platform currently bills paid subscriptions through PayPal's **Orders v2 API**, treating each monthly renewal as a brand-new order that the user must manually approve. The cron job (`SubscriptionsRenewalService`) nudges the user once per attempt, but PayPal itself does no auto-debit, holds no billing agreement, and emits no recurring-payment webhooks.

This works but has three structural costs:

1. **Churn risk.** Every renewal requires an active user click. Industry data puts manual-renewal completion rates 30–50 % below auto-debit.
2. **Operational complexity.** We re-implement dunning, expiry, and grace periods in our own cron rather than relying on PayPal's billing engine.
3. **No source of truth on payments.** Capture happens via redirect, not webhook. Closed-tab / lost-network races leave the user paid-but-not-upgraded (a known bug, partially mitigated by the `last_order_id` stash).

PayPal's **Subscriptions API** (`/v1/billing/subscriptions` + `/v1/billing/plans`) addresses all three: PayPal manages the billing agreement, debits on schedule, and emits granular webhooks for payment success, failure, suspension, and cancellation.

## Goal

Migrate paid subscription billing from Orders v2 to Subscriptions v1. After the migration:

- A new paid subscriber creates a PayPal Subscription resource (not an Order). PayPal debits monthly without further user action.
- Webhooks drive all state transitions in `user_subscriptions`. The cron disappears entirely (or shrinks to a janitor for orphaned rows).
- Failed payments enter PayPal's own retry sequence (3 attempts over ~5 days), then suspend the subscription. We mirror their state machine.
- The user can cancel from within the app; we call PayPal `/cancel` and mirror the state.

## Non-goals

- Free-tier flow. Still cron-renews in place (`provider === 'none'`).
- Other payment providers. Stripe, etc. remain a future strategy swap.
- Plan version migration. Plans defined in iSubscription continue to be the source of truth; we register a PayPal billing plan per iSub plan.
- Grandfather migration of existing Orders-based subscriptions. Handled as a one-time cutover, not a per-user opt-in.

## Architecture overview

### High-level data flow

```
1. User clicks Subscribe
   → POST /api/subscriptions { planId }
   → API ensures PayPal billing plan exists (lazy registration)
   → API calls @idevconn/payment .createSubscription({ paypalPlanId, returnUrl, cancelUrl })
   → API stashes { provider_subscription_id, status: 'incomplete' } on user_subscriptions
   → Returns { approveUrl }; client redirects user

2. User approves in PayPal
   → PayPal sends webhook BILLING.SUBSCRIPTION.ACTIVATED
   → API webhook handler verifies signature, flips status='active', fills period dates

3. Monthly debit (PayPal-side, no user action)
   → Webhook PAYMENT.SALE.COMPLETED
   → API updates current_period_start/end, emits "subscription renewed" notification (optional)

4. Failed debit
   → Webhook PAYMENT.SALE.DENIED (per attempt) + BILLING.SUBSCRIPTION.PAYMENT.FAILED
   → API logs, sends "payment failed" notification; PayPal retries internally
   → After PayPal's retry exhaustion: BILLING.SUBSCRIPTION.SUSPENDED → status='past_due'
   → User can reactivate by updating payment method via PayPal portal

5. User cancels in app
   → POST /api/subscriptions/cancel
   → API calls @idevconn/payment .cancelSubscription(provider_subscription_id, reason)
   → PayPal acknowledges; webhook BILLING.SUBSCRIPTION.CANCELLED confirms
   → API sets status='canceled', cancel_at_period_end=true (keeps access to period_end)
```

### Component changes

#### `@idevconn/payment` (pkg)

New methods on `PaymentStrategy`:

```ts
interface PaymentStrategy {
  // existing
  createOrder(...): Promise<OrderResult>;
  captureOrder(...): Promise<CaptureResult>;

  // new
  registerBillingPlan(input: BillingPlanInput): Promise<{ planId: string }>;
  createSubscription(input: CreateSubscriptionInput): Promise<{
    subscriptionId: string;
    status: string;
    approveUrl: string;
  }>;
  getSubscription(subscriptionId: string): Promise<SubscriptionDetails>;
  cancelSubscription(subscriptionId: string, reason?: string): Promise<void>;
  suspendSubscription(subscriptionId: string, reason?: string): Promise<void>;
  reactivateSubscription(subscriptionId: string, reason?: string): Promise<void>;
  verifyWebhookSignature(headers: Record<string, string>, body: string, webhookId: string): Promise<boolean>;
}
```

`PaypalStrategy` implements all of the above against `/v1/billing/*`. The existing `createOrder/captureOrder` stays for one-off purchases (none in this app yet, but the abstraction shouldn't lose generality).

Webhook signature verification uses PayPal's [`/v1/notifications/verify-webhook-signature` endpoint](https://developer.paypal.com/docs/api/webhooks/v1/#verify-webhook-signature). The pkg exposes a stateless verifier so the API doesn't need a PayPal client of its own.

#### `apps/api`

- **`PaymentService`** gains `createPayPalSubscription`, `cancelPayPalSubscription`, etc. — thin pass-through to the pkg.
- **`SubscriptionsService.createPaidOrder()`** is renamed to `createPaidSubscription()`. It returns `{ subscriptionId, approveUrl }` (not `orderId`).
- **`SubscriptionsService.capture()`** is removed. Capture happens via webhook, not redirect. The `/subscriptions/success` page becomes a passive "we're activating your plan" screen that polls `useSubscriptionQuery` until `status === 'active'`.
- **New `WebhooksController`** at `/api/webhooks/paypal`. Public endpoint (no JWT), signature-verified before any side effects. Dispatches by event type to handlers in a new `PaypalWebhooksService`.
- **`SubscriptionsRenewalService`** is deleted. The cron disappears.
- **iSub → PayPal plan mapping** lives in a new `PayPalPlanRegistry` service: on startup or on first subscribe to a plan, it ensures a PayPal billing plan exists (via `registerBillingPlan`) and caches `iSubPlanId → paypalPlanId` in a new `paypal_plan_mappings` table.

#### Schema changes

```sql
-- Map iSub plan IDs to PayPal billing plan IDs.
create table paypal_plan_mappings (
  isub_plan_id text primary key,
  paypal_plan_id text not null unique,
  effective_price numeric not null,
  effective_currency text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Record PayPal webhook deliveries for idempotency + audit.
create table paypal_webhook_events (
  id text primary key,                -- PayPal event id
  event_type text not null,
  resource_id text,                   -- subscription id, sale id, etc.
  payload jsonb not null,
  processed_at timestamptz,
  error text,
  received_at timestamptz not null default now()
);
create index paypal_webhook_events_unprocessed_idx
  on paypal_webhook_events (received_at)
  where processed_at is null;
```

No changes needed to `user_subscriptions` — `provider_subscription_id` is already there from the V3 migration (per AGENTS.md). `status` enum already supports `past_due`, `expired`, `canceled`, `incomplete`. `'suspended'` is new — needs adding.

#### Webhook handler — event dispatch

| PayPal Event                              | Handler action                                                                            |
| ----------------------------------------- | ----------------------------------------------------------------------------------------- |
| `BILLING.SUBSCRIPTION.ACTIVATED`          | status='active', start_date=now, period dates from PayPal                                 |
| `PAYMENT.SALE.COMPLETED`                  | extend period_end; optional renewal notification                                          |
| `PAYMENT.SALE.DENIED`                     | log; PayPal will retry; emit notification "payment failed, will retry"                    |
| `BILLING.SUBSCRIPTION.PAYMENT.FAILED`     | final retry exhaustion warning; status stays active until SUSPENDED                       |
| `BILLING.SUBSCRIPTION.SUSPENDED`          | status='past_due'; notification "Your subscription is paused — update payment method"     |
| `BILLING.SUBSCRIPTION.CANCELLED`          | status='canceled', cancel_at_period_end=true                                              |
| `BILLING.SUBSCRIPTION.EXPIRED`            | status='expired'; fall back to Starter via entitlements                                   |
| `BILLING.SUBSCRIPTION.RE-ACTIVATED`       | status='active'                                                                           |
| `BILLING.SUBSCRIPTION.UPDATED`            | sync price/period from PayPal (covers admin edits)                                        |

Idempotency: every handler first inserts the event into `paypal_webhook_events`. If `id` already exists with non-null `processed_at`, the handler returns 200 immediately. This protects against PayPal's at-least-once delivery.

#### Client changes

- `subscriptions.success.tsx` becomes a passive activation screen — polls `useSubscriptionQuery` every 2 s for up to 30 s. Shows "all set" once `status === 'active'`, else "still processing".
- The `useSubscribeHandler` flow no longer stashes `pendingPlanId` in localStorage (no capture POST needed).
- Cancel flow continues to call `/api/subscriptions/cancel`; the action server-side now talks to PayPal first, then updates the DB.

### Webhook security

1. Each webhook ID is registered in the PayPal Developer Dashboard once per environment (sandbox / live). The webhook ID is stored as `PAYPAL_WEBHOOK_ID` env var.
2. Every incoming request goes through `verifyWebhookSignature(headers, rawBody, PAYPAL_WEBHOOK_ID)`. Failures return 401 without touching state.
3. The endpoint reads the **raw body** before any JSON parsing — the signature is over the raw bytes, not the parsed object. This requires a NestJS raw-body middleware on the route.
4. Rate-limited via `@nestjs/throttler` (already in deps).

### iSub → PayPal plan registration

PayPal billing plans are immutable in their core pricing once activated. To keep iSubscription as the source of truth without re-registering on every price change:

1. On API startup, fetch all iSub plans, and for each paid plan, look up the mapping in `paypal_plan_mappings`.
2. If missing OR effective_price/currency differs from the mapping → register a new PayPal billing plan, deactivate the old one (if any), update the mapping.
3. Existing subscriptions on the old plan continue billing at the old price (PayPal pins them); only **new** subscriptions get the new plan ID.
4. To roll out a price change to existing users, we'd need to call PayPal's `/revise` endpoint per active subscription — explicit migration step, not implicit.

This means **price changes in iSub are not instant** for existing paid users. Acceptable trade-off (industry standard), but documented in operator runbook.

## Cutover plan (for existing paid subscribers)

Two paths considered:

### Option A: Hard cutover

On migration day:
1. Stop the existing renewal cron (deploy with `SubscriptionsRenewalService` removed).
2. For each `user_subscriptions` row with `provider='paypal'`, status='active': mark `migrating_to_subs_api=true`, send notification "Your subscription will renew via PayPal automatically from now on — no action needed if you re-authorize on next renewal."
3. On next manual renewal (T-1 nudge from the still-running fallback OR user-initiated re-subscribe), they go through the new Subscriptions flow.
4. After all `active` rows have a `provider_subscription_id` (or `current_period_end` has passed), retire the old `last_order_id` columns.

### Option B: Soft cutover (recommended)

1. Ship the Subscriptions API code path **behind a feature flag** (`FEATURE_PAYPAL_SUBSCRIPTIONS_API=true`).
2. New subscribers go through the new flow.
3. Existing Orders-based subscriptions continue under the old cron until their `current_period_end`. On natural expiry, the user re-subscribes via the new flow.
4. After ~60 days (longest billing cycle), retire the old cron + Orders code.

Recommendation: B. Avoids batch migration risk and gives a graceful 60-day deprecation window.

## Webhook tunneling for development

PayPal sandbox webhooks need a public URL. Two options:

- **cloudflared tunnel** (`cloudflared tunnel --url http://localhost:3000`) — preferred for local dev.
- **ngrok** — same idea, requires an account.

Register the tunnel URL as a sandbox webhook in PayPal Developer Dashboard. Document this in `docs/runbooks/paypal-webhook-dev-tunnel.md` (to be created during implementation).

## Rollback

Behind feature flag (Option B), rollback is a config flip — `FEATURE_PAYPAL_SUBSCRIPTIONS_API=false` reverts new subscribers to the Orders flow. The webhook handler can stay deployed (no-op without traffic).

For the schema, the two new tables and the `'suspended'` enum value are additive; rollback requires no DB changes.

The risk window is "users who already subscribed via the new flow." Their PayPal subscriptions continue billing whether or not the feature flag is on. The webhook handler must therefore continue processing events even when the flag is off — flag gates the **creation** flow, not the **event-consumption** flow.

## Open questions

1. **Trial periods.** Subscriptions API supports billing-plan-level trials cleanly (Orders v2 didn't). Worth introducing? Out of V1, but easy add-on later.
2. **Mid-cycle upgrade/downgrade.** Subscriptions API has `/revise`. UX for proration / immediate switch is a separate design.
3. **Multi-currency.** Each PayPal billing plan is single-currency. If iSub serves the same plan in multiple currencies, we register N billing plans. Today only USD — non-issue.
4. **Refunds.** PayPal Subscriptions emit `PAYMENT.SALE.REFUNDED`. We need to define product policy: refund → cancel? Refund → keep access? Out of V1.

## Estimated scope

Rough breakdown (engineering days, ±50 %):

| Slice                                                          | Days |
| -------------------------------------------------------------- | ---- |
| `@idevconn/payment` pkg: new methods, types, tests             | 4    |
| API: webhook handler + signature verify + raw-body middleware  | 3    |
| API: `SubscriptionsService` refactor, capture removal          | 2    |
| `paypal_plan_mappings` registry + cold-start sync              | 2    |
| Schema migrations + enum addition                              | 0.5  |
| Client: success page polling, cancel flow re-wire              | 1.5  |
| i18n strings, runbook, observability (logging, advisors)       | 1.5  |
| Sandbox testing with tunnel + manual scenarios                 | 2    |
| Cutover script + ops doc                                       | 1    |
| Buffer                                                         | 2.5  |
| **Total**                                                      | **~20 days** |

## Next steps

This spec is for review only. No implementation work begins until:

1. Reminder Cadence design (`2026-05-20-renewal-cadence-design.md`) ships first.
2. Product confirms the strategic priority (auto-debit churn-reduction vs. other roadmap items).
3. PayPal Subscriptions API live access reviewed (some merchants need additional underwriting for recurring billing — verify in PayPal portal before committing).
