# Lemon Squeezy Subscription API -- Detailed Reference

## All Subscription-Related Functions

### Checkouts

| Function | Signature | Description |
|---|---|---|
| `createCheckout` | `(storeId, variantId, options?) => Promise<FetchResponse<Checkout>>` | Creates a checkout session with a URL |
| `getCheckout` | `(checkoutId, params?) => Promise<FetchResponse<Checkout>>` | Retrieves a checkout by ID |
| `listCheckouts` | `(params?) => Promise<FetchResponse<ListCheckouts>>` | Lists all checkouts |

**Checkout options (`NewCheckout`):**

```typescript
{
  customPrice?: number;            // custom price in cents
  productOptions?: {
    name?: string;                 // override product name
    description?: string;          // override product description
    media?: string[];              // override product images
    redirectUrl?: string;          // redirect after purchase
    receiptButtonText?: string;
    receiptLinkUrl?: string;
    receiptThankYouNote?: string;
    enabledVariants?: number[];    // limit visible variants
    confirmationTitle?: string;
    confirmationMessage?: string;
    confirmationButtonText?: string;
  };
  checkoutOptions?: {
    embed?: boolean;               // overlay checkout
    media?: boolean;               // show product media
    logo?: boolean;                // show store logo
    desc?: boolean;                // show product description
    discount?: boolean;            // show discount code field
    skipTrial?: boolean;           // remove free trial
    subscriptionPreview?: boolean; // show renewal preview text
    backgroundColor?: string;      // hex color customizations...
    buttonColor?: string;
    // ...and more color options
  };
  checkoutData?: {
    email?: string;                // prefill email
    name?: string;                 // prefill name
    billingAddress?: { country?: string; zip?: string; };
    taxNumber?: string;
    discountCode?: string;
    custom?: Record<string, unknown>;  // your custom data (e.g. user_id)
    variantQuantities?: { variantId: number; quantity: number; }[];
  };
  preview?: boolean;               // include pricing preview
  testMode?: boolean;              // create in test mode
  expiresAt?: string | null;       // ISO 8601 expiry
}
```

### Subscriptions

| Function | Signature | Description |
|---|---|---|
| `getSubscription` | `(subscriptionId, params?) => Promise<FetchResponse<Subscription>>` | Get a single subscription |
| `listSubscriptions` | `(params?) => Promise<FetchResponse<ListSubscriptions>>` | List/filter subscriptions |
| `updateSubscription` | `(subscriptionId, updates) => Promise<FetchResponse<Subscription>>` | Update subscription |
| `cancelSubscription` | `(subscriptionId) => Promise<FetchResponse<Subscription>>` | Cancel subscription |

**Filter params for `listSubscriptions`:**

```typescript
{
  filter: {
    storeId?: string | number;
    orderId?: string | number;
    orderItemId?: string | number;
    productId?: string | number;
    variantId?: string | number;
    userEmail?: string;
    status?: "on_trial" | "active" | "paused" | "past_due" | "unpaid" | "cancelled" | "expired";
  },
  page: { number?: number; size?: number; },
  include: ["store", "customer", "order", "order-item", "product", "variant", "subscription-items", "subscription-invoices"],
}
```

**Update options (`UpdateSubscription`):**

```typescript
{
  variantId?: number;              // switch plan
  cancelled?: boolean;             // true = cancel, false = resume
  pause?: { mode: "void" | "free"; resumesAt?: string | null; } | null;  // null = unpause
  billingAnchor?: number | null;   // day of month (1-31), null/0 = reset
  invoiceImmediately?: boolean;    // charge prorated amount now
  disableProrations?: boolean;     // skip proration, charge at next renewal
  trialEndsAt?: string | null;     // extend/shorten trial
}
```

### Subscription Invoices

| Function | Signature | Description |
|---|---|---|
| `getSubscriptionInvoice` | `(invoiceId, params?) => Promise` | Get a single invoice |
| `listSubscriptionInvoices` | `(params?) => Promise` | List/filter invoices |
| `generateSubscriptionInvoice` | `(invoiceId, params) => Promise` | Generate a PDF invoice |
| `issueSubscriptionInvoiceRefund` | `(invoiceId, amount) => Promise` | Refund an invoice |

**Invoice filter params:** `storeId`, `status` (`pending`/`paid`/`void`/`refunded`), `refunded` (boolean), `subscriptionId`

**Generate invoice params:** `name`, `address`, `city`, `state?`, `zipCode`, `country`, `notes?`, `locale?`

### Subscription Items

| Function | Signature | Description |
|---|---|---|
| `getSubscriptionItem` | `(itemId, params?) => Promise` | Get a subscription item |
| `listSubscriptionItems` | `(params?) => Promise` | List subscription items |
| `getSubscriptionItemCurrentUsage` | `(itemId) => Promise` | Get current usage (usage-based billing) |
| `updateSubscriptionItem` | `(itemId, updates) => Promise` | Update quantity |

**Update options:** `{ quantity: number; invoiceImmediately?: boolean; disableProrations?: boolean; }`

### Usage Records

| Function | Signature | Description |
|---|---|---|
| `createUsageRecord` | `(subscriptionItemId, record) => Promise` | Report usage |
| `getUsageRecord` | `(usageRecordId, params?) => Promise` | Get a usage record |
| `listUsageRecords` | `(params?) => Promise` | List usage records |

**New usage record:** `{ quantity: number; action?: "increment" | "set"; }`

### Supporting Functions

| Function | Module | Purpose |
|---|---|---|
| `listProducts` / `getProduct` | Products | List subscription products |
| `listVariants` / `getVariant` | Variants | List subscription tiers/plans |
| `listPrices` / `getPrice` | Prices | Get pricing (intervals, tiers, trials) |
| `listCustomers` / `getCustomer` / `createCustomer` / `updateCustomer` / `archiveCustomer` | Customers | Manage customers |
| `createWebhook` / `getWebhook` / `updateWebhook` / `deleteWebhook` / `listWebhooks` | Webhooks | Manage webhooks |
| `getAuthenticatedUser` | Users | Verify API key |

---

## Subscription Data Fields

Every subscription object (`data.data.attributes`) contains:

| Field | Type | Description |
|---|---|---|
| `store_id` | number | Store this subscription belongs to |
| `customer_id` | number | Customer this subscription belongs to |
| `order_id` | number | Associated order |
| `order_item_id` | number | Associated order item |
| `product_id` | number | Current product |
| `variant_id` | number | Current variant (plan tier) |
| `product_name` | string | Human-readable product name |
| `variant_name` | string | Human-readable variant name |
| `user_name` | string | Customer full name |
| `user_email` | string | Customer email |
| `status` | string | `on_trial`, `active`, `paused`, `past_due`, `unpaid`, `cancelled`, `expired` |
| `status_formatted` | string | Title-case status (e.g. "Past due") |
| `card_brand` | string or null | `visa`, `mastercard`, `amex`, `discover`, `jcb`, `diners`, `unionpay` |
| `card_last_four` | string or null | Last 4 digits of card |
| `pause` | object or null | `{ mode: "void" \| "free", resumes_at?: string }` |
| `cancelled` | boolean | Whether subscription is cancelled |
| `trial_ends_at` | string or null | ISO 8601 trial end date |
| `billing_anchor` | number | Day of month for billing (1-31) |
| `first_subscription_item` | object or null | `{ id, subscription_id, price_id, quantity, is_usage_based, created_at, updated_at }` |
| `urls` | object | `{ update_payment_method, customer_portal, customer_portal_update_subscription }` (valid 24h) |
| `renews_at` | string | ISO 8601 next billing date |
| `ends_at` | string or null | ISO 8601 expiry (if cancelled/expired) |
| `created_at` | string | ISO 8601 creation date |
| `updated_at` | string | ISO 8601 last update date |
| `test_mode` | boolean | Whether created in test mode |

---

## Webhook Events

| Event | When it fires |
|---|---|
| `subscription_created` | Customer completes checkout for a subscription product |
| `subscription_updated` | Subscription is modified (plan change, billing anchor, etc.) |
| `subscription_cancelled` | Subscription is cancelled (enters grace period) |
| `subscription_resumed` | Previously cancelled subscription is resumed |
| `subscription_expired` | Grace period over, or unpaid sub expired via dunning |
| `subscription_paused` | Payment collection is paused |
| `subscription_unpaused` | Subscription is unpaused |
| `subscription_payment_success` | Renewal payment succeeds |
| `subscription_payment_failed` | Renewal payment fails |
| `subscription_payment_recovered` | Previously failed payment is recovered |
| `subscription_payment_refunded` | Subscription payment is refunded |
| `order_created` | Any order is created (including initial subscription order) |
| `order_refunded` | Order is refunded |
| `license_key_created` | License key is created |
| `license_key_updated` | License key is updated |

**Webhook payload structure:**

```typescript
{
  meta: {
    event_name: string;            // e.g. "subscription_created"
    custom_data: Record<string, unknown>;  // your checkoutData.custom
  },
  data: {
    type: "subscriptions";
    id: string;
    attributes: { /* subscription fields above */ };
    relationships: { store, customer, order, product, variant, ... };
  },
}
```

---

## Recommended Database Schema

**subscriptions table:**

| Column | Type | Description |
|---|---|---|
| `id` | primary key | Your internal ID |
| `user_id` | foreign key | Link to your users table |
| `lemon_subscription_id` | integer | Lemon Squeezy subscription ID |
| `lemon_customer_id` | integer | Lemon Squeezy customer ID |
| `product_id` | integer | Current product |
| `variant_id` | integer | Current variant/plan |
| `status` | string | Subscription status |
| `current_period_end` | timestamp | From `renews_at` |
| `ends_at` | timestamp nullable | Grace period end (if cancelled) |
| `trial_ends_at` | timestamp nullable | Trial end date |
| `pause_mode` | string nullable | "void" or "free" if paused |
| `pause_resumes_at` | timestamp nullable | When pause ends |
| `card_brand` | string nullable | Payment card brand |
| `card_last_four` | string nullable | Last 4 digits |
| `created_at` | timestamp | Record creation |
| `updated_at` | timestamp | Last update |

---

## Subscription Invoice Fields

| Field | Type | Description |
|---|---|---|
| `store_id` | number | Store the invoice belongs to |
| `subscription_id` | number | Associated subscription |
| `customer_id` | number | Customer the invoice belongs to |
| `billing_reason` | string | `initial` or `renewal` |
| `status` | string | `pending`, `paid`, `void`, `refunded` |
| `currency` | string | ISO 4217 code (e.g. `USD`) |
| `subtotal` | number | Subtotal in cents (store currency) |
| `discount_total` | number | Discount in cents |
| `tax` | number | Tax in cents |
| `total` | number | Total in cents |
| `refunded` | boolean | Whether refunded |
| `refunded_amount` | number | Refunded amount in cents |
| `subtotal_formatted` | string | e.g. "$9.99" |
| `total_formatted` | string | e.g. "$9.99" |
| `urls.invoice_url` | string or null | PDF download URL (null if pending) |

---

## Price Model Fields (for subscription variants)

| Field | Type | Description |
|---|---|---|
| `category` | string | `one_time`, `subscription`, `lead_magnet`, `pwyw` |
| `scheme` | string | `standard`, `package`, `graduated`, `volume` |
| `usage_aggregation` | string or null | `sum`, `last_during_period`, `last_ever`, `max` |
| `unit_price` | number | Price in cents |
| `renewal_interval_unit` | string or null | `day`, `week`, `month`, `year` |
| `renewal_interval_quantity` | number or null | e.g. 3 = every 3 units |
| `trial_interval_unit` | string or null | Trial period unit |
| `trial_interval_quantity` | number or null | Trial period count |
| `setup_fee_enabled` | boolean or null | Has setup fee |
| `setup_fee` | number or null | Setup fee in cents |
| `tiers` | array or null | For graduated/volume: `{ last_unit, unit_price, fixed_fee }[]` |
