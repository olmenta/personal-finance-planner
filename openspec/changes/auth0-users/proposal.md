## Why

Olmenta runs as a single seeded development user: `current_user` always returns `dev@localhost`, and every visitor would see and change the same budget. That makes it impossible to put a beta online for the user and a few friends. Every query already filters by `user_id`, so what's missing is identity: knowing who is calling, and giving each person their own data.

The architecture already chose Auth0 (project-definition §6.1, §6.2): Universal Login in the webapp, and the Python API validating RS256 JWTs. The beta goes on a shared Hetzner VPS (next change, `deploy-beta`). Login has to come first, so the app is never public without it.

## What Changes

- **New: login with Auth0 in the webapp.**
  - The webapp is the Next.js BFF (`@auth0/nextjs-auth0` v4).
  - Every app page requires a session; without one, the user goes to Auth0's login and comes back.
  - Logout ends the session.
  - The sidebar and Settings show the signed-in person instead of the "Maya Ortiz" placeholder.
- **New: the BFF sends the user's access token to the API.**
  - The token is for the environment's API.
  - The browser still never talks to the API, and never sees the token.
- **New: the API validates the token and knows the user.**
  - It checks the RS256 signature against Auth0's keys, the issuer, the environment's audience and the expiry.
  - It maps the token's subject to a user, creating one on the first visit with a cash account, so onboarding can start.
  - An unauthenticated call gets 401 `unauthenticated`.
- **Environments and Auth0 setup**, in a dedicated EU tenant (`olmenta.eu.auth0.com`):
  - one application per environment: "Olmenta (dev)" (localhost and `dev.olmenta.com` through cloudflared) and "Olmenta (beta)" (`beta.olmenta.com`); prod comes later;
  - one API per environment, with the identifiers `https://api-dev.olmenta.com`, `https://api-beta.olmenta.com` and `https://api.olmenta.com` (identifiers, not public hosts);
  - one database connection, with sign-ups disabled, plus Google.

  With this setup, logging in once works across environments (one tenant session), while a token for one environment's API is rejected by another's. A post-login Action adds the email to the access token.
- **Invite-only beta.** Sign-ups are disabled: the owner creates each user in Auth0, and the person sets their password from the invitation email.
- **New: account linking.** A person can sign in with their password or with Google (other methods later) and always reaches the same data. A post-login Action links a new method to the invited account with the same email, only when that email is verified, and denies methods with no invitation behind them.
- **Local development and tests keep working without Auth0.** A `dev_user` mode, allowed only in the local and test environments, keeps the seeded user for local dev, pytest, the e2e suite and the dev MCP server. The API refuses to start in `dev_user` mode in dev, beta or prod.
- **`GET /me`.** The signed-in user's email and locale.
- **New: Home before setup.** A new user (only the empty cash account) gets a new home status, `not_set_up`. Instead of a month analysis of zeros, Home invites the setup chat, and the coach doesn't analyze.
- **Docs.**
  - The user guide gets "Signing in".
  - A developer guide covers the Auth0 setup: applications, APIs, the connection, the Action, and the environment variables per environment.

## Capabilities

### New Capabilities

- `authentication`:
  - webapp sessions;
  - the BFF's token forwarding;
  - API token validation;
  - user provisioning;
  - invite-only access;
  - account linking across login methods;
  - the local/test `dev_user` mode and its refusal outside those environments;
  - `GET /me`;
  - the signed-in identity in the shell.

### Modified Capabilities

- `bff-proxy`: route handlers forward the session's access token and turn a missing session into 401 `unauthenticated`.
- `home`: the `not_set_up` status, before any budget or money exists.
- `coach-conversation`: the snapshot before setup invites the setup chat.

## Impact

- **Backend:**
  - JWT validation (`pyjwt[crypto]`);
  - `deps.current_user` rewritten (Auth0 or `dev_user`, by setting);
  - user provisioning;
  - `GET /me`;
  - settings (`app_env`, `auth_mode`, `auth0_domain`, `auth0_audience`);
  - tests with a locally signed token and a fake key set.

  No migration: `users.auth0_sub` already exists.
- **Webapp:**
  - `@auth0/nextjs-auth0`, `lib/auth0.ts` and `middleware.ts`;
  - `proxyFetch` attaching the token;
  - the shell's user card, Settings and logout;
  - e2e in auth-disabled mode.
- **Docs:** `docs/user-guide.md` ("Signing in") and `docs/auth0-setup.md`.
- **Auth0 (documented; created with the Auth0 MCP where it can, the rest by hand):** two applications, three APIs, the database and Google connections, one Machine-to-Machine application for the Action, and one post-login Action (linking plus the email claim), in the dedicated tenant.
- **Unaffected:** every domain endpoint and its logic (already scoped by `user_id`), the coach, imports, and the MCP server (local `dev_user`).
