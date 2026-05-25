---
name: idevconn-subscriptions
description: Adds the full iSubscribe + PayPal + @idevconn/isubscribe-entitlements + Supabase subscription stack to a Nx + NestJS + React + Supabase project. Use when the user wants to add subscriptions, billing, paywall, pricing page, feature gating, entitlements, PayPal checkout, plan management, or cancel/reactivate flows; or mentions iSubscribe, isubscribe.me, @teamco/isubscribe-widget-react, @idevconn/isubscribe-entitlements, or @idevconn/payment.
disable-model-invocation: true
---

# iSubscribe + PayPal + Entitlements Subscription Stack

Ports the proven subscription pattern from the iDEVconn Warranty project into any new Nx repo.
All source templates live in `templates/` alongside this file. Deep reference in `docs/`.

## Before you start — read these first

- Prerequisites to gather from user: [reference-prerequisites.md](reference-prerequisites.md)
- Preflight validation in target project: [reference-validation.md](reference-validation.md)

## Workflow checklist

```
- [ ] Phase 1 — Gather prerequisites (see reference-prerequisites.md)
- [ ] Phase 2 — Validate target project (see reference-validation.md)
- [ ] Phase 3 — Install npm dependencies
- [ ] Phase 4 — Apply Supabase migrations
- [ ] Phase 5 — Copy shared lib templates + customize FEATURE_SLUGS
- [ ] Phase 6 — Copy backend (NestJS) templates
- [ ] Phase 7 — Wire AuthService + AppModule
- [ ] Phase 8 — Copy frontend (React) templates
- [ ] Phase 9 — Mount EntitlementsProvider + register routes
- [ ] Phase 10 — Add env vars
- [ ] Phase 11 — Add i18n keys
- [ ] Phase 12 — Smoke test
```

## Phase 3 — npm dependencies

```bash
# workspace root
npm install @teamco/isubscribe-widget-react @idevconn/isubscribe-entitlements

# apps/api
npm install --prefix apps/api @idevconn/payment @idevconn/isubscribe-entitlements
# ensure these are present in apps/api: @nestjs/schedule @nestjs/axios @nestjs/cache-manager class-validator class-transformer

# apps/client
npm install --prefix apps/client @idevconn/isubscribe-entitlements @teamco/isubscribe-widget-react
```

## Phase 4 — Supabase migrations

Copy `templates/migrations/001_*.sql` through `007_*.sql` into `supabase/migrations/`.
**Rename timestamps** to follow your project's sequence (e.g. `20260601000001_create_subscriptions.sql`).

> Migration 004 adds values to a `notification_type` enum. If your project does not have one,
> create it first or adjust the migration to create it fresh. See [reference-validation.md](reference-validation.md).

## Phase 5 — Shared lib templates

Copy `templates/shared/` files into your shared lib (e.g. `libs/shared/src/`):

| Template | Target | Customize? |
|---|---|---|
| `features.ts.template` | `libs/shared/src/features.ts` | **YES — replace all FEATURE_SLUGS/VALUES** |
| `isubscribe-error-reason.ts.template` | `libs/shared/src/isubscribe-error-reason.ts` | No |
| `types.ts.template` | `libs/shared/src/types.ts` | Merge with your existing types |
| `index.ts.template` | `libs/shared/src/index.ts` | Merge re-exports |

See [reference-customization.md](reference-customization.md) for the full placeholder swap table.

## Phase 6 — Backend templates

Copy all files from `templates/api/` into `apps/api/src/` preserving the folder structure:

| Template dir | Target dir |
|---|---|
| `templates/api/subscriptions/` | `apps/api/src/subscriptions/` |
| `templates/api/payment/` | `apps/api/src/payment/` |

**Rename `.template` → remove suffix** when copying (e.g. `dto.ts.template` → `dto.ts`).

**Files with `PLACEHOLDER:` markers that require edits** — see [reference-customization.md](reference-customization.md):
- `subscriptions.service.ts` — return URLs (`/subscriptions/success`, `/subscriptions/cancel`)
- `subscriptions-renewal.service.ts` — dunning notification copy
- `fallback-plan.ts` — starter feature slugs list
- `entitlements-or-admin.guard.ts` — admin ability check (adapt to your CASL/auth setup)
- `feature-slug-validator.ts` — imports FEATURE_SLUGS from your shared lib path

Update **import paths**: replace `@warranty/shared` with your shared lib alias (e.g. `@myapp/shared`).

## Phase 7 — Wire AuthService + AppModule

**In `apps/api/src/auth/auth.service.ts`:**

```typescript
// After successful user creation in register():
await this.subscriptionsService.assignFreePlan(userId);
// Rollback auth user if assignFreePlan throws

// In getMe() (lazy assign for OAuth users):
await this.subscriptionsService.assignFreePlan(userId).catch(() => null);
```

**In `apps/api/src/profile/profile.service.ts` (deleteAccount):**

```typescript
const hasPaid = await this.subscriptionsService.hasActivePaidSubscription(userId);
if (hasPaid) throw new BadRequestException("Cancel your paid subscription before deleting your account");
```

**In `apps/api/src/app.module.ts`:**

```typescript
import { ScheduleModule } from '@nestjs/schedule';
import { SubscriptionsModule } from './subscriptions/subscriptions.module';
import { PaymentModule } from './payment/payment.module';

@Module({
  imports: [
    ScheduleModule.forRoot(),
    SubscriptionsModule,
    PaymentModule,
    // ... your other modules
  ],
})
```

## Phase 8 — Frontend templates

Copy all files from `templates/client/` into `apps/client/src/` preserving structure.
**Rename `.template` → remove suffix** when copying.

| Template dir | Target dir |
|---|---|
| `templates/client/subscriptions/` | `apps/client/src/subscriptions/` |
| `templates/client/components/landing/` | `apps/client/src/components/landing/` |
| `templates/client/components/subscriptions/` | `apps/client/src/components/subscriptions/` |
| `templates/client/components/profile/` | `apps/client/src/components/profile/` |
| `templates/client/queries/` | `apps/client/src/queries/` |
| `templates/client/routes/_dashboard/` | `apps/client/src/routes/_dashboard/` |

**Files with `PLACEHOLDER:` markers** (see [reference-customization.md](reference-customization.md)):
- `landing-pricing.tsx` — replace hardcoded plan IDs in `subscriptionOverrides`
- `queries/subscription.ts` — update `@warranty/shared` import to your shared lib alias

## Phase 9 — Mount EntitlementsProvider + register routes

**In `apps/client/src/main.tsx`** (wrap the app):

```tsx
import { EntitlementsProvider } from '@/subscriptions';

root.render(
  <QueryClientProvider client={queryClient}>
    <EntitlementsProvider>
      <App />
    </EntitlementsProvider>
  </QueryClientProvider>
);
```

**Register TanStack Router routes** for:
- `_dashboard/subscriptions/success`
- `_dashboard/subscriptions/cancel`
- `_dashboard/subscriptions/manage`

## Phase 10 — Env vars

Add to `apps/api/.env.example` (copy `templates/env/api.env.example.template`):

```
ISUBSCRIBE_API_URL=https://isubscribe.me/api/v1/public/subscriptions/data
ISUBSCRIBE_API_KEY=<from iSubscribe dashboard>
ISUBSCRIBE_ORIGIN=https://your-app.com
FREE_SUBSCRIPTION_PLAN_ID=<starter plan ID from iSubscribe dashboard>
PAYPAL_CLIENT_ID=<from PayPal developer portal>
PAYPAL_SECRET=<from PayPal developer portal>
PAYPAL_ENV=sandbox
APP_BASE_URL=http://localhost:4200
```

Add to `apps/client/.env.example` (copy `templates/env/client.env.example.template`):

```
VITE_SUBSCRIBE_BASE_URL=https://isubscribe.me/api/v1
VITE_TENANT_KEY=<from iSubscribe dashboard — same as ISUBSCRIBE_API_KEY>
```

## Phase 11 — i18n keys

Merge `templates/i18n/en.subscription.json` into your app's `en.json` locale.
Do the same for `ru.subscription.json` and `he.subscription.json` if those locales are used.
Keys live under `subscriptions`, `profile.subscription`, `profile.orders`, `landing.pricing`.

## Phase 12 — Smoke test

1. Register a new user → confirm `user_subscriptions` row with `provider='none'` + Starter entitlements.
2. Visit the pricing page → plans load from iSubscribe widget.
3. Click Subscribe on a paid plan → redirected to PayPal sandbox.
4. Approve → redirected to `/subscriptions/success` → capture succeeds → entitlements updated.
5. Visit `/profile` → plan badge shows upgraded plan; Cancel works; Reactivate works.
6. Add `@RequireSubscription({ feature: 'YOUR_FEATURE_SLUG' })` to one endpoint and verify gates fire.

## Security invariants — NEVER remove

See [reference-architecture.md](reference-architecture.md) for full rationale.

1. **Server-side price re-fetch**: `createPaidOrder` ignores widget `effectivePrice` — re-fetches from iSubscribe.
2. **Order ID verification**: `captureOrder` verifies `orderId === last_order_id` stored at order-creation time.
3. **`defaultPolicy: 'deny'`**: `EntitlementsModule` blocks by default; guards are applied per controller, never as `APP_GUARD`.
4. **`SecureUserContextResolver`**: reads only `req.user.id` (set by JWT `AuthGuard`); never falls back to headers.
5. **`global: false`** on `EntitlementsModule.forRootAsync`: prevents auto `APP_GUARD` registration that would run before `AuthGuard`.

## Additional resources

- Architecture & flows: [reference-architecture.md](reference-architecture.md)
- Prerequisites: [reference-prerequisites.md](reference-prerequisites.md)
- Validation: [reference-validation.md](reference-validation.md)
- Env contract: [reference-env-contract.md](reference-env-contract.md)
- Customization placeholders: [reference-customization.md](reference-customization.md)
- Known gaps & hardening: [reference-known-gaps.md](reference-known-gaps.md)
- Master architecture spec: [docs/architecture.md](docs/architecture.md)
- Future PayPal Subscriptions API migration: [docs/future-paypal-subscriptions-api.md](docs/future-paypal-subscriptions-api.md)
