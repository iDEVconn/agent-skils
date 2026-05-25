# Subscription & Entitlements Integration Architecture

This document serves as the high-level **System Architecture Specification** for the Subscription Integration within the **iDEVconn Warranty** platform. It covers the end-to-end design, data models, class contracts, execution flows, and key architectural patterns governing subscriptions, payments, and feature-gating.

---

## 1. Executive Summary & Core Philosophy

The iDEVconn Warranty subscription system is designed around a three-tier decoupling strategy:

1. **Self-Contained Frontend Components**: The checkout interface is driven by a drop-in, style-tokenized React widget (`@teamco/isubscribe-widget-react`) that fetches plans dynamically from an external SaaS catalog via client-safe Tenant Keys.
2. **Framework-Agnostic Core Packages**: Payment gateways and rule engines are encapsulated in dedicated packages (`@idevconn/payment` and `@idevconn/isubscribe-entitlements`) which are decoupled from specific server frameworks (such as NestJS) or specific ORMs/databases (such as Supabase, Prisma, or TypeORM).
3. **Secure Intermediary API**: The local NestJS backend (`apps/api`) acts as the single source of truth and secure orchestrator. It manages session security, maps SaaS plans to database rules, coordinates payment capture, and prevents client-side price or role spoofing.

> [!IMPORTANT]
> **Security Boundary**: The frontend client never communicates directly with payment gateways (PayPal) or the database (Supabase). Every financial contract and feature resolution is authorized, verified, and recorded by the NestJS API.

---

## 2. Big Picture Architecture

The subsystem consists of four core building blocks communicating over secure channels:

```mermaid
flowchart TB
    subgraph Client["Frontend App (Vite + React)"]
        Landing["landing-pricing.tsx"]
        Widget["@teamco/isubscribe-widget-react"]
        AuthStore["Zustand Auth Store"]
    end

    subgraph API["NestJS Middleware & Controllers (apps/api)"]
        SubController["SubscriptionsController"]
        SubService["SubscriptionsService"]
        PaymentService["PaymentService"]
        SupabaseService["SupabaseService"]
        PlanResolver["PlanResolverFactory"]
    end

    subgraph Packages["Framework-Agnostic Libraries"]
        EntitlementsPkg["@idevconn/isubscribe-entitlements"]
        PaymentPkg["@idevconn/payment"]
    end

    subgraph External["External Services & DB"]
        iSubSaaS["iSubscription SaaS (SaaS Catalog)"]
        PayPalAPI["PayPal REST API"]
        SupabaseDB[("Supabase DB (user_subscriptions)")]
    end

    %% Client Interactions
    Landing -->|uses| Widget
    Widget -->|1. fetch plans| iSubSaaS
    Widget -->|2. onSubscribe()| Landing
    Landing -->|3. POST /api/subscriptions| SubController

    %% API Orchestration
    SubController --> SubService
    SubService -->|4. fetch raw plan| iSubSaaS
    SubService -->|5. createPayPalOrder| PaymentService
    PaymentService -->|uses| PaymentPkg
    PaymentPkg -->|6. OAuth token & Order| PayPalAPI
    SubService -->|7. stash orderId| SupabaseService
    SubService -->|8. saveSubscription| EntitlementsPkg
    
    %% Storage & Rules
    EntitlementsPkg -->|9. save/read| SupabaseDB
    PlanResolver -->|maps iSub plans to app features| SubService
```

---

## 3. Deep-Dive Module Breakdowns

### 3.1 Frontend React UI Widget (`@teamco/isubscribe-widget-react`)
This is a self-contained, drop-in React component (`SubscriptionWidget`) designed for maximum embeddability and visual performance.

*   **Responsibility**:
    *   Initiates dynamic network fetches (utilizing `AbortController` for clean react lifecycle unmounts) to retrieve the subscription plans from iSubscription.
    *   Renders responsive subscription cards with flex-column pricing structures, sale badges, feature lists, and custom call-to-actions.
    *   Exposes custom visual hooks (`--isw-*` CSS custom variables) that allow the parent website's styling (e.g. glassmorphism or golden gradients) to flow seamlessly into the widget.
*   **Key Design Patterns**:
    *   **Stable Callback Refs**: Stabilization of event handlers (`onSubscribe`, `onError`, `onLoaded`) using React `useRef` to prevent infinite rendering cycles when inline arrow functions are passed as props.
    *   **CSS Custom Property Tokens**: Fully avoids heavy JS theming bundles, resolving custom branding styles in real-time in the browser with zero runtime overhead.
    *   **Intl.NumberFormat**: Handles multi-currency format localization gracefully with browser-native APIs.

### 3.2 Payment Wrapper (`@idevconn/payment`)
A framework-agnostic payment abstraction library modeled directly around standard strategy boundaries.

*   **Responsibility**:
    *   Provides interchangeable payment strategies (e.g. `PaypalStrategy`) behind a unified `PaymentStrategy` contract.
    *   Handles wire-level REST integrations, security handshakes, and token retrievals.
*   **Key Design Patterns**:
    *   **Strategy Pattern**: Swapping Stripe, PayPal, or any local POS gateway is a zero-change refactor at the router/controller level; it requires only passing a different implementation to the registry.
    *   **OAuth Token Cache & Single-Flight Refresh**:
        *   Caches tokens locally until a short safety threshold (e.g. 9 hours) to avoid expensive handshakes on every request.
        *   Implements **Promise Sharing** (Single-Flight) to combine concurrent auth calls during a token refresh into a single Promise, eliminating "thundering herd" bottlenecks.
    *   **Request Idempotency**: Auto-injects standard unique request identifiers (`PayPal-Request-Id`) across retries to prevent double-captures under heavy network latency.

### 3.3 Authorization & Gating Engine (`@idevconn/isubscribe-entitlements`)
An enterprise-grade rule compilation and caching service designed to gate features based on active subscription contracts.

*   **Responsibility**:
    *   Resolves, manages, and stores user subscriptions and usage data.
    *   Exposes clean hooks (`useFeature`, `useLimit`, `useUsage`) and NestJS decorators (`@RequireSubscription`) to enforce limits globally.
*   **Key Design Patterns**:
    *   **Adapter Pattern**: Decoupled from physical database models. Exposes a generic `SubscriptionPersistenceAdapter` contract with concrete implementations for Memory (testing), Prisma, TypeORM, and Supabase.
    *   **CASL Decoupling**: Encapsulates all rule logic within `CaslAuthorizationEngine`. Swapping this to an external policy engine (like OPA or Cerbos) does not affect any application code.
    *   **SSR Snapshot Rehydration**: React `EntitlementsProvider` accepts an `initialSnapshot` computed on the server, avoiding flashing, double-rendering, or client-only loading screens on initial load.

---

## 4. End-to-End Execution Flows

### 4.1 Order Creation & Checkout Flow
This flow ensures that payment orders cannot be manipulated or spoofed by modifying pricing data on the client side.

```mermaid
sequenceDiagram
    autonumber
    actor User as Client Browser
    participant Widget as React Widget
    participant API as NestJS API
    participant iSub as iSubscription SaaS
    participant PayPal as PayPal REST API
    database DB as Supabase DB

    User->>Widget: Clicks "Subscribe"
    Widget->>API: POST /api/subscriptions (payload: { planId })
    Note over API: Security: Re-fetch plan from SaaS<br/>to get trusted price, not the client payload!
    API->>iSub: GET /plans/{planId}
    iSub-->>API: Plan details (effectivePrice = $19.99)
    API->>API: Preflight: ensureStarterRow()
    API->>DB: Upsert starter subscription if absent
    API->>PayPal: createOrder({ amount: 19.99, referenceId: ... })
    PayPal-->>API: { orderId, approveUrl }
    API->>DB: Update user_subscriptions SET last_order_id = orderId
    API-->>Widget: { orderId, approveUrl }
    Widget->>User: Redirect to PayPal Approval Page
```

### 4.2 Order Capture & Upgrade Flow
When a user completes their payment on PayPal, the capture endpoint verifies the order against the stored backend state.

```mermaid
sequenceDiagram
    autonumber
    actor User as Client Browser
    participant API as NestJS API
    participant PayPal as PayPal REST API
    participant iSub as iSubscription SaaS
    database DB as Supabase DB

    User->>API: POST /api/subscriptions/capture (payload: { orderId, planId })
    API->>DB: SELECT last_order_id FROM user_subscriptions
    DB-->>API: Row data (last_order_id = "PAYPAL-123")
    
    alt orderId matches last_order_id
        API->>PayPal: captureOrder("PAYPAL-123")
        PayPal-->>API: { status: "COMPLETED", payer: ... }
        API->>iSub: GET /plans/{planId} (Trusted Catalog Source)
        iSub-->>API: Plan features & parameters
        API->>API: Compile Entitlements snapshot map
        API->>DB: saveSubscription(Upgraded plan & snapshot)
        API->>DB: Clear last_order_id & last_order_approve_url
        API-->>User: Upgraded Subscription Record
    else orderId drift / forgery
        API-->>User: 400 BadRequestException ("Order mismatch")
    end
```

### 4.3 Feature Gating & Capacity Resolution
When an endpoint is decorated with `@RequireSubscription`, the NestJS API intercepts the request to verify active entitlements.

```mermaid
sequenceDiagram
    autonumber
    actor Client as Request Client
    participant Guard as EntitlementsGuard
    participant Service as CoreEntitlementsService
    database DB as Supabase DB

    Client->>Guard: Request with @RequireSubscription({ feature: 'max_products' })
    Guard->>Guard: contextResolver (Extract req.user.id)
    Guard->>Service: check('max_products')
    Note over Service: cacheTtlMs = 0 (Real-time DB query)
    Service->>DB: getActiveSubscription(userId)
    DB-->>Service: ActiveSubscription (Starter plan)
    Service->>Service: CaslEngine compiles rules
    
    alt Has Entitlement
        Service-->>Guard: true
        Guard-->>Client: Allow request to execute
    else Entitlement Missing
        Service-->>Guard: false
        Guard-->>Client: 402 Payment Required / 403 Forbidden
    end
```

---

## 5. Architectural Patterns Used

| Pattern | Code Implementation | Purpose |
| :--- | :--- | :--- |
| **Strategy Pattern** | `PaymentStrategy` interface & `PaypalStrategy` | Decouples order orchestration from the specific mechanics of upstream billing processors, ensuring seamless support for future providers (Stripe, Adyen, etc.). |
| **Adapter Pattern** | `SubscriptionPersistenceAdapter` (Supabase concrete class) | Allows the rule engine to remain entirely SQL-agnostic. The package knows how to request a subscription, while the adapter handles database-specific dialects (SQL, ORM calls, Prisma client). |
| **Gateway / Reverse Proxy** | NestJS `PaymentService` & `ISubscribeService` | Shields the client from external secrets and database tables, keeping all business credentials stored securely inside environment variables. |
| **Idempotency Locks** | `PayPal-Request-Id` headers & `last_order_id` validation | Guarantees that double-submitting a checkout form (or browser refreshing during a pending capture) does not result in double charging the user. |
| **Single-Flight Cache** | Promise chaining in `OauthTokenCache` | Prevents high-concurrency thundering herds from overloading authentication services, making the system resilient under traffic surges. |

---

## 6. Recommended System Improvements & Hardening

As a Solution Architect, I have analyzed the current repository and identified key areas to improve the reliability, security, and scalability of the subscription lifecycle.

### 💡 Recommendation 1: Webhook-Driven Payment Capture (Fail-Safe Resilience)
*   **The Problem**: Currently, the system relies on the React checkout callback to trigger the `POST /api/subscriptions/capture` call from the browser. If a user closes the browser tab, loses network connectivity, or experiences a client-side crash *after* approving the payment on PayPal but *before* redirecting to the app, the payment completes, but the user is never upgraded in the database.
*   **The Solution**: Transition to an asynchronous **Webhook Capture** system:
    1. Let PayPal send a server-to-server webhook `BILLING.SUBSCRIPTION.CREATED` / `CHECKOUT.ORDER.APPROVED` directly to a public endpoint on the NestJS API.
    2. The NestJS backend captures the order and updates the subscription table asynchronously.
    3. The client application polls `GET /api/subscriptions/me` or uses real-time Supabase listeners to detect the upgrade status and transition the UI.

### 💡 Recommendation 2: Activate the Dormant Capped Metric RPC
*   **The Problem**: The `entitlements_usage` table and `entitlements_increment_usage_capped` PostgreSQL RPC are currently dormant (pre-staged). If metered features (such as limits on AI tokens) are introduced in the future, standard database increments are prone to race conditions, letting high-frequency parallel requests bypass limits.
*   **The Solution**: Activate the capping mechanisms inside `apps/api`:
    *   Expose the capping RPC directly through the `SupabaseAdapter` interface.
    *   Wrap resource creation endpoints in transactional guards that leverage the capped RPC before executing expensive calls (like Google Gemini invoice parsing).

### 💡 Recommendation 3: Add Distributed Caching (Redis) for Scale
*   **The Problem**: Currently, to avoid multi-process inconsistency, `cacheTtlMs` is set to `0` in `entitlements.config.ts`, forcing the system to hit Supabase on every single request that executes a gated route (such as fetching or creating products). This will lead to high database load as traffic scales.
*   **The Solution**: Provide a pluggable **Redis Cache Adapter** in the `@idevconn/isubscribe-entitlements` package options:
    *   Enable a short TTL (e.g. 5 minutes) cached in a shared Redis cluster.
    *   Publish an invalidation message to Redis whenever `saveSubscription` is invoked (such as on webhooks or manual upgrades) to ensure instant, consistent rule updates across all running API nodes.

### 💡 Recommendation 4: Graceful Plan Downgrade & Data Archiving Strategy
*   **The Problem**: If a user downgrades their subscription from Pro (Unlimited Products) to Starter (Max 5 Products) while having 10 products registered in their database, what happens? Currently, the code allows them to view their products, but blocks creating new ones.
*   **The Solution**: Establish a formal plan-downgrade strategy:
    *   Implement **Read-Only Soft Limits**: Products above the capacity limit are marked as "locked" or "read-only" until the user upgrades again or archives/deletes surplus items.
    *   Add clean archiving flows so users can choose which 5 products they want to keep active on the Starter tier.
