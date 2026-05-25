# Validation — Preflight Checks in the Target Project

Run these checks **before writing any files**. Use Read, Glob, and Grep to verify. Stop and report
if any blocker is found.

---

## Blockers (must be true before proceeding)

| Check | Command / file to inspect | Fix if missing |
|---|---|---|
| Nx workspace root | `nx.json` exists at workspace root | Not an Nx project — cannot proceed |
| NestJS 11 API app | `apps/<api>/src/app.module.ts` exists, `@nestjs/core` ≥ 11 in deps | Ensure NestJS 11 is installed |
| React 19 client app | `apps/<client>/src/main.tsx` exists | Ensure React 19 is configured |
| TanStack Router | `@tanstack/react-router` in deps | Skill assumes TanStack Router; adapting to React Router requires route changes |
| Supabase | `supabase/migrations/` dir exists | Initialize Supabase CLI first |
| `auth.users` enabled | Supabase config has `[auth] enabled = true` | Enable auth in `supabase/config.toml` |
| `update_updated_at()` function | Grep for `update_updated_at` in existing migrations | Migration 001 adds a trigger that calls this function — ensure it exists or add it |

---

## Warnings (proceed with caution)

| Check | Impact |
|---|---|
| `@nestjs/schedule` missing from `apps/api` | The renewal cron won't compile — install it |
| `@nestjs/axios` missing from `apps/api` | `ISubscribeService` uses `HttpService` — install it |
| `@nestjs/cache-manager` missing from `apps/api` | Plan caching won't work — install it |
| `class-validator` / `class-transformer` missing | DTOs will fail — install them |
| `notification_type` enum missing from DB | Migration 004 adds values to it — check existing migrations for `create type notification_type` |
| Existing `apps/api/src/subscriptions/` | Prompt user before overwriting |
| Existing `user_subscriptions` table | Skip migration 001; apply only the gap migrations |
| `sonner` not installed in client | UI components use `toast` from `sonner` — install it |
| `lucide-react` not installed in client | Icons used in profile/subscription components |
| No `formatAmount` util in client | `orders-card.tsx` uses `@/lib/format-amount` — create it or adapt the template |
| No CASL `useAbility` hook in client | `entitlements-provider.tsx` uses `useAbility` for admin override — adapt or stub it |

---

## Migration 004 special handling

Migration 004 (`004_add_subscription_notification_types.sql`) extends an existing `notification_type` enum:

```sql
alter type notification_type add value if not exists 'subscription_renewal';
alter type notification_type add value if not exists 'subscription_cancelled';
alter type notification_type add value if not exists 'subscription_reactivated';
```

**If the target project has no `notification_type` enum and no `notifications` table:**
- Replace migration 004 with a fresh creation:

```sql
create type notification_type as enum (
  'subscription_renewal',
  'subscription_cancelled',
  'subscription_reactivated'
);
-- create a minimal notifications table if needed by SubscriptionsService
create table notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  type notification_type not null,
  message text not null,
  channel text not null default 'web',
  read_at timestamptz,
  created_at timestamptz not null default now()
);
alter table notifications enable row level security;
create policy "users_read_own_notifications" on notifications
  for select using (auth.uid() = user_id);
```

- Also provide a matching `NotificationsModule` / `NotificationsService` in the API, or stub it out
  from `SubscriptionsService` if the project doesn't need in-app notifications yet.

---

## `update_updated_at()` function

Migration 001 registers a trigger on `user_subscriptions` that calls `update_updated_at()`.
This function must exist before migration 001 runs. Check:

```bash
grep -r "update_updated_at" supabase/migrations/
```

If not found, prepend this to migration 001 (or add as a separate migration before it):

```sql
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;
```

---

## Supabase migration numbering

The 7 migrations in `templates/migrations/` are numbered `001_` through `007_`.
Copy them into `supabase/migrations/` with **ISO-8601 timestamps** that sort after your last existing migration.

Example: if your last migration is `20260531000000_something.sql`, number the new ones starting at `20260601000001_create_subscriptions.sql`.

Run `supabase db reset` or `supabase migration up` locally to verify they apply cleanly.
