# Environment Variable Contract

All subscription-related env vars. Add these to `.env.example`, `.env.docker.example`,
`docker-compose.yml` (under the `api` service), and CI secrets.

---

## API (`apps/api`)

| Variable | Example | Source | Purpose |
|---|---|---|---|
| `ISUBSCRIBE_API_URL` | `https://isubscribe.me/api/v1/public/subscriptions/data` | iSubscribe dashboard → API docs | Server-side endpoint for fetching the plan catalog |
| `ISUBSCRIBE_API_KEY` | `sk_live_abc123...` | iSubscribe dashboard → Tenant → API Key | Auth header (`x-api-key`) for the catalog request |
| `ISUBSCRIBE_ORIGIN` | `https://your-app.com` | Must match an allowed origin in iSubscribe settings | `Origin` header sent with catalog requests |
| `FREE_SUBSCRIPTION_PLAN_ID` | `dm0pgfjDgI70fgSrWe0h` | iSubscribe dashboard → Plans → Starter plan ID | Plan auto-assigned to new users on registration |
| `PAYPAL_CLIENT_ID` | `AXv2...` | PayPal Developer → My Apps → App credentials | PayPal OAuth client ID |
| `PAYPAL_SECRET` | `EAb3...` | PayPal Developer → My Apps → App credentials | PayPal OAuth secret |
| `PAYPAL_ENV` | `sandbox` or `live` | Deployment decision | Controls which PayPal endpoint is used |
| `APP_BASE_URL` | `https://your-app.com` | Deployment config | Base URL for PayPal `return_url` and `cancel_url` |

### Used by `ISubscribeService`

`ISUBSCRIBE_API_KEY` and `ISUBSCRIBE_API_URL` are fetched via `ConfigService.get()` — no throw if missing;
a warning is logged and upstream status is marked degraded. `ISUBSCRIBE_ORIGIN` defaults to `http://localhost:5173`.

### Used by `PaymentService`

`PAYPAL_CLIENT_ID` and `PAYPAL_SECRET` are fetched via `ConfigService.getOrThrow()` — API boot fails if either is missing.
`PAYPAL_ENV` defaults to `sandbox`.

### Used by `SubscriptionsService`

`FREE_SUBSCRIPTION_PLAN_ID` → `getOrThrow()` in `assignFreePlan()` — throws if missing.
`APP_BASE_URL` → `getOrThrow()` in `createPaidOrder()` — throws if missing.

---

## Client (`apps/client`)

| Variable | Example | Source | Purpose |
|---|---|---|---|
| `VITE_SUBSCRIBE_BASE_URL` | `https://isubscribe.me/api/v1` | iSubscribe API docs | Base URL for the `SubscriptionWidget` component |
| `VITE_TENANT_KEY` | `pk_live_abc123...` | iSubscribe dashboard → Tenant → Public Key | Client-safe key for the widget's plan fetch |

> `VITE_TENANT_KEY` is the **public** key (safe to expose in the browser bundle).
> `ISUBSCRIBE_API_KEY` may be the same value or a server-only key — check the iSubscribe dashboard.

### Widget usage

```tsx
const apiKey = import.meta.env.VITE_TENANT_KEY;
const apiBaseUrl = import.meta.env.VITE_SUBSCRIBE_BASE_URL
  ? `${import.meta.env.VITE_SUBSCRIBE_BASE_URL}/public/subscriptions`
  : undefined;

<SubscriptionWidget apiKey={apiKey} apiBaseUrl={apiBaseUrl} ... />
```

---

## docker-compose.yml snippet (api service)

```yaml
api:
  environment:
    ISUBSCRIBE_API_URL: ${ISUBSCRIBE_API_URL}
    ISUBSCRIBE_API_KEY: ${ISUBSCRIBE_API_KEY}
    ISUBSCRIBE_ORIGIN: ${ISUBSCRIBE_ORIGIN}
    FREE_SUBSCRIPTION_PLAN_ID: ${FREE_SUBSCRIPTION_PLAN_ID}
    PAYPAL_CLIENT_ID: ${PAYPAL_CLIENT_ID}
    PAYPAL_SECRET: ${PAYPAL_SECRET}
    PAYPAL_ENV: ${PAYPAL_ENV:-sandbox}
    APP_BASE_URL: ${APP_BASE_URL}
```

## CI / CD

In GitHub Actions (or similar), add all 8 vars as repository secrets and inject them
into the deployment `.env` file before starting the container. The client build only needs
`VITE_SUBSCRIBE_BASE_URL` and `VITE_TENANT_KEY` baked in at build time.
