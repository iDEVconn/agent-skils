# Login Implementation Guide

Full-stack auth pattern for projects using `@idevconn/supabase` + NestJS.

Covers: email/password login, Google OAuth, JWT guard chain, role-based access, token refresh.

---

## Architecture

```
Browser                  NestJS API              Supabase
  │                           │                       │
  │  POST /auth/login         │                       │
  │  { email, password }──── ▶│  signInWithPassword   │
  │                           │──────────────────────▶│
  │                           │◀──────────────────────│
  │◀── { access_token,        │  { session }          │
  │      refresh_token }      │                       │
  │                           │                       │
  │  GET /products            │                       │
  │  Authorization: Bearer ──▶│  verifyToken(token)   │
  │                           │──────────────────────▶│
  │                           │◀── { user }           │
  │◀── [ products ]           │                       │
```

**Key rule:** The frontend NEVER talks to Supabase directly for data. All DB operations go through NestJS. Supabase client on frontend is **auth-only** (Google OAuth + session management).

---

## Backend (NestJS)

### 1. SupabaseService

Two clients with different privileges:

```typescript
// src/supabase/supabase.service.ts
@Injectable()
export class SupabaseService {
  private adminClient: SupabaseClient;  // SERVICE_ROLE key — bypasses RLS
  private anonClient: SupabaseClient;   // ANON key — for user auth operations

  constructor(private config: ConfigService) {
    const url = this.config.getOrThrow("SUPABASE_URL");
    this.adminClient = createClient(url, this.config.getOrThrow("SUPABASE_SERVICE_ROLE_KEY"));
    this.anonClient = createClient(url, this.config.getOrThrow("SUPABASE_ANON_KEY"));
  }

  get admin(): SupabaseClient { return this.adminClient; }
  get auth(): SupabaseClient  { return this.anonClient;  }

  async verifyToken(token: string) {
    const { data, error } = await this.adminClient.auth.getUser(token);
    if (error || !data.user) throw new Error("Invalid token");
    return data.user;  // { id, email, ... }
  }
}

// src/supabase/supabase.module.ts
@Global()  // ← Global so every module gets it without importing
@Module({ providers: [SupabaseService], exports: [SupabaseService] })
export class SupabaseModule {}
```

**When to use which client:**
- `supabase.admin` — all DB queries (`from("products")`, `from("user_settings")`, etc.)
- `supabase.auth` — `signInWithPassword()`, `refreshSession()` only
- `supabase.admin.auth.admin` — admin-level auth ops: `createUser()`, `deleteUser()`, `getUserById()`, `signOut()`

---

### 2. AuthGuard — validates JWT on every request

```typescript
// src/auth/auth.guard.ts
@Injectable()
export class AuthGuard implements CanActivate {
  constructor(private supabase: SupabaseService, private reflector: Reflector) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    // Skip guard for routes decorated with @Public()
    const isPublic = this.reflector.getAllAndOverride<boolean>("isPublic", [
      context.getHandler(),
      context.getClass(),
    ]);
    if (isPublic) return true;

    const request = context.switchToHttp().getRequest();
    const token = this.extractToken(request);
    if (!token) throw new UnauthorizedException();

    try {
      const user = await this.supabase.verifyToken(token);
      request.user = user;  // { id, email, ... } — available as req.user in controllers
    } catch {
      throw new UnauthorizedException();
    }
    return true;
  }

  private extractToken(request: { headers: { authorization?: string } }): string | undefined {
    const [type, token] = request.headers.authorization?.split(" ") ?? [];
    return type === "Bearer" ? token : undefined;
  }
}
```

**Works for both email/password AND Google OAuth** — Supabase issues the same JWT format for both. No guard changes needed for OAuth.

---

### 3. RolesGuard — optional role check per endpoint

```typescript
// src/auth/roles.guard.ts
@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector, private authService: AuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const requiredRoles = this.reflector.getAllAndOverride<UserRole[]>("roles", [
      context.getHandler(),
      context.getClass(),
    ]);
    if (!requiredRoles) return true;  // no @Roles() decorator → pass

    const request = context.switchToHttp().getRequest();
    const role = await this.authService.getUserRole(request.user.id);
    request.user.role = role;
    if (!requiredRoles.includes(role)) throw new ForbiddenException();
    return true;
  }
}
```

---

### 4. Decorators

```typescript
// src/auth/roles.decorator.ts
export const Public = () => SetMetadata("isPublic", true);   // skip AuthGuard
export const Roles = (...roles: UserRole[]) => SetMetadata("roles", roles);  // require role
```

Usage:
```typescript
@Public()                        // anyone can access
@Roles("admin")                  // only admin (AuthGuard still runs first)
@Request() req: { user: { id: string } }  // always available after AuthGuard
```

---

### 5. Register guards as APP_GUARD (global)

```typescript
// src/auth/auth.module.ts
@Module({
  controllers: [AuthController],
  providers: [
    AuthService,
    { provide: APP_GUARD, useClass: AuthGuard },   // runs first on every request
    { provide: APP_GUARD, useClass: RolesGuard },  // runs second
  ],
  exports: [AuthService],
})
export class AuthModule {}
```

**Order matters:** `APP_GUARD` entries run in order. AuthGuard must come before RolesGuard because RolesGuard reads `request.user` set by AuthGuard.

**Only import `AuthModule` once** — in `AppModule`. `APP_GUARD` is already global via NestJS DI, no need to add it elsewhere.

---

### 6. AuthController endpoints

```typescript
@Controller("auth")
export class AuthController {
  // Email/password login — returns JWT pair
  @Public()
  @Post("login")
  @HttpCode(HttpStatus.OK)
  login(@Body() body: { email: string; password: string }) {
    return this.authService.login(body.email, body.password);
  }
  // → { access_token, refresh_token, expires_in, user: { id, email } }

  // Register new user
  @Public()
  @Post("register")
  register(@Body() body: { email: string; password: string }) {
    return this.authService.register(body.email, body.password);
  }

  // Refresh expired access token
  @Public()
  @Post("refresh")
  @HttpCode(HttpStatus.OK)
  refresh(@Body() body: { refresh_token: string }) {
    return this.authService.refresh(body.refresh_token);
  }

  // Get current user (requires auth)
  @Get("me")
  getMe(@Request() req: { user: { id: string } }) {
    return this.authService.getMe(req.user.id);
  }
  // → { id, email, role: "user" | "admin" }

  // Logout
  @Post("logout")
  logout(@Request() req) {
    const token = req.headers.authorization?.split(" ")[1];
    if (token) this.authService.logout(token);
    return { ok: true };
  }

  // Delete account + all associated data
  @Delete("account")
  @HttpCode(HttpStatus.NO_CONTENT)
  deleteAccount(@Request() req: { user: { id: string } }) {
    return this.authService.deleteAccount(req.user.id);
  }
}
```

**Google OAuth — no backend endpoint needed.** OAuth is handled entirely by Supabase + the frontend callback. The resulting JWT is identical to email/password JWT and validated by the same `AuthGuard`.

---

### 7. Rate limiting with ThrottlerGuard

Apply to auth endpoints to prevent brute force:

```typescript
// app.module.ts — register once globally
ThrottlerModule.forRoot([
  { name: "auth-burst", ttl: seconds(60), limit: 10 },
])

// auth.controller.ts — per-endpoint
@Public()
@UseGuards(ThrottlerGuard)
@Throttle({ "auth-burst": { limit: 10, ttl: 60000 } })
@Post("login")
login(...) {}
```

**Only `@Public()` endpoints need `@UseGuards(ThrottlerGuard)`** — `APP_GUARD` does not apply `ThrottlerGuard` globally, so add it explicitly where needed.

---

### 8. Required env vars (backend)

```env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

---

## Frontend (React + @idevconn/supabase)

### 1. Install

```bash
cd apps/client && npm install @idevconn/supabase
```

### 2. Create Supabase singleton

```typescript
// src/lib/supabase.ts
import { createSupabaseClient, AuthService } from "@idevconn/supabase";

export const supabase = createSupabaseClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
);

export const authService = new AuthService<"google">(supabase, {
  allowedProviders: ["google"],
});
```

**Module-level singleton** — import `supabase` and `authService` from here everywhere. Do not call `createSupabaseClient` more than once.

### 3. Auth store (Zustand)

```typescript
// src/stores/auth.ts
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setAuth: (data) => set({ accessToken: data.accessToken, refreshToken: data.refreshToken, user: data.user }),
      setUser: (user) => set({ user }),
      logout: () => set({ accessToken: null, refreshToken: null, user: null }),
    }),
    { name: "my-app-auth" },  // localStorage key
  ),
);
```

### 4. API client with auto token refresh

```typescript
// src/api/client.ts
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = useAuthStore.getState().accessToken;
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");

  let res = await fetch(`${import.meta.env.VITE_API_URL}${path}`, { ...options, headers });

  // Token expired → try refresh
  if (res.status === 401 && token) {
    const refresh = useAuthStore.getState().refreshToken;
    if (refresh) {
      const r = await fetch(`${import.meta.env.VITE_API_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (r.ok) {
        const data = await r.json();
        useAuthStore.getState().setAuth({ accessToken: data.access_token, refreshToken: data.refresh_token, user: useAuthStore.getState().user! });
        headers.set("Authorization", `Bearer ${data.access_token}`);
        res = await fetch(`${import.meta.env.VITE_API_URL}${path}`, { ...options, headers });
      }
    }
  }

  // Still 401 → force logout
  if (res.status === 401) {
    useAuthStore.getState().logout();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.message ?? body.error ?? `HTTP ${res.status}`);
  }
  return res.json();
}
```

### 5. Email/password login (React Query mutation)

```typescript
// src/queries/auth.ts
export function useLogin() {
  return useMutation({
    mutationFn: (data: { email: string; password: string }) =>
      api<{ access_token: string; refresh_token: string; user: { id: string; email: string; role: "admin" | "user" } }>(
        "/auth/login", { method: "POST", body: JSON.stringify(data) }
      ),
    onSuccess: (data) => {
      useAuthStore.getState().setAuth({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        user: data.user,
      });
    },
  });
}
```

### 6. Google OAuth login

```typescript
// In login component — triggers browser redirect to Google
async function handleGoogleLogin() {
  const { error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: `${window.location.origin}/auth/callback` },
  });
  if (error) setError(error.message);
  // Browser navigates away — no further code runs
}
```

### 7. OAuth callback route

```typescript
// src/routes/auth.callback.tsx  (TanStack Router: maps to /auth/callback)
export const Route = createFileRoute("/auth/callback")({
  component: AuthCallbackPage,
});

function AuthCallbackPage() {
  const navigate = useNavigate();

  useEffect(() => {
    // Case 1: session already ready before component mounts
    void authService.getCurrentUser().then(async ({ session }) => {
      if (session) await commitSession(session);
    });

    // Case 2: session arrives via onAuthStateChange (normal flow)
    const sub = authService.onAuthStateChange(async (event, session) => {
      if (event === "SIGNED_IN" && session) await commitSession(session);
    });

    const timeout = setTimeout(() => navigate({ to: "/login" }), 10_000);

    return () => { sub.unsubscribe(); clearTimeout(timeout); };
  }, []);

  async function commitSession(session: { access_token: string; refresh_token: string; user: { id: string; email?: string } }) {
    // 1. Store tokens so api() can authenticate
    useAuthStore.getState().setAuth({
      accessToken: session.access_token,
      refreshToken: session.refresh_token,
      user: { id: session.user.id, email: session.user.email ?? "", role: "user" },
    });
    // 2. Fetch real role from NestJS
    try {
      const user = await api<{ id: string; email: string; role: "admin" | "user" }>("/auth/me");
      useAuthStore.getState().setUser(user);
    } catch { /* role stays "user" */ }
    // 3. Navigate to app
    void navigate({ to: "/", search: {} });
  }

  return <div className="flex min-h-screen items-center justify-center">Signing in…</div>;
}
```

### 8. Route protection (TanStack Router)

```typescript
// src/routes/_dashboard.tsx — protected layout
export const Route = createFileRoute("/_dashboard")({
  beforeLoad: () => {
    if (!useAuthStore.getState().accessToken) {
      throw redirect({ to: "/login" });
    }
  },
  component: DashboardLayout,
});
// All routes under _dashboard/ are automatically protected
```

### 9. Required env vars (frontend)

```env
VITE_API_URL=http://localhost:3000/api
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
```

---

## Supabase Configuration

### supabase/config.toml — key auth settings

```toml
[auth]
site_url = "http://localhost:5173"          # your frontend URL
additional_redirect_urls = [
  "http://localhost:5173/auth/callback",    # local dev callback
  "https://yourdomain.com/auth/callback",  # production callback
]
jwt_expiry = 3600                           # 1 hour (max 604800 = 1 week)
enable_refresh_token_rotation = true
refresh_token_reuse_interval = 10
enable_signup = true
minimum_password_length = 6

# Google OAuth — local dev only
# Production uses Dashboard (see below)
[auth.external.google]
enabled = true
client_id = "env(SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID)"
secret = "env(SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET)"
```

**Never hardcode secrets in `config.toml`.** Use `env(VAR_NAME)` and set the vars in your local shell or `.env` (gitignored).

Apply config changes:
```bash
npx supabase db push        # push migrations
npx supabase start          # restart local stack to pick up config changes
```

### DB migration — user_roles auto-create on signup

Every new user (email OR Google OAuth) gets a row automatically:

```sql
-- runs in: supabase/migrations/<timestamp>_create_user_roles.sql
create table user_roles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role user_role not null default 'user'
);

create or replace function handle_new_user()
returns trigger as $$
begin
  insert into public.user_roles (user_id, role) values (new.id, 'user');
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();
```

This means `getUserRole()` on the backend always finds a row — no "defaults to user" fallback needed if the trigger is in place.

### Supabase Dashboard Setup (Google OAuth — production)

1. **Authentication → Providers → Google** → Enable
2. Paste **Google Client ID** and **Google Client Secret**  
   (Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID)
3. Add to **Authorized redirect URIs** in Google Cloud Console:
   ```
   https://<project-ref>.supabase.co/auth/v1/callback
   ```

---

## Guard Execution Flow (every request)

```
Request arrives
     │
     ▼
AuthGuard.canActivate()
     ├── @Public() on route? → pass (skip all further checks)
     ├── No Authorization header? → 401
     ├── supabase.admin.auth.getUser(token) fails? → 401
     └── OK → sets request.user = { id, email, ... }
     │
     ▼
RolesGuard.canActivate()
     ├── No @Roles() on route? → pass
     ├── No request.user? → 403
     ├── DB lookup: user_roles WHERE user_id = request.user.id
     │   (defaults to "user" if no row — Google OAuth users have no row initially)
     └── role not in requiredRoles? → 403
     │
     ▼
Controller method runs
request.user = { id: string, email: string, role: "user" | "admin" }
```

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Registering `AuthModule` in multiple modules | Import it only in `AppModule` — `APP_GUARD` is already global |
| Adding Supabase client to frontend for data queries | Frontend data goes through NestJS API only; Supabase client is auth-only |
| Forgetting `@Public()` on login/register/refresh | These routes must be accessible without a token |
| Using `supabase.admin` for user auth operations | Use `supabase.auth` (anon client) for `signInWithPassword`/`refreshSession` |
| Using `supabase.auth` for DB operations | Use `supabase.admin` for all DB queries (anon key has RLS restrictions) |
| Not handling Google OAuth users in role lookup | `getUserRole` must default to `"user"` when no `user_roles` row exists |
| Applying `ThrottlerGuard` globally via `APP_GUARD` | Add `@UseGuards(ThrottlerGuard)` + `@Throttle()` per controller instead |
| Calling `createSupabaseClient` multiple times | Create once in `lib/supabase.ts`, export singleton |
