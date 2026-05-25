# Prerequisites — Questions to Ask the User

Ask ALL of these before writing any files. Use the AskQuestion tool when available.

---

## 1. Target workspace

- **Absolute path** to the Nx workspace root?
- **API app name** inside `apps/` (default: `api`)?
- **Client app name** inside `apps/` (default: `client`)?
- **Shared lib name** (default: `libs/shared`, package alias e.g. `@myapp/shared`)?

---

## 2. iSubscribe credentials

Obtain from the [iSubscribe dashboard](https://isubscribe.me):

| Value | Where |
|---|---|
| `ISUBSCRIBE_API_KEY` (= `VITE_TENANT_KEY`) | Dashboard → Tenant → API Key |
| `ISUBSCRIBE_API_URL` | Default: `https://isubscribe.me/api/v1/public/subscriptions/data` |
| `ISUBSCRIBE_ORIGIN` | Must match an allowed origin in iSubscribe dashboard settings |
| **Free plan ID** (`FREE_SUBSCRIPTION_PLAN_ID`) | Dashboard → Plans → Starter plan ID |
| **Paid plan IDs** (for widget overrides) | Dashboard → Plans → each paid plan ID |

---

## 3. PayPal credentials

Obtain from [PayPal Developer](https://developer.paypal.com):

| Value | Note |
|---|---|
| `PAYPAL_CLIENT_ID` | App credentials |
| `PAYPAL_SECRET` | App credentials |
| `PAYPAL_ENV` | `sandbox` (dev) or `live` (prod) |

---

## 4. App base URL

`APP_BASE_URL` — the public URL of the client app (e.g. `http://localhost:4200` for dev, `https://your-app.com` for prod). Used as the base for PayPal `return_url` and `cancel_url`.

---

## 5. Feature slugs

List of feature slugs for this product — must match slugs configured in the iSubscribe dashboard **exactly** (character-for-character). These replace warranty's `FEATURE_SLUGS` in `libs/shared/src/features.ts`.

For each feature, also specify its **semantic value**: `true` (boolean gate), a number (numeric cap), or `null` (unlimited).

Example:
```
MAX_ITEMS: "up_to_10_items" → value: 10
PREMIUM_EXPORT: "premium_export" → value: true
STORAGE_MB: "storage_50_mb" → value: 50
```

---

## 6. Free plan fallback slugs

Which feature slugs belong to the free Starter tier? These populate `fallback-plan.ts` (used when iSubscribe is unreachable at API boot). Typically a subset of the full slug list.

---

## 7. i18n locales

Which locales does the target project use? (en, ru, he, others?) — determines which `templates/i18n/*.subscription.json` files to copy and translate.

---

## 8. Existing code conflicts

- Does `apps/api/src/subscriptions/` already exist? (prompt before overwriting)
- Does `apps/client/src/subscriptions/` already exist? (prompt before overwriting)
- Does the Supabase `user_subscriptions` table already exist?
- Does the project have a `notification_type` Postgres enum? (migration 004 requires it)
- Does the project use CASL for authorization? (affects `entitlements-or-admin.guard.ts`)

---

## 9. Auth / profile service paths

- Where is `AuthService.register()` defined? (to add `assignFreePlan` hook)
- Where is `AuthService.getMe()` defined? (to add lazy-assign hook for OAuth users)
- Where is the account-delete flow? (to add `hasActivePaidSubscription` guard)
- How does the project check if a user is an admin? (to adapt `EntitlementsOrAdminGuard`)
