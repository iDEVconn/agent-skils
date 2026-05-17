---
name: nx-kotlin-integration
description: Scaffold or maintain a Kotlin/JVM (Gradle Kotlin DSL) subproject inside a TypeScript-first Nx monorepo. Use whenever the user mentions Kotlin in Nx, Java in Nx, Gradle in Nx, @nx/gradle, @jnxplus/nx-gradle, adding a JVM app or ML service to an Nx workspace, "ml service in nx", "kotlin subproject", "scaffold kotlin app", troubleshooting `projectDependencyTask` not found, Gradle configuration cache errors in Nx, or WebStorm refusing to load the Kotlin plugin (`com.intellij.modules.java-capable`). Encodes the exact plugin choice, Gradle plugin versions, files to create, and gotchas discovered when integrating a Kotlin/JVM app under apps/ alongside existing React + NestJS workspaces.
---

# Nx + Kotlin/JVM (Gradle Kotlin DSL) Integration

This skill is a playbook for the specific job of dropping a Kotlin/JVM Gradle subproject into an Nx workspace that already has JS/TS apps. The advice is opinionated because the obvious-looking choices (the official `@nx/gradle` plugin, defaults from `gradle init`, leaving the configuration cache on) silently don't work in this layout. The notes below capture what does work and **why** — so when the next variant shows up (Java app, Maven, Spring Boot) you can adapt instead of cargo-culting.

## When to use this skill

Reach for it whenever the work involves:

- Adding a new JVM (Kotlin or Java) project under `apps/` of an existing Nx monorepo
- Picking an Nx Gradle plugin (`@nx/gradle` vs `@jnxplus/nx-gradle`) and explaining the tradeoff
- Wiring `project.json` / `nx.json` so Nx commands proxy to `gradlew`
- Diagnosing "Task `projectDependencyTask` not found" or "Configuration cache problems found" errors
- Onboarding a developer who wants to open the project in WebStorm and hits the missing Kotlin plugin
- Deciding how the JVM service talks to the rest of the stack (auth, DB access, payments)

## The big picture

A TypeScript-first Nx monorepo treats `nx.json` as the source of truth and runs everything through Nx targets. Gradle, by contrast, expects to *own* its workspace root — `settings.gradle.kts` at the top of a Gradle workspace, every subproject `include`d from there. When you try to nest a single Gradle project under `apps/<name>/` of a TS monorepo, the two world views collide.

There are three things that have to be true for the integration to feel native:

1. **Gradle stays contained.** The Gradle root must live inside the subproject directory (e.g. `apps/ml/settings.gradle.kts`), not at `nx.json`'s sibling. We don't want a stray `settings.gradle.kts` polluting the JS workspace root.
2. **Nx still sees the project.** `nx show projects`, `nx graph`, and `affected` must include the JVM project so CI can pick it up.
3. **Targets are cacheable.** `nx run ml:build` should hit the Nx cache the second time, with accurate `inputs` / `outputs` derived from the Gradle layout.

The plugin and configuration choices below are the smallest set that satisfies all three.

## Pick the right plugin

| Option | Verdict | Why |
|---|---|---|
| `@nx/gradle` (Nrwl official) | **Don't use** | Hard-coded to expect the Gradle root at the workspace root. There is no `gradleRoot` / `gradleRootDirectory` option. Moving Gradle to the workspace root drags wrapper scripts, `settings.gradle.kts`, and `build/` into the JS-first repo. |
| `@jnxplus/nx-gradle` | **Use this** | Accepts `gradleRootDirectory: "apps/ml"` in `nx.json`. Discovers the Gradle project from a subdirectory and registers it as an Nx node. Community plugin, but actively maintained by gridatek and the only realistic option for polyglot subprojects today. |
| Manual `nx:run-commands` only | Fallback | Works everywhere — just shell out to `./gradlew` from a `project.json` target. You lose automatic graph discovery and the `affected` integration for Gradle dependencies. Acceptable as a stopgap; not what we want long-term. |

Install:

```bash
npm install -D @jnxplus/nx-gradle
```

## Two plugins, not one

`@jnxplus/nx-gradle` is the **Node-side** plugin (it runs as part of Nx's project graph computation). It needs a **Gradle-side** counterpart applied inside the JVM project: `io.github.khalilou88.jnxplus`. That Gradle plugin registers the `projectDependencyTask` and `projectTask` tasks that the Node plugin invokes via `./gradlew :projectDependencyTask --outputFile=...`.

**Version matters:** v0.4.0 (which is what `@jnxplus/common`'s default `jnxplusGradlePluginVersion` constant points to) does **not** register `projectDependencyTask` — you'll see "Task 'projectDependencyTask' not found in root project" and an empty Nx project list. Pin **v1.0.0 or newer** explicitly in `gradle.properties`.

## File layout to produce

For a project at `apps/<name>/`:

```
apps/<name>/
├── build.gradle.kts          # Kotlin DSL: plugins + deps + toolchain
├── settings.gradle.kts       # pluginManagement + rootProject.name
├── gradle.properties         # version pins + Gradle daemon settings
├── project.json              # Nx targets (build / test / serve / check / clean)
├── gradle/
│   └── wrapper/
│       ├── gradle-wrapper.jar          # vendored (~43KB)
│       └── gradle-wrapper.properties   # distribution URL
├── gradlew                   # wrapper script (unix)
├── gradlew.bat               # wrapper script (windows)
├── src/
│   ├── main/kotlin/<package>/Application.kt
│   └── test/kotlin/<package>/ApplicationTest.kt
└── README.md
```

The wrapper jar and scripts are **vendored** (committed) so new devs only need a JDK installed — the wrapper bootstraps Gradle itself on first run. Source the wrapper jar from gradle/gradle's GitHub repo at a tagged release (e.g. `https://raw.githubusercontent.com/gradle/gradle/v8.14.0/gradle/wrapper/gradle-wrapper.jar`). Source the `gradlew` / `gradlew.bat` scripts from any well-known Gradle project at the matching version (spring-boot's repo at the matching tag is a reliable source — they ship identical wrapper scripts).

### `settings.gradle.kts`

```kotlin
pluginManagement {
    val kotlinVersion: String by settings
    val jnxplusGradlePluginVersion: String by settings
    plugins {
        id("org.jetbrains.kotlin.jvm") version kotlinVersion
        id("io.github.khalilou88.jnxplus") version jnxplusGradlePluginVersion
    }
    repositories {
        mavenCentral()
        gradlePluginPortal()
    }
}

rootProject.name = "<name>"
```

Version constants come from `gradle.properties` (DRY — `build.gradle.kts` doesn't restate them).

### `gradle.properties`

```properties
org.gradle.jvmargs=-Xmx2g -Dfile.encoding=UTF-8
org.gradle.daemon=true
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configuration-cache=false
kotlin.code.style=official
kotlinVersion=2.1.21
jnxplusGradlePluginVersion=1.0.0
```

**`configuration-cache=false` is load-bearing.** The jnxplus Gradle plugin's `projectDependencyTask` reads `Task.project` at execution time, which the configuration cache explicitly rejects. Leaving the configuration cache on produces this error on every `nx show projects`:

```
Invocation of 'Task.project' by task ':projectDependencyTask' at execution time is unsupported.
```

Build cache (`org.gradle.caching=true`) and parallel execution stay on — they're orthogonal to the configuration cache and provide most of the speedup anyway.

### `build.gradle.kts`

```kotlin
plugins {
    kotlin("jvm")
    application
    id("io.github.khalilou88.jnxplus")
}

group = "com.<org>.<name>"
version = "0.1.0"

repositories {
    mavenCentral()
}

kotlin {
    jvmToolchain(21)
}

dependencies {
    testImplementation(kotlin("test"))
    // ML framework choice deferred — drop in KotlinDL / DJL / ONNX Runtime here
}

application {
    mainClass.set("com.<org>.<name>.ApplicationKt")
}

tasks.test {
    useJUnitPlatform()
}
```

Notes:

- `jvmToolchain(21)` makes Gradle auto-download JDK 21 if it isn't on `PATH`. Devs only need *some* JDK installed; the toolchain handles the rest.
- The `kotlin("jvm")` version is omitted here because it's pinned in `settings.gradle.kts` via the `kotlinVersion` property. Keep it in one place.
- Apply `io.github.khalilou88.jnxplus` even when the project has no subprojects — the Node plugin still invokes `projectDependencyTask`.

### `gradle/wrapper/gradle-wrapper.properties`

```properties
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.14.2-bin.zip
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
```

### `project.json`

This is the file that costs the most when omitted. `@jnxplus/nx-gradle` registers only `{root, name, tags}` for the Nx node — despite documentation hinting at `buildTargetName`/`testTargetName`/`serveTargetName` options, those don't auto-generate targets. Without `project.json`, `nx run ml:build` fails with "Cannot find target 'build'".

Write the targets explicitly:

```json
{
  "$schema": "../../node_modules/nx/schemas/project-schema.json",
  "name": "<name>",
  "root": "apps/<name>",
  "sourceRoot": "apps/<name>/src",
  "projectType": "application",
  "tags": ["scope:<name>", "lang:kotlin"],
  "targets": {
    "build": {
      "executor": "nx:run-commands",
      "cache": true,
      "inputs": [
        "{projectRoot}/build.gradle.kts",
        "{projectRoot}/settings.gradle.kts",
        "{projectRoot}/gradle.properties",
        "{projectRoot}/gradle/**",
        "{projectRoot}/src/main/**"
      ],
      "outputs": ["{projectRoot}/build/libs", "{projectRoot}/build/classes"],
      "options": {
        "cwd": "apps/<name>",
        "command": "./gradlew assemble --console=plain"
      }
    },
    "test": {
      "executor": "nx:run-commands",
      "cache": true,
      "inputs": [
        "{projectRoot}/build.gradle.kts",
        "{projectRoot}/settings.gradle.kts",
        "{projectRoot}/gradle.properties",
        "{projectRoot}/src/main/**",
        "{projectRoot}/src/test/**"
      ],
      "outputs": ["{projectRoot}/build/test-results", "{projectRoot}/build/reports/tests"],
      "options": {
        "cwd": "apps/<name>",
        "command": "./gradlew test --console=plain"
      }
    },
    "serve": {
      "executor": "nx:run-commands",
      "cache": false,
      "options": {
        "cwd": "apps/<name>",
        "command": "./gradlew run --console=plain"
      }
    },
    "check": {
      "executor": "nx:run-commands",
      "cache": true,
      "options": { "cwd": "apps/<name>", "command": "./gradlew check --console=plain" }
    },
    "clean": {
      "executor": "nx:run-commands",
      "cache": false,
      "options": { "cwd": "apps/<name>", "command": "./gradlew clean --console=plain" }
    }
  }
}
```

The `inputs` array is what makes caching correct. Without explicit inputs, Nx falls back to "all of `projectRoot`", which includes `build/` and busts the cache after every Gradle run. The list above declares exactly the files that influence the output, so cache hits actually happen.

`serve` and `clean` set `cache: false` because they're long-running / side-effectful and don't produce reusable artifacts.

## Workspace-level wiring

### `nx.json`

Register the plugin once:

```json
{
  "plugins": [
    {
      "plugin": "@jnxplus/nx-gradle",
      "options": {
        "gradleRootDirectory": "apps/<name>"
      }
    }
  ]
}
```

If multiple JVM projects exist under `apps/`, the plugin docs imply you can list multiple entries with different `gradleRootDirectory` values, but each one is its own Gradle root (independent wrappers, independent settings). We haven't needed that yet — keep it simple.

### `package.json` — npm aliases

Mirror the `dev:client` / `dev:api` UX so the JVM project feels at home:

```json
{
  "scripts": {
    "dev:<name>": "nx run <name>:serve",
    "build:<name>": "nx run <name>:build",
    "test:<name>": "nx run <name>:test",
    "<name>:check": "nx run <name>:check",
    "<name>:clean": "nx run <name>:clean",
    "<name>:gradle": "cd apps/<name> && ./gradlew"
  }
}
```

The passthrough alias (`<name>:gradle`) lets devs run ad-hoc Gradle tasks (`npm run ml:gradle -- dependencies`) without remembering the directory.

### `.gitignore`

```gitignore
apps/<name>/.gradle/
apps/<name>/build/
apps/<name>/.kotlin/
**/*.iml
```

## Architectural rule: route through the existing API

The JVM service must be reached **only through the existing TypeScript API layer** (e.g. NestJS in this repo). It does not directly access Supabase, PayPal, iSubscribe, or any other infrastructure that already has a TS client. The API layer makes HTTP calls to the JVM service over loopback / private network.

Why this matters: every auth check, rate-limiter, audit log, and entitlement gate is already implemented in the TS layer. Re-implementing those in Kotlin doubles the surface area for security bugs and creates two sources of truth for things like "is this user allowed to consume tokens." The JVM service stays a pure compute worker — give it bytes, get bytes back.

When the user asks "should the Kotlin service hit the DB directly?" the answer is no, regardless of how convenient it looks.

## IDE caveat (real, not theoretical)

WebStorm cannot enable the Kotlin plugin. It surfaces as:

```
Missing module: com.intellij.modules.java-capable
```

WebStorm ships without the Java module. The Kotlin plugin depends on it. There is no fix — JetBrains intentionally splits their IDEs this way. Options for the JVM dev:

- **IntelliJ IDEA Community** (free) — open `apps/<name>/` as a separate project in IDEA while WebStorm stays the IDE for the TS side. JetBrains Toolbox simplifies running both.
- **IntelliJ IDEA Ultimate** ($) — superset of WebStorm + Java + Kotlin. One IDE for the whole monorepo. Worth it if the company has an All Products Pack.
- **JetBrains Fleet** — polyglot IDE that handles both TS and Kotlin. Reasonable middle ground for solo devs working across both.
- **VS Code + `fwcd.kotlin`** — works for editing and basic LSP features. No refactoring or graph features close to IDEA's level. Fine for a CLI-heavy workflow.

Tell the dev which one fits their workflow rather than insisting on a specific choice.

## Troubleshooting (failure modes I've actually hit)

| Symptom | Cause | Fix |
|---|---|---|
| `Task 'projectDependencyTask' not found in root project` | `io.github.khalilou88.jnxplus` plugin missing or pinned to v0.4.0 | Pin `jnxplusGradlePluginVersion=1.0.0` (or newer) in `gradle.properties` and apply the plugin in `build.gradle.kts` |
| `Configuration cache problems found ... 'Task.project' at execution time is unsupported` | Gradle configuration cache enabled | Set `org.gradle.configuration-cache=false` in `gradle.properties` |
| `nx show projects` lists the JVM project but `nx run <name>:build` says target not found | `@jnxplus/nx-gradle` doesn't auto-generate targets | Add a manual `project.json` with `nx:run-commands` targets (see snippet above) |
| `nx show projects` doesn't list the JVM project at all, error mentions `ENOENT ... nx-gradle-deps.json` | Plugin discovered the Gradle root but the Gradle invocation failed before producing the deps JSON. Usually configuration cache or missing Gradle plugin | Re-read the BUILD FAILED output above the ENOENT; fix the actual Gradle error |
| WebStorm refuses to enable Kotlin plugin | `com.intellij.modules.java-capable` missing | Use IntelliJ IDEA / Fleet / VS Code instead — WebStorm can't be made to support Kotlin |
| `gradle.properties` set, but `kotlinVersion` referenced in `settings.gradle.kts` errors as "unresolved" | Property typo or missing entry | The settings DSL reads via `val kotlinVersion: String by settings` — typos there produce confusing errors. Verify the property name matches exactly |
| Cache busts after every Gradle invocation despite `cache: true` | `project.json` has no `inputs`, so Nx hashes the entire `projectRoot` including `build/` | Add explicit `inputs` listing only source + config files, not build output |

## Verifying the integration

After scaffolding, run these in order — each one validates a layer:

```bash
# 1. Gradle alone works
cd apps/<name> && ./gradlew build

# 2. Nx sees the project
nx show projects
# Expect: ["@warranty/shared","client","api","<name>"]

# 3. Nx targets work
nx run <name>:test
nx run <name>:build

# 4. npm aliases work
npm run test:<name>
npm run build:<name>

# 5. Full monorepo test still passes
npm test
```

If step 2 fails, the plugin isn't loaded or the Gradle plugin is missing. If step 3 fails but step 2 worked, `project.json` is missing or wrong. If step 5 fails on the JVM project but step 4 passed, check that the JVM project's failure isn't masking a real issue — Nx surfaces the first failure, not all of them.

## Anti-patterns

- **Don't run `nx init` in an existing TS-first repo to "add Gradle support."** It re-initializes the entire workspace and adds opinions you don't want.
- **Don't move `settings.gradle.kts` to the workspace root just to make `@nx/gradle` work.** It pollutes the JS side with Gradle artifacts (wrapper, `.gradle/`, `build/`) and makes `nx show projects` flaky.
- **Don't write a `dev.nx.gradle.project-graph` block into the JVM project.** That's `@nx/gradle`'s flavor — if you accidentally ran `nx generate @nx/gradle:init` it'll have injected one; remove it before switching to `@jnxplus/nx-gradle`.
- **Don't trust `jnxplusGradlePluginVersion` defaults from `@jnxplus/common`.** Pin the version explicitly.
- **Don't let the JVM project talk to infra clients directly.** Route through the existing TS API.

## Reference: example commit

In this repo, the scaffold commits are:

- `feat(nx): scaffold Kotlin/JVM ml app under apps/ml` — full file set
- `chore: add npm script aliases for the ml Gradle targets` — npm wiring

Read those before scaffolding the next JVM project so you can mimic the same shape exactly.
