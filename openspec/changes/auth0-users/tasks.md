## 1. API: settings and token validation

- [x] 1.1 Settings: `app_env`, `auth_mode`, `auth0_domain`, `auth0_audience`, and a startup check (`dev_user` refused in dev/beta/prod; `auth0` needs domain and audience) (D3). Add `pyjwt[crypto]` with `uv add`.
- [x] 1.2 `app/auth.py`: the cached JWKS client and `verify(token)` (RS256, issuer, audience, required claims, refetch on unknown kid). Errors map to 401 `unauthenticated` or 503 `auth_unavailable`.
- [x] 1.3 `services/users.py::resolve(db, sub, email)`: by `auth0_sub`, else link by email, else create with locale `es` and a cash account "Efectivo"; savepoint plus retry on a unique conflict.
- [x] 1.4 `deps.current_user`: `dev_user` or `auth0`, with `WWW-Authenticate: Bearer` on 401. `GET /me`.
- [x] 1.5 `.env.example`: the new variables, documented per environment. conftest: `AUTH_MODE=dev_user`, `APP_ENV=test`.
- [x] 1.6 `tests/test_auth.py`:
  - a locally signed RS256 token covering valid, wrong audience, wrong issuer, expired, bad signature and missing token;
  - provisioning on first visit (user and cash account);
  - linking by email;
  - parallel first requests create one user;
  - two users isolated (transactions, budget, coach conversation);
  - `dev_user` refused with `APP_ENV=beta`;
  - `GET /me`.

## 2. Webapp: sessions and the BFF

- [x] 2.1 `volta run npm install @auth0/nextjs-auth0`. `src/lib/auth0.ts` (audience, scope with `offline_access`) and the auth-disabled rule (no `AUTH0_DOMAIN` and `APP_ENV` local/test) (D2).
- [x] 2.2 `src/middleware.ts`: SDK routes; pages without a session redirect to `/auth/login?returnTo=`; `/api/*` without a session gets 401; static assets and `/auth/*` excluded.
- [x] 2.3 `lib/server/backend.ts::proxyFetch`: attach `Authorization: Bearer` from `getAccessToken()`; `AccessTokenError` becomes 401 `unauthenticated`.
- [x] 2.4 `lib/api.ts`: on 401 `unauthenticated`, go to `/auth/login?returnTo=<current path>`.
- [x] 2.5 Shell: the session user (name, email, picture) in the sidebar user card and in Settings, with "Log out" to `/auth/logout`; "Development user" when auth is disabled. Remove the "Maya Ortiz" placeholder and the "Pro" badge.
- [x] 2.6 `webapp/.env.example`: the Auth0 variables and `APP_ENV`.
- [x] 2.7 Dev tunnel support (D7):
  - with auth disabled, the middleware answers 403 to any host other than `localhost`/`127.0.0.1`;
  - `allowedDevOrigins: ["dev.olmenta.com"]` in `next.config.ts`;
  - `APP_BASE_URL` documented as a comma-separated list (`http://localhost:3000,https://dev.olmenta.com`).

- [x] 2.8 Before setup (D8): home status `not_set_up` (no categories and no transactions) with no reasons and no suggestions; the snapshot invites the setup chat instead of the month analysis, and the onboarding nudge hides; the coach context says not to analyze. Tests in `test_home.py`; e2e `setup.spec.ts` with `resetDb({ fresh: true })`.
- [x] 2.9 Onboarding layout, found in the first real sign-in: during the interview the page is the viewport's height and only the message list scrolls, so the newest message and the answer options stay in view; the review screen opens at its top. e2e `onboarding-layout.spec.ts` (interview API answered in the browser).

## 3. Auth0 setup (documented)

- [x] 3.1 `docs/auth0-setup.md`:
  - the two applications with their URLs;
  - the three APIs (identifiers, RS256, offline access);
  - the "olmenta-users" connection (sign-ups disabled);
  - the post-login Action code that adds `https://olmenta.com/email`;
  - inviting a user (create, then a change-password ticket);
  - the environment variables per environment;
  - a manual login checklist on `dev.olmenta.com` (login, return to page, logout, a token for the wrong audience rejected, users isolated).

- [x] 3.2 Dedicated tenant: `docs/auth0-setup.md`, the design and the proposal name `olmenta.eu.auth0.com` and drop the shared-tenant caveats.
- [x] 3.3 Account linking (D6) in `docs/auth0-setup.md`:
  - the Google connection with Olmenta's own Google OAuth client;
  - the Machine-to-Machine application "Olmenta login Action" (`read:users`, `update:users`) and the Action secrets;
  - the "Olmenta login" Action code (invitation gate, linking onto the "olmenta-users" user, email claim) replacing the claim-only Action;
  - checklist items: password then Google, Google first, Google without an invitation.
- [x] 3.4 `docs/user-guide.md` "Signing in": "Continue with Google" with the invited address.
- [x] 3.5 `docs/dev-tunnel.md`:
  - the public hostname `dev.olmenta.com` → `localhost:3000` on the Cloudflare tunnel, with optional Cloudflare Access;
  - the local `.env` for real login;
  - what changes while it's on (new user, the dev MCP server needs `dev_user`);
  - turning it off;
  - troubleshooting.

  Linked from `docs/README.md`, along with `auth0-setup.md`.

## 4. Docs

- [x] 4.1 `docs/user-guide.md`: "Signing in" (the invitation email, setting your password, staying signed in, logging out). Check `docs/debt-guide.md`: no change expected.
- [x] 4.2 Check that the deltas match the implementation: `authentication` added, `bff-proxy` modified.

## 5. Verification

- [x] 5.1 `uv run pytest` green in `backend/`.
- [x] 5.2 Type check, lint and build green in `webapp/` (separate dist dir).
- [x] 5.3 e2e green in auth-disabled mode (`volta run npm run e2e`). Add to `e2e/home.spec.ts`: the sidebar shows "Development user" and no Maya placeholder.
- [x] 5.4 Auth0 objects in `olmenta.eu.auth0.com`: the dev and beta APIs, the dev and beta applications, the Machine-to-Machine application and its grant, and the Action, through the Auth0 MCP; the connections, the Action binding and the Google OAuth client by hand.
- [x] 5.5 Manual: the user adds the `dev.olmenta.com` public hostname to the tunnel (`docs/dev-tunnel.md`).
- [ ] 5.6 Manual: the user runs the login checklist locally (`localhost:3000`, or `dev.olmenta.com` through cloudflared), including the linking cases.
