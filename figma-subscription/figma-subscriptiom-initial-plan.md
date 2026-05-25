Act as a senior enterprise SaaS architect and platform engineer.

Design a production-ready architecture for a Subscription Infrastructure Platform with:
- Figma Plugin integration
- Drop-in subscription widgets
- Payment integrations
- Castle security integration
- Tenant-based configuration
- Public SDK
- AI/MCP-ready architecture

The system goal:
Allow any company or creator to create subscription products on a centralized platform and then integrate them into:
- websites
- React apps
- mobile apps
- Figma projects
- future MCP/AI workflows

==================================================
HIGH LEVEL BUSINESS CONCEPT
==================================================

The platform provides:
1. Subscription builder
2. Plan management
3. Sub-items/features management
4. Payment provider integration
5. Security layer integration
6. Public drop-in widgets
7. Figma plugin integration
8. SDK for frontend integration
9. Tenant-based architecture

The platform should work similarly to:
- Stripe Checkout
- Auth0 widgets
- Clerk
- Intercom
- RevenueCat
- Paddle
- Supabase embeddable architecture

==================================================
IMPORTANT PRODUCT DECISION
==================================================

NO LOGIN INSIDE FIGMA PLUGIN.

Instead:
- Use Public Tenant Keys
- Use Subscription IDs
- Plugin acts as lightweight configurator
- Platform handles all business logic

Architecture must support:
- public tenant access
- secure backend API
- embeddable widgets
- future AI automation
- MCP integrations

==================================================
TENANT MODEL
==================================================

Each organization has:
- tenant_id
- public_tenant_key
- secret_api_key
- subscriptions
- plans
- payment configs
- security configs
- themes
- localization settings

Example:

PUBLIC:
pk_tenant_xxx

SECRET:
sk_tenant_xxx

Public keys can:
- read public subscription configuration
- render widgets
- fetch themes
- fetch plans

Secret keys can:
- create checkout sessions
- manage customers
- configure providers
- access analytics
- manage webhooks

==================================================
MAIN PLATFORM MODULES
==================================================

Design the architecture for:

1. Auth Service
2. Tenant Service
3. Subscription Service
4. Plans Service
5. Features/Sub-items Service
6. Checkout Service
7. Payment Provider Abstraction
8. Castle Security Integration
9. Widget Rendering Engine
10. Theme Engine
11. Public API Gateway
12. Admin Dashboard
13. Figma Plugin API
14. MCP Integration Layer
15. AI Agent Integration Layer
16. Webhook Processing System
17. Event Bus
18. Analytics Service
19. Audit Logs
20. API Key Management

==================================================
SUBSCRIPTION MODEL
==================================================

Each subscription contains:
- subscription_id
- title
- description
- plans
- sub-items/features
- billing interval
- trial config
- localization
- payment configuration
- security policy
- UI theme
- checkout settings

Each plan contains:
- monthly/yearly price
- currency
- features
- limits
- metadata

==================================================
FIGMA PLUGIN ARCHITECTURE
==================================================

Design a Figma Plugin architecture.

The plugin must:
- accept Public Tenant Key
- fetch subscriptions
- allow selecting subscription
- allow selecting UI templates
- insert subscription blocks into Figma
- generate integration snippets
- generate SDK configuration
- generate React integration code

The plugin must support:
- pricing tables
- checkout blocks
- paywalls
- subscription cards
- account billing UI
- upgrade screens

The plugin must NOT:
- contain sensitive logic
- store secrets
- handle payment directly

==================================================
DROP-IN SDK
==================================================

Design a frontend SDK.

Examples:

<SubscriptionWidget />
<PricingTable />
<CheckoutButton />
<PaywallGate />
<AccountBilling />

SDK requirements:
- React-first
- embeddable
- SSR compatible
- Vite compatible
- Next.js compatible
- themeable
- i18n support
- lazy loaded
- secure
- analytics enabled

==================================================
CASTLE SECURITY INTEGRATION
==================================================

Design Castle integration.

Security layer should:
- risk-score sessions
- detect abuse
- validate checkout attempts
- protect APIs
- provide tenant-level policies

Architecture should include:
- middleware
- policy engine
- event tracking
- risk adapters

==================================================
PAYMENT ARCHITECTURE
==================================================

Design provider abstraction for:
- Stripe
- PayPal
- Paddle
- future providers

Must support:
- subscriptions
- one-time payments
- trials
- invoices
- coupons
- taxes
- webhooks

==================================================
PUBLIC API
==================================================

Design REST API.

Examples:

GET /public/subscriptions
GET /public/subscriptions/:id/config
POST /checkout/session
POST /checkout/confirm
POST /security/risk-check

==================================================
TECH STACK
==================================================

Use:
- Nx monorepo
- NestJS backend
- React frontend
- TypeScript everywhere
- PostgreSQL or Supabase
- Redis
- BullMQ
- Event-driven architecture
- Vite
- Zustand or Redux Toolkit
- React Query
- Webhooks
- Docker
- Traefik
- Kubernetes-ready design

==================================================
MCP + AI ARCHITECTURE
==================================================

Design future MCP integration.

Goals:
- AI agents can inspect Figma subscription blocks
- AI agents can generate integration code
- AI agents can configure subscriptions
- Cursor/Claude/Codex compatible workflows
- Figma MCP compatible architecture

Example flow:

Figma
↓
MCP Server
↓
AI Agent
↓
Reads subscription config
↓
Generates React/NestJS integration
↓
Creates SDK configuration automatically

==================================================
DATABASE DESIGN
==================================================

Provide:
- complete entity model
- relationships
- multi-tenant strategy
- RBAC strategy
- API key strategy
- audit logs
- webhook tables
- payment tables
- checkout session tables
- analytics tables

==================================================
OUTPUT REQUIREMENTS
==================================================

Provide:
1. High-level architecture
2. Production-ready system design
3. Backend architecture
4. Frontend architecture
5. Figma plugin architecture
6. SDK architecture
7. Security architecture
8. Payment abstraction architecture
9. MCP/AI architecture
10. Database schema recommendations
11. API design
12. Event-driven architecture
13. Scaling strategy
14. Deployment strategy
15. DevOps recommendations
16. Monorepo structure
17. Nx module structure
18. Suggested package naming
19. Enterprise best practices
20. MVP roadmap
21. Future scaling roadmap
22. Recommended implementation phases

The result must be:
- enterprise-grade
- production-oriented
- modular
- scalable
- AI-ready
- developer-friendly
- SaaS-ready
- multi-tenant-ready
- security-first