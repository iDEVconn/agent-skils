---
name: lemonsqueezy-subscriptions
description: >-
  Integrate Lemon Squeezy subscription billing into a project using the
  @lemonsqueezy/lemonsqueezy.js SDK. Use when the user mentions Lemon Squeezy,
  LemonSqueezy, subscription payments, checkout integration, subscription
  webhooks, or wants to add SaaS billing with Lemon Squeezy.
---

# Lemon Squeezy Subscription Integration

## SDK Overview

**Package:** `@lemonsqueezy/lemonsqueezy.js` (v4+)
**Runtime:** Node.js >= 20, server-side only (exposes API key -- never use in browser)
**Formats:** ESM and CJS, zero runtime dependencies
**API:** Thin typed wrapper around https://api.lemonsqueezy.com/v1

## Installation

```bash
npm install @lemonsqueezy/lemonsqueezy.js
```

## Setup (call once at app startup)

```typescript
import { lemonSqueezySetup } from "@lemonsqueezy/lemonsqueezy.js";

lemonSqueezySetup({
  apiKey: process.env.LEMON_SQUEEZY_API_KEY,
  onError: (error) => console.error("LemonSqueezy:", error),
});
```

Required env vars:
- `LEMON_SQUEEZY_API_KEY` -- from https://app.lemonsqueezy.com/settings/api
- `LEMON_SQUEEZY_STORE_ID` -- your store ID
- `LEMON_SQUEEZY_WEBHOOK_SECRET` -- for verifying webhook signatures

## Subscription Lifecycle

1. **Create checkout** -> user pays on hosted page -> `subscription_created` webhook fires
2. **Active subscription** -> query/update via API, state changes arrive via webhooks
3. **Cancel** -> grace period until `ends_at` -> `subscription_expired` webhook fires

## Core Integration Pattern

```typescript
import {
  lemonSqueezySetup,
  createCheckout,
  getSubscription,
  updateSubscription,
  cancelSubscription,
} from "@lemonsqueezy/lemonsqueezy.js";

// Create checkout (start a subscription)
const { data, error } = await createCheckout(STORE_ID, VARIANT_ID, {
  checkoutData: {
    email: "user@example.com",
    custom: { user_id: "your-db-user-id" },
  },
  productOptions: {
    redirectUrl: "https://yourapp.com/success",
  },
});
// Redirect user to: data.data.attributes.url

// Get subscription
const sub = await getSubscription(subscriptionId, {
  include: ["product", "variant"],
});

// Change plan (upgrade/downgrade)
await updateSubscription(subscriptionId, {
  variantId: NEW_VARIANT_ID,
  invoiceImmediately: true,
});

// Pause
await updateSubscription(subscriptionId, {
  pause: { mode: "void" },  // or "free"
});

// Unpause
await updateSubscription(subscriptionId, { pause: null });

// Cancel
await cancelSubscription(subscriptionId);

// Resume (before ends_at)
await updateSubscription(subscriptionId, { cancelled: false });
```

## Response Pattern

Every function returns `{ statusCode, data, error }`. Always check error first:

```typescript
const { data, error } = await getSubscription(id);
if (error) {
  // error.name === "Lemon Squeezy Error"
  // error.cause has JSON:API error details
  throw error;
}
// data is non-null here
```

## Webhook Handler (Critical)

Webhooks are the only reliable way to track subscription state changes. Always verify the `x-signature` header with HMAC SHA-256.

```typescript
import crypto from "crypto";

app.post("/api/webhooks/lemonsqueezy", async (req, res) => {
  const hmac = crypto.createHmac("sha256", process.env.LEMON_SQUEEZY_WEBHOOK_SECRET);
  const digest = hmac.update(JSON.stringify(req.body)).digest("hex");
  if (req.headers["x-signature"] !== digest) return res.status(401).end();

  const event = req.body.meta.event_name;
  const attrs = req.body.data.attributes;
  const customData = req.body.meta.custom_data; // your checkout custom data

  switch (event) {
    case "subscription_created":    /* store in DB, link via customData.user_id */ break;
    case "subscription_updated":    /* update record */ break;
    case "subscription_cancelled":  /* mark cancelled, note ends_at */ break;
    case "subscription_expired":    /* revoke access */ break;
    case "subscription_resumed":    /* restore access */ break;
    case "subscription_paused":     /* update pause state */ break;
    case "subscription_unpaused":   /* update pause state */ break;
    case "subscription_payment_success": /* log payment */ break;
    case "subscription_payment_failed":  /* alert user */ break;
    case "subscription_payment_recovered": /* mark recovered */ break;
  }
  return res.status(200).json({ received: true });
});
```

## Create Webhook Programmatically

```typescript
import { createWebhook } from "@lemonsqueezy/lemonsqueezy.js";

await createWebhook(STORE_ID, {
  url: "https://yourapp.com/api/webhooks/lemonsqueezy",
  events: [
    "subscription_created", "subscription_updated", "subscription_cancelled",
    "subscription_resumed", "subscription_expired", "subscription_paused",
    "subscription_unpaused", "subscription_payment_success",
    "subscription_payment_failed", "subscription_payment_recovered",
  ],
  secret: "your-webhook-signing-secret",
});
```

## Customer Portal URLs

Each subscription has pre-signed self-service URLs (valid 24h):

```typescript
const sub = await getSubscription(subscriptionId);
const paymentUrl = sub.data.data.attributes.urls.update_payment_method;
const portalUrl = sub.data.data.attributes.urls.customer_portal;
```

## Key Considerations

- **Server-side only** -- never expose API key in client code
- **Webhook idempotency** -- events may be delivered more than once; deduplicate by subscription ID
- **Custom data** -- pass your user ID via `checkoutData.custom` at checkout; it returns in `meta.custom_data` on webhooks
- **Grace periods** -- `cancelled` status still has access until `ends_at`
- **Dunning** -- failed payments retry 4 times over 2 weeks before becoming `unpaid`
- **Test mode** -- set `testMode: true` on checkouts/webhooks; test objects have `test_mode: true`
- **Rate limits** -- cache subscription data in your DB, update via webhooks instead of polling

## Detailed Reference

For complete API function signatures, subscription data fields, invoice/usage-record APIs, and database schema recommendations, see [reference.md](reference.md).
