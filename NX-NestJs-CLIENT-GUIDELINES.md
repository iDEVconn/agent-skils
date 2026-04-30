---
name: nestjs-nx-react-guidelines
description: Use when starting new project or adding new feature/module to this stack. Covers NestJS module structure, guard ordering, Nx workflow, React client patterns, and test conventions derived from this codebase.
---

# NestJS + Nx + React ? Project Guidelines

## Overview

Stack: **NestJS 11** backend (microservices) � **Nx 22** monorepo � **React 19** frontend � **Firebase Auth + Firestore** � **Yarn 4 (PnP)**.

---

## 1. Nx ? Workspace Rules

**Always use Nx, never direct tooling.**

```bash
nx run <project>:<target>          # single
nx run-many -t build lint test     # all projects
nx affected -t test                # only changed

# Package manager: YARN ONLY
yarn add <pkg>         # ?
npm install <pkg>      # ? never
```

**After every code change ? mandatory:**
```bash
nx lint <project>
nx build <project>
nx test <project>
```

**Path aliases** (defined in `tsconfig.base.json`):
- `@common/types` ? `libs/types/src/index.ts`
- `@common/utils` ? `libs/utils/src/index.ts`
- `@firebase/admin` ? `libs/firebase-admin/src/index.ts`
- `@api/*` ? `apps/api/src/*`
- `@auth/client` ? `libs/auth-client/src/index.ts`

**Monorepo layout:**
```
apps/
  api/                   # NestJS main API
  microservices/
    auth/                # Auth microservice
    upload/              # Upload microservice
    subscriptions/       # Subscriptions microservice
  client/                # React frontend (admin)
  consumer/              # React frontend (end-user)
libs/
  types/                 # Shared TypeScript types
  utils/                 # Common utilities
  auth-client/           # Auth microservice client
  upload-client/         # Upload microservice client
  firebase-admin/        # Firebase Admin wrapper
```

---

## 2. NestJS ? Module Structure

**One feature = one module.** Module contains: `controller`, `service`, `module`, `dto/`.

```
src/
  tenants/
    dto/
      create-tenant.dto.ts
    tenants.controller.ts
    tenants.service.ts
    tenants.module.ts
    __tests__/
      tenants.controller.unit.test.ts
      tenants.service.unit.test.ts
```

**Module template:**
```typescript
@Module({
  imports: [ConfigModule],   // only what this module needs
  controllers: [TenantsController],
  providers: [TenantsService],
  exports: [TenantsService], // export only if other modules need it
})
export class TenantsModule {}
```

**App module** ? import `ConfigModule.forRoot({ isGlobal: true })` once at root.

---

## 3. NestJS ? Guards (critical: order matters)

Guards execute **left to right**. Each guard can read what previous guards wrote to `request`.

### Guard registry

| Guard | File | What it does |
|-------|------|--------------|
| `ThrottlerGuard` | `@nestjs/throttler` | Rate-limiting ? must be **first** on public endpoints |
| `JwtGuard` | `common/guards/jwt.guard.ts` | Verifies Firebase JWT ? sets `request.user` |
| `RolesGuard` | `common/guards/roles.guard.ts` | Checks `request.user.role` vs `@Roles()` metadata |
| `AdminGuard` | `common/guards/admin.guard.ts` | Shortcut: requires `role === 'admin'` |
| `EmailVerifiedGuard` | `common/guards/email-verified.guard.ts` | Requires `request.user.email_verified` |
| `RecaptchaGuard` | `common/guards/recaptcha.guard.ts` | Validates reCAPTCHA token from `recaptcha-token` header |
| `ApiKeyGuard` | `common/guards/api-key.guard.ts` | Validates `x-api-key`, enforces monthly quota, sets `request.tenantId` |

### Standard guard chains

```typescript
// Admin-only endpoint
@UseGuards(JwtGuard, RolesGuard)
@Roles('admin')
@Controller('tenants')
export class TenantsController {}

// Authenticated user (any role)
@UseGuards(JwtGuard)
@Get('profile')
async getProfile(@Req() req: RequestWithUser) {}

// Authenticated user + bot protection (e.g. file upload)
// Two separate @UseGuards ? JwtGuard on class, RecaptchaGuard on class,
// @Recaptcha(threshold, action) on specific methods
@Controller('upload')
@UseGuards(JwtGuard)
@UseGuards(RecaptchaGuard)
export class ApiUploadController {
  @Post()
  @Recaptcha(0.5, 'file_upload')  // per-method threshold override
  async uploadFile() {}

  @Delete()  // RecaptchaGuard still runs here (no @Recaptcha = uses defaults)
  async deleteFile() {}
}

// Public endpoint with bot protection only (registration, login)
@UseGuards(RecaptchaGuard)
@Post('register')
async register() {}

// Public unauthenticated ? rate-limit only (e.g. marketplace)
@UseGuards(ThrottlerGuard)
@Controller('marketplace')
export class MarketplaceController {}

// Public multi-tenant API key ? rate-limit THEN key validation
@UseGuards(ThrottlerGuard, ApiKeyGuard)
@Controller('public/subscriptions')
export class SubscriptionsController {}
```

### ThrottlerGuard ? when and how

**Use on:** public endpoints that are accessible without JWT (multi-tenant consumer API, marketplace, any `/public/*` route).  
**Skip on:** JWT-protected admin/user endpoints ? Firebase token verification already prevents anonymous abuse.

**Setup ? register `ThrottlerModule` in the feature module** (not global `AppModule`):

```typescript
// subscriptions.module.ts
import { ThrottlerModule, seconds } from '@nestjs/throttler';

@Module({
  imports: [
    ThrottlerModule.forRoot([
      {
        name: 'public-burst',  // descriptive name for logging
        ttl: seconds(60),      // window: 60 seconds
        limit: 60,             // max requests per window per IP
      },
    ]),
    // ...other imports
  ],
  controllers: [SubscriptionsController],
})
export class SubscriptionsModule {}
```

**Apply at controller level** ? `ThrottlerGuard` must be **first**:

```typescript
import { ThrottlerGuard } from '@nestjs/throttler';

@UseGuards(ThrottlerGuard, ApiKeyGuard)  // ThrottlerGuard first ? rejects before key lookup
@Controller('public/subscriptions')
export class SubscriptionsController {}
```

**Why first:** Rate limit runs before expensive operations (bcrypt API key comparison, Firestore reads). Rejects hammering clients at zero cost.

**Default rate in this project:** `60 req / 60 s` per IP. Adjust per endpoint sensitivity:
- Marketplace read (cheap): 60/60s ?
- Auth/registration: lower (10?20/60s) + add `RecaptchaGuard`
- File upload: lower (5?10/60s)

---

### RecaptchaGuard ? when, how, why

**Files:**
- Config: `apps/api/src/recaptcha/recaptcha.config.ts`
- Module: `apps/api/src/recaptcha/recaptcha.module.ts`
- Service: `apps/api/src/recaptcha/recaptcha.service.ts`
- Guard: `apps/api/src/common/guards/recaptcha.guard.ts`
- Decorator: `apps/api/src/common/decorators/recaptcha.decorator.ts`

**When to use:**
- Public endpoints accessible without JWT that are bot-attack targets: registration, login, contact forms
- Sensitive authenticated endpoints where cost per request is high: file upload
- **Skip on:** admin-only JWT endpoints (already human-verified), internal microservice calls

**Why:** reCAPTCHA v3 returns a score 0?1 (1 = human, 0 = bot). Guard rejects requests below the minimum score or with wrong `action` string. Prevents credential stuffing, spam uploads, and brute-force without user friction.

**Env vars** (set in `.env`):
```
RECAPTCHA_SECRET_KEY=<google-secret>   # required in production
RECAPTCHA_MINIMUM_SCORE=0.5            # default threshold (0?1)
RECAPTCHA_ENABLED=false                # set to disable in dev/test
```

**Step 1 ? import `RecaptchaModule` in your feature module:**

```typescript
// upload.module.ts
import { RecaptchaModule } from '@api/recaptcha/recaptcha.module';

@Module({
  imports: [RecaptchaModule, UploadClientModule],  // RecaptchaModule exports guard + service
  controllers: [ApiUploadController],
})
export class ApiUploadModule {}
```

**Step 2 ? apply guard on controller, per-method threshold via `@Recaptcha`:**

```typescript
import { Recaptcha } from '@api/common/decorators/recaptcha.decorator';
import { JwtGuard } from '@api/common/guards/jwt.guard';
import { RecaptchaGuard } from '@api/common/guards/recaptcha.guard';

@Controller('upload')
@UseGuards(JwtGuard)        // auth first
@UseGuards(RecaptchaGuard)  // then bot check
export class ApiUploadController {

  @Post()
  @Recaptcha(0.5, 'file_upload')  // override threshold + set expected action
  async uploadFile() {}

  @Delete()
  // RecaptchaGuard still runs here ? uses RECAPTCHA_MINIMUM_SCORE default, no action check
  async deleteFile() {}
}
```

**Token transport:** client must send token in HTTP header `recaptcha-token`. Guard reads it there ? never from body.

**Score thresholds by sensitivity:**

| Endpoint | Threshold | Action string |
|----------|-----------|---------------|
| File upload | 0.5 | `'file_upload'` |
| Registration / login | 0.7?0.9 | `'register'` / `'login'` |
| Low-risk reads | 0.3?0.5 | omit or set action |

**Action validation:** the `action` string passed to `@Recaptcha('action')` must match what the frontend sends in the reCAPTCHA token. Mismatch ? `ForbiddenException`. Use namespaced strings: `'file_upload'`, `'register'`, `'login'`.

**Dev/test bypass:** set `RECAPTCHA_ENABLED=false` ? service returns `{ success: true, score: 1.0 }` without calling Google. Never disable in production.

**Guard implementation rules (how `RecaptchaGuard` reads metadata):**

```typescript
// Guard reads per-method decorators via Reflector
const threshold = this.reflector.get<number>(RECAPTCHA_THRESHOLD, context.getHandler());
const expectedAction = this.reflector.get<string>(RECAPTCHA_ACTION, context.getHandler());
// Falls back to RECAPTCHA_MINIMUM_SCORE from config when threshold is undefined
```

### Guard implementation rules

1. **JWT must always be first** ? it populates `request.user`; role guards depend on it.
2. **Never trust `request.user` without `JwtGuard` before it.**
3. Throw `UnauthorizedException` for auth failures, `ForbiddenException` for permission failures.
4. Guards are `@Injectable()` ? use constructor DI for services.
5. Use `Reflector` to read metadata set by decorators (`@Roles`, `@RecaptchaAction`).

```typescript
// Correct guard pattern
@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.getAllAndOverride<string[]>('roles', [
      context.getHandler(),
      context.getClass(),  // controller-level @Roles override per-method
    ]);
    if (!requiredRoles) return true;  // no restriction

    const { user } = context.switchToHttp().getRequest();
    if (!user) throw new UnauthorizedException('User not authenticated');

    if (!requiredRoles.some((r) => user.role === r)) {
      throw new UnauthorizedException(`Required: ${requiredRoles.join(', ')}`);
    }
    return true;
  }
}
```

### Custom decorator for guard metadata

```typescript
// decorators/roles.decorator.ts
export const Roles = (...roles: string[]) => SetMetadata('roles', roles);
```

---

## 4. NestJS ? Controllers

```typescript
@ApiTags('tenants')
@ApiBearerAuth('access-token')
@UseGuards(JwtGuard, RolesGuard)
@Roles('admin')
@Controller('tenants')
export class TenantsController {
  private readonly logger = new Logger(TenantsController.name);

  constructor(private readonly tenantsService: TenantsService) {}

  @ApiOperation({ summary: 'Create a new tenant' })
  @Post()
  async createTenant(
    @Body() dto: CreateTenantDto,
    @Req() req: RequestWithUser,
  ) {
    return this.tenantsService.createTenant(dto, req.user.uid);
  }
}
```

**Rules:**
- Always `async/await` ? no sync methods.
- `@Req()` typed via `RequestWithUser` or `RequestWithTenant` interface.
- `Logger` declared as `private readonly` with `ClassName` as context.
- Swagger decorators on every endpoint: `@ApiOperation`, `@ApiParam`, `@ApiBearerAuth`.
- Controllers delegate to services ? zero business logic in controllers.

**Request interfaces:**
```typescript
// common/interfaces/request-with-user.interface.ts
export interface RequestWithUser extends Request {
  user: DecodedIdToken;  // set by JwtGuard
}

// common/interfaces/request-with-tenant.interface.ts
export interface RequestWithTenant extends Request {
  tenantId: string;  // set by ApiKeyGuard
}
```

---

## 5. NestJS ? Services

```typescript
@Injectable()
export class TenantsService {
  private readonly logger = new Logger(TenantsService.name);

  constructor(
    private readonly authClient: AuthClientService,  // microservice client
  ) {}

  async createTenant(dto: CreateTenantDto, adminUid: string): Promise<ITenant> {
    try {
      const response = await this.authClient.createTenant(dto);
      if (!response.success) throw new Error(response.error);
      return response.tenant;
    } catch (error: any) {
      this.logger.error('Error creating tenant:', error);
      throw error;
    }
  }
}
```

**Rules:**
- Always inject dependencies via constructor, never `new`.
- Wrap microservice calls in `try/catch` and log errors.
- For microservice clients returning Observables: `lastValueFrom(client.method())`.
- Services own business logic; controllers own HTTP mapping.
- Ownership/security checks go in service, not controller.

---

## 6. NestJS ? DTOs & Validation

```typescript
import { IsString, IsEmail, IsOptional, Length } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

export class CreateTenantDto {
  @ApiProperty()
  @IsString()
  @Length(2, 100)
  name: string;

  @ApiProperty()
  @IsEmail()
  email: string;

  @ApiProperty({ required: false })
  @IsOptional()
  @IsString()
  company?: string;
}
```

**Global ValidationPipe** (set in `main.ts`, do not repeat per-controller):
```typescript
app.useGlobalPipes(
  new ValidationPipe({
    whitelist: true,           // strip unknown fields
    forbidNonWhitelisted: true, // 400 on unknown fields
    transform: true,           // auto-cast types
  }),
);
```

---

## 7. NestJS ? Bootstrap (main.ts)

```typescript
async function bootstrap() {
  const app = await NestFactory.create<NestExpressApplication>(AppModule);

  app.setGlobalPrefix('api/v1');
  app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }));

  // CORS ? static for admin dashboard, dynamic PublicCorsMiddleware for public endpoints
  // setupSwagger ? only outside production
  if (!isProd(process.env)) setupSwagger(app);

  await app.listen(getEnv('API_PORT', { defaultValue: 3000, env: process.env }));
}
```

**Rules:**
- Global prefix: `api/v1`.
- Swagger: only non-prod, separate port.
- Env vars: always via `getEnv()` from `@common/utils`, never `process.env.X` directly.
- Two-layer CORS: static allowlist for dashboard, `PublicCorsMiddleware` for `/api/v1/public/*`.

---

## 8. NestJS ? Microservices Pattern

Microservices communicate via **TCP** (NestJS `ClientProxy`). The API never calls microservices directly ? it uses generated client libraries (`libs/auth-client`, `libs/upload-client`).

```typescript
// Service in API layer ? thin delegation
@Injectable()
export class ApiAuthService {
  constructor(private readonly authClient: AuthClientService) {}

  async setUserRole(user: User, defaultRole?: EUserRole) {
    return lastValueFrom(this.authClient.setUserRole({ user, defaultRole }));
  }
}
```

**Upload uses Strategy pattern** ? new storage backends implement `UploadStrategy` interface.

---

## 9. Client ? State Management

| Type | Tool | Use for |
|------|------|---------|
| Server state | TanStack Query | API/Firestore data |
| Global UI state | Zustand | loading, drawer, menu, locale |
| Auth/permission state | React Context | user, CASL abilities |
| Form state | Ant Design Form | form fields, dirty tracking |

### Query key convention

```typescript
export const featureKeys = {
  all: ['features'] as const,
  lists: () => [...featureKeys.all, 'list'] as const,
  list: (filters: Record<string, any>) => [...featureKeys.lists(), filters] as const,
  detail: (id: string) => [...featureKeys.all, 'detail', id] as const,
};
```

### Custom query/mutation wrappers

```typescript
// Always use project wrappers, not raw useQuery/useMutation
const { data, isLoading } = useStoreQuery({
  queryKey: featureKeys.list({ type: 'user' }),
  queryFn: () => getUserFeatures(),
});

const mutation = useStoreMutation({
  mutationFn: (data: IFeature) => createFeature(data),
  invalidateQueries: [featureKeys.lists()],  // auto-invalidate on success
});
```

### Hook pattern

```typescript
export const useFeatures = () => {
  const { useUserFeatures } = useFeatureQueries();
  const { setError } = useError();

  const { data, isLoading, isFetching } = useUserFeatures();
  const { loading, setLoading } = useLoading(isLoading || isFetching);

  const onDeactivate = useCallback(async (entity: IFeature) => {
    try {
      setLoading(true);
      await deactivateMutation.mutateAsync(entity.id as string);
    } catch (error) {
      setError({ data: error as TErrorData, description: EErrorType.FAILED_DEACTIVATE });
      throw error;
    } finally {
      setLoading(false);
    }
  }, [deactivateMutation, setError, setLoading]);

  return { loading, entities: data?.features ?? [], total: data?.total ?? 0, onDeactivate };
};
```

---

## 10. Client ? Authorization (CASL)

**Backend guards = source of truth. CASL = UX only.**

```typescript
// hooks/useAbilities.tsx
const { can } = useAbility();

// In JSX
<Can I="update" a="feature">
  <EditButton />
</Can>

// In hooks
if (!can('delete', 'tenant')) return null;
```

**Rules:**
- Never use CASL as the only gate ? always pair with backend guard.
- Actions: `EAbilityActions` (READ, CREATE, UPDATE, DELETE, MANAGE, ...).
- Subjects: `EAbilitySubjects` (TENANTS, SUBSCRIPTIONS, FEATURES, ...).
- Consumer app (`apps/consumer`) uses parallel `useAbilities` for consumer roles.
- Backend authorization: `JwtGuard` + `EmailVerifiedGuard` + ownership check in service.

---

## 11. Client ? Routing

```typescript
// Route-based code splitting
export const FeatureEditPage = lazy(() =>
  import('../pages/features/feature/feature.edit').then((m) => ({
    default: m.FeatureEditPage ?? m.default,
  })),
);

// Route configuration
<Route
  path={ERoutePaths.FEATURE_EDIT}
  element={
    <LazyRoute>
      <ProtectedRoute>
        <FeatureEditPage />
      </ProtectedRoute>
    </LazyRoute>
  }
/>
```

**Route enum** ? all paths in `ERoutePaths`, never raw strings.

---

## 12. Tests ? Backend (Jest)

```typescript
describe('TenantsService', () => {
  let service: TenantsService;
  let authClient: AuthClientService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        TenantsService,
        {
          provide: AuthClientService,
          useValue: { createTenant: jest.fn() },
        },
      ],
    }).compile();

    service = module.get<TenantsService>(TenantsService);
    authClient = module.get<AuthClientService>(AuthClientService);
  });

  afterEach(() => jest.clearAllMocks());

  it('should call authClient.createTenant and return result', async () => {
    const dto = { name: 'Test', email: 'a@b.com' } as CreateTenantDto;
    const expected = { id: '1', ...dto };
    jest.spyOn(authClient, 'createTenant').mockReturnValue(of({ success: true, tenant: expected }) as any);

    const result = await service.createTenant(dto, 'admin-uid');
    expect(result).toEqual(expected);
  });
});
```

**Guard tests** ? mock `ExecutionContext` manually:
```typescript
const mockContext = {
  switchToHttp: () => ({
    getRequest: () => ({ headers: { authorization: 'Bearer token' }, user: {} }),
  }),
} as unknown as ExecutionContext;
```

**Rules:**
- Use `Test.createTestingModule()` ? never instantiate services with `new`.
- Mock external services via `useValue` in providers array.
- `jest.clearAllMocks()` in `afterEach`.
- Test file: `__tests__/name.unit.test.ts` inside the feature folder.
- Run: `nx test <project>` ? never `jest` directly.

---

## 13. Tests ? Frontend (Vitest)

```typescript
// vi.mock FIRST, before any imports
vi.mock('react-router', () => ({ useNavigate: vi.fn() }));
vi.mock('@client/store/loading.store', () => ({
  useLoading: vi.fn(),
}));

// ESM imports after mocks ? specifier must match vi.mock key exactly
import { useNavigate } from 'react-router';

describe('useFeatures', () => {
  beforeEach(() => {
    vi.mocked(useNavigate).mockReturnValue(vi.fn());
    vi.mocked(useLoading).mockReturnValue({ loading: false, setLoading: vi.fn() });
  });

  afterEach(() => vi.clearAllMocks());

  it('returns empty list on no data', () => {
    const { result } = renderHook(() => useFeatures());
    expect(result.current.entities).toEqual([]);
  });
});
```

**Full-shape mock for factory hooks:**
```typescript
// Always return complete interface ? not just the methods used in this test
vi.mock('@client/queries/useFeatureQueries', () => ({
  useFeatureQueries: vi.fn(),
}));

const createFeatureQueriesMock = (overrides = {}) => ({
  useUserFeatures: vi.fn().mockReturnValue({ data: null, isLoading: false, isFetching: false, isError: false, error: null, refetch: vi.fn() }),
  useCreateFeature: vi.fn().mockReturnValue({ mutateAsync: vi.fn() }),
  useUpdateFeature: vi.fn().mockReturnValue({ mutateAsync: vi.fn() }),
  useDeleteFeature: vi.fn().mockReturnValue({ mutateAsync: vi.fn() }),
  ...overrides,
});

beforeEach(() => {
  vi.mocked(useFeatureQueries).mockReturnValue(createFeatureQueriesMock());
});
```

**Test file types:**

| Type | Suffix | Environment | When |
|------|--------|-------------|------|
| Unit | `*.unit.test.ts(x)` | jsdom | hooks, components, utils |
| Browser | `*.browser.test.ts(x)` | Playwright/Chromium | navigation, DOM events, real router |

**Commands:**
```bash
nx run client:test          # all
nx run client:test:unit     # unit only (fast, ~700ms)
nx run client:test:browser  # browser (Chromium, ~3s)
```

**Coverage minimum: 80%** (lines, branches, functions) for `apps/client`.

**Rules:**
- `vi.mock()` before all imports.
- Import specifier must match `vi.mock` key exactly (including extension).
- Add `__esModule: true` for named-export mocks.
- Never use `require()` except for type conflict workarounds.
- Fix test files to match production API ? never change production code for tests.
- `vi.clearAllMocks()` in `afterEach`.
- Dynamic imports in tests: always `async/await`.

---

## 14. Shared Types

Single vocabulary across all apps ? `libs/types`.

```typescript
// Always import from lib, never duplicate
import { IFeature, ITenant, EUserRole, ETier } from '@common/types';
```

**Rules:**
- New cross-cutting types ? `libs/types`.
- Consumer apps narrow shapes via DTO validation (`@IsIn(...)`), not new types.
- Enums: `E` prefix (`EUserRole`, `ETier`, `EAbilityActions`).
- Interfaces: `I` prefix (`IFeature`, `ITenant`).
- Constants: `C` prefix (`CScheduler`, `CFeaturesPath`).

---

## 15. Security Checklist

- [ ] Authentication: `JwtGuard` on all non-public endpoints.
- [ ] Authorization: `RolesGuard` + `@Roles()` for role-restricted actions.
- [ ] Ownership: service layer validates that sub-resource belongs to parent (e.g., API key belongs to tenant).
- [ ] Input validation: DTO with `class-validator` + global `ValidationPipe(whitelist, forbidNonWhitelisted)`.
- [ ] CORS: static allowlist from `CORS_ALLOWED_ORIGINS` env var; `PublicCorsMiddleware` for `/public/*`.
- [ ] reCAPTCHA: `RecaptchaGuard` on public registration/auth endpoints.
- [ ] API keys: bcrypt-hashed in Firestore, monthly quota enforced atomically.
- [ ] CASL on client: UX only ? never sole gate.
- [ ] Env vars: `getEnv()` wrapper ? fails fast on missing required vars.

---

## 16. Documentation Rule

Every PR that changes behavior, data shape, or setup **must** update related `.md` in the same commit:
- New env var ? `apps/<app>/.env.example` + `docs/manual-setup.md`
- New cross-cutting decision ? `docs/conventions.md`
- New complex flow ? `docs/<topic>.md`
- Architecture change ? `ARCHITECTURE.md`
