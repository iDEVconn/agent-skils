# Customization — Placeholder Swap Table

Every place where warranty-specific values must be replaced with target product values.
All `// PLACEHOLDER:` comments in template files point back to this table.

---

## 1. Shared lib — `libs/shared/src/features.ts`

**Most important file to customize.** Replace slug VALUES (strings) freely.

⚠️ **Coupling note.** The following key NAMES are referenced by
`subscriptions.service.ts` → `buildEntitlementsFromPlan` and
`fallback-plan.ts` → `STARTER_FEATURE_SLUGS`:

- `MAX_ITEMS`
- `UNLIMITED_ITEMS`
- `STORAGE_MB`
- `STORAGE_GB`

If you rename any of these keys, you MUST update those two files in lock-step
or the API will not compile. Slug VALUES (the right-hand-side strings) can
change freely without touching service code.

### Template structure

```typescript
export const FEATURE_SLUGS = {
  // PLACEHOLDER: Replace VALUES with slugs from your iSubscribe dashboard.
  // KEY NAMES listed in the coupling note above must remain unchanged.

  // Free tier features
  MAX_ITEMS: "up_to_10_items",           // numeric cap — used by service (DO NOT RENAME KEY)
  BASIC_FEATURE: "basic_feature",        // free-form boolean key — rename freely
  STORAGE_MB: "storage_100_mb",          // numeric storage — used by service (DO NOT RENAME KEY)

  // Paid tier features
  UNLIMITED_ITEMS: "unlimited_items",    // used by service (DO NOT RENAME KEY)
  STORAGE_GB: "storage_5_gb",            // used by service (DO NOT RENAME KEY)
  PREMIUM_FEATURE: "premium_feature",    // free-form boolean key — rename freely
} as const;

export const FEATURE_VALUES: Record<FeatureSlug, FeatureValue> = {
  // PLACEHOLDER: For each slug above, define its semantic value:
  //   true     = boolean gate (user either has it or doesn't)
  //   number   = numeric cap (e.g. 10 for up to 10 items)
  //   null     = unlimited (use with UNLIMITED_* slugs)
  [FEATURE_SLUGS.MAX_ITEMS]: 10,
  [FEATURE_SLUGS.BASIC_FEATURE]: true,
  [FEATURE_SLUGS.STORAGE_MB]: 100,
  [FEATURE_SLUGS.UNLIMITED_ITEMS]: true,  // normalized to null in buildEntitlementsFromPlan
  [FEATURE_SLUGS.STORAGE_GB]: 5120,       // 5 GB expressed in MB
  [FEATURE_SLUGS.PREMIUM_FEATURE]: true,
};
```

---

## 2. `fallback-plan.ts` — Starter fallback feature list

```typescript
// PLACEHOLDER: List only the slugs that belong to the FREE Starter tier.
// These are used when iSubscribe is unreachable at API boot (graceful degradation).
// Use the FEATURE_SLUGS constant keys, NOT the raw string values.
const STARTER_FEATURE_SLUGS = [
  FEATURE_SLUGS.MAX_ITEMS,
  FEATURE_SLUGS.BASIC_FEATURE,
  // ... add all your Starter-tier feature keys here
] as const;
```

---

## 3. `subscriptions.service.ts` — PayPal return / cancel URLs

```typescript
// PLACEHOLDER: These are the routes the client registers for PayPal redirect.
// Update if your client uses different path segments.
returnUrl: `${appBaseUrl}/subscriptions/success`,  // ← update path if different
cancelUrl: `${appBaseUrl}/subscriptions/cancel`,   // ← update path if different
```

---

## 4. `subscriptions-renewal.service.ts` — Dunning copy

```typescript
// PLACEHOLDER: Replace dunning notification messages with copy appropriate for your product.
// The strings include the plan title and a PayPal approveUrl.
private renewalCopy(stage: 1 | 2 | 3 | 4, planTitle: string, approveUrl: string): string {
  switch (stage) {
    case 1: return `Your ${planTitle} subscription renews tomorrow. Approve: ${approveUrl}`;
    case 2: return `Your ${planTitle} subscription is overdue. Renew: ${approveUrl}`;
    case 3: return `Last few days of grace on ${planTitle}. Renew: ${approveUrl}`;
    case 4: return `Final notice — ${planTitle} subscription ends in 7 days. ${approveUrl}`;
  }
}
```

---

## 5. `entitlements-or-admin.guard.ts` — Admin check

```typescript
// PLACEHOLDER: Adapt the admin check to your project's auth service.
// The warranty version calls this.authService.isAdmin(userId).
// Replace with however your app determines admin status:
//   - CASL ability: ability.can('manage', 'all')
//   - DB lookup: check user_roles table
//   - JWT claim: req.user.role === 'admin'
if (userId && (await this.authService.isAdmin(userId))) {
  return true;
}
```

---

## 6. `landing-pricing.tsx` — Hardcoded plan IDs in widget overrides

```typescript
// PLACEHOLDER: Replace these with your actual plan IDs from the iSubscribe dashboard.
// The key is the iSubscribe plan ID. The value is the override config.
subscriptionOverrides={{
  "YOUR_PRO_PLAN_ID": {           // REPLACE with actual Pro plan ID
    badge: t("landing.pricing.popular"),
    style: OVERRIDES_CSS,
    buttonText: t("landing.pricing.pro.cta", "Start Pro"),
  },
  "YOUR_STARTER_PLAN_ID": {       // REPLACE with actual Starter plan ID
    buttonText: t("landing.pricing.starter.cta", "Get started free"),
  },
}}
```

---

## 7. `subscriptions.module.ts` — Shared lib import alias

```typescript
// PLACEHOLDER: Replace '@warranty/shared' with your project's shared lib alias.
// This import appears in: subscriptions.service.ts, plan-resolver.ts,
// fallback-plan.ts, feature-slug-validator.ts, subscriptions-renewal.service.ts
import { FEATURE_SLUGS, FEATURE_VALUES } from '@warranty/shared'; // ← replace alias
// becomes e.g.:
import { FEATURE_SLUGS, FEATURE_VALUES } from '@myapp/shared';
```

---

## 8. `queries/subscription.ts` (client) — Shared lib import alias

```typescript
// PLACEHOLDER: Replace '@warranty/shared' with your project's shared lib alias.
import type { ISubscribeUpstreamStatus } from '@warranty/shared'; // ← replace
```

---

## 9. `entitlements-provider.tsx` — Auth store and ability hooks

The template imports:
```typescript
import { useAuthStore } from '@/stores/auth';   // PLACEHOLDER: your auth store hook
import { useAbility } from '@/abilities';        // PLACEHOLDER: your CASL ability hook
```

Replace with the equivalent hooks in your project. If you don't use CASL, remove the
`isAdmin` branch and simplify the provider (admins won't get the unlimited proxy).

---

## 10. Notification types in migration 004

```sql
-- PLACEHOLDER: Add any subscription lifecycle notification types your product needs.
-- Remove types that don't apply (e.g. skip subscription_reactivated if you don't support reactivation).
alter type notification_type add value if not exists 'subscription_renewal';
alter type notification_type add value if not exists 'subscription_cancelled';
alter type notification_type add value if not exists 'subscription_reactivated';
```
