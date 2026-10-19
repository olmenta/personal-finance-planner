## Context

Today `deps.current_user` returns the seeded `dev@localhost` user for every request. Every domain query already filters by `user_id`, and `users.auth0_sub` already exists. The webapp is the only public surface (the BFF): route handlers call `proxyFetch(path)` with no credentials, and the API sits on an internal network.

The architecture chose Auth0 (Universal Login, RS256 JWTs validated by the API). Olmenta has its own EU tenant, `olmenta.eu.auth0.com`. A tenant shared with another project was ruled out: Universal Login, emails and branding are per tenant (people would see the other product's name and logo), and that tenant runs post-login Actions that link accounts across all its apps. Environments:

- **local:** a developer's machine (`localhost`), optionally exposed as `dev.olmenta.com` through cloudflared;
- **test:** pytest and the e2e suite;
- **beta:** `beta.olmenta.com` on the Hetzner VPS (`deploy-beta`);
- **prod:** later.

## Goals / Non-Goals

**Goals:**

- Each person signs in and sees only their own data; the app is never public without login.
- One login works across environments, while tokens are bound to their environment's API.
- Local development, pytest, e2e and the dev MCP server keep working without Auth0.
- An invite-only beta.

**Non-Goals:**

- Billing and subscription gating (Stripe), for the launch.
- Account export and deletion (`beta-readiness`).
- The environment banner (`deploy-beta`).
- Apple and passwordless logins (later: new connections, linked the same way as Google, D6).
- A custom Auth0 domain (`auth.olmenta.com`, possible now that the tenant is dedicated; before prod).
- Roles and permissions.
- Terraform for Auth0 (manual setup, documented, for the beta).

## Decisions

### D1. Auth0 objects in the dedicated tenant

| Object | Dev | Beta | Prod (later) |
|---|---|---|---|
| Application (Regular Web App) | "Olmenta (dev)" | "Olmenta (beta)" | "Olmenta (prod)" |
| Callback / logout URLs | `http://localhost:3000`, `https://dev.olmenta.com` (+ `/auth/callback`) | `https://beta.olmenta.com` (+ `/auth/callback`) | `https://app.olmenta.com` |
| API identifier (audience) | `https://api-dev.olmenta.com` | `https://api-beta.olmenta.com` | `https://api.olmenta.com` |

All of them use one database connection, "olmenta-users", with sign-ups disabled, plus the Google connection (D6). The tenant's default connections and the "Default App" are disabled.

- **APIs:** RS256, allow offline access (refresh tokens), token lifetime 1 h.
- **API identifiers are not hosts.** None of them is a public host: the API stays internal, behind the BFF (bff-proxy). `api.olmenta.com` becomes a real host only if a mobile client needs it.
- **SSO without shared audiences:** the tenant session gives single sign-on across environments. Each environment's API only accepts its own audience, so a beta token is useless against prod.

**Post-login Action, email claim** (part of "Olmenta login", D6): when the requested audience is one of the three identifiers, add `https://olmenta.com/email` (and `email_verified`) to the access token. Access tokens don't carry the email by default, and the API needs it for provisioning.

- **Alternative:** have the BFF send the email in a header. Rejected: identity would rest on a header instead of the signed token.

### D2. Webapp: `@auth0/nextjs-auth0` v4

- **`src/lib/auth0.ts`:** `new Auth0Client({ authorizationParameters: { audience: process.env.AUTH0_AUDIENCE, scope: "openid profile email offline_access" } })`. Environment variables: `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `AUTH0_SECRET`, `APP_BASE_URL` and `AUTH0_AUDIENCE`.
- **`src/middleware.ts`:**
  - `auth0.middleware(request)` handles `/auth/*`;
  - for everything else except static assets, no session means a redirect to `/auth/login?returnTo=<path>` for pages and a 401 JSON for `/api/*`.
- **`proxyFetch`** (server-only) calls `auth0.getAccessToken()` and sets `Authorization: Bearer`. An `AccessTokenError` (session gone, refresh failed) becomes 401 `unauthenticated`.
- **Client side:** `request()` in `lib/api.ts`, on a 401 `unauthenticated`, does `window.location.assign("/auth/login?returnTo=" + location.pathname)`, so a session that ends mid-use leads to login instead of an error panel.
- **Shell:** the user card and Settings read the session user (`auth0.getSession()` in a server component, passed down) for name, email and picture; "Log out" links to `/auth/logout`. The placeholder "Maya Ortiz" and the "Pro" badge go away.
- **Auth disabled:** when `AUTH0_DOMAIN` is unset and `APP_ENV` is `local` or `test`, the middleware is a pass-through and `proxyFetch` sends no token. The shell shows "Development user" with no logout. The e2e suite runs this way.

### D3. API: token validation and user resolution

- **New settings:**
  - `app_env` (`local` | `test` | `dev` | `beta` | `prod`, default `local`);
  - `auth_mode` (`dev_user` | `auth0`, default `dev_user`);
  - `auth0_domain`, `auth0_audience`.

  On startup, `auth_mode == "dev_user"` with `app_env` in {dev, beta, prod} raises a configuration error. So does `auth0` without a domain or audience.
- **`app/auth.py`:**
  - `jwt.PyJWKClient(f"https://{domain}/.well-known/jwks.json", cache_keys=True)` is held per process;
  - `verify(token)` runs `jwt.decode(token, key, algorithms=["RS256"], audience=…, issuer=f"https://{domain}/", options={"require": ["exp", "sub", "iss", "aud"]})`;
  - any error becomes `Unauthenticated`;
  - an unknown key id refetches the JWKS once.
- **`deps.current_user`:**
  - in `dev_user` mode it is the seeded user, as today;
  - in `auth0` mode it reads `Authorization`, verifies, and calls `users.resolve(db, sub, email)`: find by `auth0_sub`, else link by case-insensitive email with a null `auth0_sub`, else create the user and its "Efectivo" cash account (the same as the seed, without the category tree; onboarding builds it).
  - Creation runs in a savepoint and retries the lookup on a unique conflict, because two first requests can arrive in parallel (Home and the conversation load together).
- **401s:** `{code: "unauthenticated"}` with `WWW-Authenticate: Bearer`.
- **Logging:** never the token or the email; Sentry sees only the user id.

`GET /me` returns `{email, locale, created_at}`.

### D4. Invitations

The owner creates the user in Auth0 → Users (connection "olmenta-users") and sends a change-password ticket, which is the invitation email. The invitee can then use their password or "Continue with Google" with the same address (D6). Documented in `docs/auth0-setup.md` with screenshots-free steps. The API also links pre-existing users by email (D3), so a user can be created in Olmenta's database ahead of time if ever needed.

### D5. Tests

- **pytest:** `dev_user` by default (conftest sets `AUTH_MODE=dev_user`, `APP_ENV=test`). New `test_auth.py`:
  - generates an RSA key and monkeypatches the JWKS client to return it;
  - signs tokens to cover valid, wrong audience, wrong issuer, expired, bad signature, missing token, provisioning on first visit, linking by email, and the parallel-first-request race;
  - checks isolation between two users (transactions, budget, coach conversation), and the startup refusal of `dev_user` in beta.
- **e2e:** auth disabled (`APP_ENV=test` without Auth0 variables in the Playwright web server env). Real login is covered manually on `dev.olmenta.com` (a checklist in the setup doc).
- **The dev MCP server:** unchanged, against a local API in `dev_user` mode.

### D6. Account linking (one person, several login methods)

The same person must reach the same data whether they use their password or Google. Auth0 treats each method as a separate user, so a post-login Action links them into one, with the invited "olmenta-users" user as primary.

**The Action "Olmenta login"** (post-login, one Action so the order is explicit) does two things:

1. **Linking and the invitation gate**, only when the connection isn't "olmenta-users":
   - the user already holds an "olmenta-users" identity → continue (already linked; Auth0 hands the Action the primary user);
   - the method's email isn't verified → deny;
   - look up users by that email through the Management API, keep those with an "olmenta-users" identity: exactly one → `api.authentication.setPrimaryUser(primary)` and link the current identity to it (`POST /users/{primary}/identities` with `provider` and `user_id`); none → deny ("Olmenta is invitation-only"); more than one → deny (needs the owner).
2. **The email claim** (D1), for Olmenta's audiences.

- **Management API client:** a Machine-to-Machine application "Olmenta login Action" with only `read:users` and `update:users`. Its domain, client id and secret are Action secrets. The Action caches its token in `api.cache`, and calls the API with `fetch` (no npm dependency).
- **Google connection:** with Olmenta's own Google OAuth client (Auth0's development keys aren't for real users), scopes `email` and `profile`, enabled for the Olmenta applications. Universal Login shows "Continue with Google" by itself; the webapp doesn't change.
- **The API doesn't change:** after linking, the token's `sub` is the primary user's id, which is what `users.resolve` already knows. If Google is the first method someone uses, the first token already carries the primary id.
- **Alternatives:**
  - Auth0's "suggested linking" (the user proves both accounts in a page of ours). Rejected for the beta: an extra screen and flow for a risk sign-ups-disabled already removes.
  - Opening sign-ups for Google and linking afterwards. Rejected: it breaks invite-only.

### D7. The dev tunnel

`dev.olmenta.com` is a public hostname on a Cloudflare Tunnel whose connector runs on the developer's Mac, pointing at `localhost:3000`. Only the webapp goes through it; the API stays local.

- **Never expose the development user.** With auth disabled, everyone is `dev@localhost`, so the middleware answers 403 to any `Host` or `X-Forwarded-Host` other than `localhost`, `127.0.0.1` or `[::1]`. A tunnel left running with Auth0 unset shows a 403, not the owner's budget.
- **Two origins, one server.** `APP_BASE_URL` takes a comma-separated list. For each request, the SDK infers the origin from the forwarded headers and accepts it only if it's in the list, so localhost and the tunnel work together.
- **`allowedDevOrigins`** lets the dev server's assets and hot reload work from the tunnel's origin.
- **Cloudflare Access** in front is recommended, not required: Auth0 already guards the app.
- Documented in `docs/dev-tunnel.md`.

### D8. Before setup: nothing to analyze

A provisioned user has the empty cash account, so Home used to see "an account" and analyze a month of zeros ("I've updated your month. You have 0,00 € in your accounts"). A new home status, `not_set_up`, comes first: no categories and no transactions.

- **Why that test:** the onboarding and the starter template both create categories, and recording money (an opening balance, a transaction) means the person is using the app their own way. The test doesn't depend on a completed onboarding session, because the template path doesn't complete one.
- **In that state:** no reasons, no coach suggestions (detection is skipped), and the snapshot is a single invitation to the setup chat. The onboarding nudge hides so it isn't said twice. The coach's context says not to analyze and to point to the setup chat.
- **The cash account stays:** onboarding reuses accounts by name, and it lets someone who skips the onboarding record cash right away.

## Risks / Trade-offs

- **[Google lets anyone create an Auth0 user]** → Social connections can't disable sign-ups, so the Action denies any Google login without an invitation; those Auth0 users never reach Olmenta (no token is issued) and can be deleted from the dashboard.
- **[Automatic linking hands an account to whoever controls the email]** → Only when the Google email is verified, and only onto an account the owner created. Auth0's guidance prefers proving both accounts; with sign-ups disabled the invited side can't be planted by an attacker, so the extra step isn't worth it for the beta.
- **[The Action can't reach the Management API]** → The login is denied with a clear message (never let in unlinked), and it shows in the tenant logs.
- **[JWKS fetch failure at boot or on rotation]** → Keys are cached, refetched on an unknown kid, and failures return 503 `auth_unavailable` (not 401) so it's visible in Sentry.
- **[Session expiry while typing in the composer]** → The draft is already kept in localStorage; after re-login, the composer restores it.
- **[e2e doesn't exercise real login]** → The manual checklist on dev; the backend validation is fully unit-tested with real RS256 tokens.

## Migration Plan

No schema change. Local and test keep `dev_user`. The beta is created with `AUTH_MODE=auth0`, `APP_ENV=beta` and the beta audience (`deploy-beta`). The owner's local data stays in the dev database, and the beta starts empty.

## Open Questions

None.
