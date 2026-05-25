# Architecture Reference

Concise guide to the subscription stack. For the full master spec with all mermaid diagrams,
see [docs/architecture.md](docs/architecture.md).

---

## Stack at a glance

| Layer | Technology |
|---|---|
| Plan catalog | [iSubscribe SaaS](https://isubscribe.me) — external, no local `plans` table |
| Widget | `@teamco/isubscribe-widget-react` — fetches plans, calls `onSubscribe` |
| Payment | `@idevconn/payment` with `PaypalStrategy` — PayPal Orders v2 |
| Entitlements | `@idevconn/isubscribe-entitlements` — NestJS + React adapters |
| Persistence | Supabase: `user_subscriptions`, `entitlements_usage`, `payment_history` |
| Cron | `SubscriptionsRenewalService` — daily dunning (03:00 UTC) |

---

## End-to-end checkout flow

```
User clicks Subscribe (widget)
  → widget fetches plans from iSubscribe (VITE_TENANT_KEY)
  → onSubscribe(planDto) → use-subscribe-handler.ts
  → POST /api/subscriptions { planId }
  → SubscriptionsService.createPaidOrder()
      1. Re-fetch plan from iSubscribe (trusted price — not dto.effectivePrice)
      2. Reject if effectivePrice ≤ 0 (free plans assigned automatically)
      3. ensureSubscriptionRow() — idempotent Starter row creation
      4. PaymentService.createPayPalOrder(amount, currency, referenceId, returnUrl, cancelUrl)
      5. UPDATE user_subscriptions SET last_order_id, last_order_approve_url
  → { orderId, approveUrl } → client redirects to approveUrl
  → User approves on PayPal
  → PayPal returns to /subscriptions/success?token=<orderId>
  → POST /api/subscriptions/capture { orderId, planId }
  → SubscriptionsService.captureOrder()
      1. Verify dto.orderId === user_subscriptions.last_order_id
      2. PaymentService.capturePayPalOrder(orderId, idempotencyKey)
      3. Re-fetch plan from iSubscribe (never trust caller entitlements)
      4. entitlements.saveSubscription(sub)
      5. INSERT payment_history row (idempotent on dedup index)
      6. CLEAR last_order_id, reset renewal_attempts
  → Subscription active; React Query invalidated
```

---

## Feature gating (backend)

```
@UseGuards(EntitlementsOrAdminGuard)
@RequireSubscription({ feature: 'your_feature_slug' })
@Post('some-endpoint')
async create(...) { ... }
```

The guard chain:
1. `AuthGuard` (your existing guard) sets `req.user.id` from JWT.
2. `EntitlementsOrAdminGuard` checks if user is admin (short-circuit `true`) else delegates to pkg `EntitlementsGuard`.
3. `EntitlementsGuard` calls `SecureUserContextResolver.resolve()` → reads `req.user.id` (JWT only).
4. Pkg fetches `user_subscriptions` from Supabase (`cacheTtlMs: 0`).
5. Returns 402/403 if entitlement missing; proceeds if granted.

---

## Feature gating (frontend)

```tsx
import { Feature, LockedFeature, useFeature, useLimit } from '@/subscriptions';

// Renders children only when feature is granted:
<Feature name="your_feature_slug">
  <PremiumComponent />
</Feature>

// Renders fallback when feature is locked:
<LockedFeature name="your_feature_slug" fallback={<UpgradePrompt />}>
  <PremiumComponent />
</LockedFeature>

// Programmatic check in a component:
const { granted, limit } = useFeature('your_feature_slug');
```

`EntitlementsProvider` (mounted in `main.tsx`) hydrates the snapshot from `GET /api/subscriptions/me`
via React Query. Admins get a proxy that returns `null` (unlimited) for every feature.

---

## Supabase schema overview

### `user_subscriptions`

| Column | Type | Notes |
|---|---|---|
| `user_id` | uuid FK → `auth.users` | ON DELETE CASCADE |
| `plan_id` | text | iSubscribe plan ID |
| `status` | `subscription_status` | `active`, `canceled`, `past_due`, `expired`, `incomplete` |
| `provider` | text | `'none'` (free) or `'paypal'` |
| `entitlements` | jsonb | snapshot from `buildEntitlementsFromPlan()` |
| `current_period_start/end` | timestamptz | billing period |
| `cancel_at_period_end` | boolean | cancel flag |
| `last_order_id` | text | pending PayPal order — verified at capture |
| `renewal_attempts` | int | dunning stage counter (0–4) |
| `tenant_id` | text | NULL for single-tenant |

**Unique index**: `(user_id, tenant_id) NULLS NOT DISTINCT` — one row per user.
**RLS**: `SELECT` for `auth.uid() = user_id`; writes go through service-role client only.

### `entitlements_usage`

Pre-staged for metered features. No callers yet. Unique on `(user_id, tenant_id, metric, period_start)`.

### `payment_history`

Append-only ledger. Dedup unique on `(provider, provider_order_id)` — capture retries are safe.
Written by `SubscriptionsService.captureOrder()`; read by `GET /api/subscriptions/orders`.

---

## Security invariants

These must **never** be removed:

| # | Invariant | Where |
|---|---|---|
| 1 | Server-side plan price re-fetch | `subscriptions.service.ts → createPaidOrder` |
| 2 | `orderId === last_order_id` check | `subscriptions.service.ts → captureOrder` |
| 3 | `defaultPolicy: 'deny'` | `subscriptions.module.ts → EntitlementsModule.forRootAsync` |
| 4 | `global: false` on EntitlementsModule | `subscriptions.module.ts` — prevents auto `APP_GUARD` |
| 5 | `SecureUserContextResolver` reads `req.user.id` only | `secure-user-context.resolver.ts` |
| 6 | `EntitlementsExceptionFilter` strips PII in production | `subscriptions.module.ts → APP_FILTER` |

---

## Renewal / dunning cron

`SubscriptionsRenewalService` runs daily at 03:00 UTC via `@Cron(CronExpression.EVERY_DAY_AT_3AM)`.

**Dunning stages** (see `renewal-schedule.ts`):

| Stage | Days from period end | Action |
|---|---|---|
| 1 | T-1 to T+0 | Pre-expiry warning; create PayPal order; notify |
| 2 | T+1 to T+2 | First overdue nudge |
| 3 | T+3 to T+6 | Mid-grace reminder |
| 4 | T+7 to T+13 | Final notice |
| Expired | T+14+ | Transition to Starter; notify `subscription_expired` |

Free plans (`provider='none'`) are renewed in-place (no PayPal order needed).
Subscriptions with `cancel_at_period_end=true` are skipped by the cron filter.

18h throttle prevents double-sends when the cron runs accidentally twice.
