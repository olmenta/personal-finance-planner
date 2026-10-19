# authentication Specification

## Purpose
TBD - created by archiving change auth0-users. Update Purpose after archive.
## Requirements
### Requirement: Sessions in the webapp

The webapp SHALL authenticate people with Auth0 Universal Login through the Next.js SDK, which mounts `/auth/login`, `/auth/callback` and `/auth/logout`. Every app page and every BFF route SHALL require a session, except `/auth/*` and static assets. A page request without a session SHALL redirect to `/auth/login` and come back to the requested page after login. Logout SHALL end the webapp session and the Auth0 session. The session SHALL ask Auth0 for an access token for the environment's API (`AUTH0_AUDIENCE`), with `offline_access`, so the SDK refreshes it without asking the person to log in again.

#### Scenario: Not signed in

- **WHEN** someone opens `/budgets` without a session
- **THEN** they are sent to Auth0's login and, after signing in, land on `/budgets`

#### Scenario: Logout

- **WHEN** the person chooses "Log out"
- **THEN** their session ends, and opening any page asks them to sign in again

### Requirement: The BFF forwards the user's access token

Every BFF route handler SHALL obtain the session's access token for the environment's API and send it to the backend as `Authorization: Bearer <token>`. A BFF request without a session SHALL return 401 `{code: "unauthenticated"}` without calling the backend. The token SHALL never reach the browser.

#### Scenario: Token attached

- **WHEN** a signed-in person loads Home
- **THEN** the backend receives each request with a Bearer token whose audience is the environment's API

#### Scenario: Session expired during use

- **WHEN** the session has ended and the browser calls `/api/home`
- **THEN** the BFF answers 401 `unauthenticated`, and the webapp sends the person to sign in

### Requirement: The API validates tokens and resolves the user

In `auth0` mode, the API SHALL accept a request only with a valid Bearer token:

- an RS256 signature by a key from the tenant's JWKS (cached, refreshed on an unknown key id);
- issuer `https://<AUTH0_DOMAIN>/`;
- an audience equal to the environment's `AUTH0_AUDIENCE`;
- not expired.

Otherwise it SHALL return 401 `{code: "unauthenticated"}`.

The token's `sub` SHALL identify the user:

- an existing user with that `auth0_sub` is used;
- otherwise a user whose email (from the token's email claim) matches and has no `auth0_sub` gets linked;
- otherwise a new user is created with that email, the default locale `es` and a cash account "Efectivo", so the person starts at onboarding.

Every domain endpoint SHALL keep using only that user's data.

#### Scenario: A token for another environment

- **WHEN** a token issued for `https://api-beta.olmenta.com` reaches the dev API (audience `https://api-dev.olmenta.com`)
- **THEN** the API answers 401 `unauthenticated`

#### Scenario: First visit

- **WHEN** a valid token arrives for a `sub` the API has never seen, with email `ana@example.com`
- **THEN** a user with that email and a cash account "Efectivo" is created, and Home shows the onboarding invitation

#### Scenario: Two people, two budgets

- **WHEN** Ana and Luis each record an expense
- **THEN** each one's transactions, budget and coach conversation show only their own data

### Requirement: Invite-only beta

Olmenta SHALL use a dedicated Auth0 tenant. Its database connection "olmenta-users" SHALL have sign-ups disabled. People SHALL get access when the owner creates their user in that connection and sends a change-password ticket that marks the email as verified; they set their password from the invitation email. Other login methods (Google first) SHALL only let in someone who already has an invited account with the same verified email (see "Account linking"). The setup SHALL be documented step by step.

#### Scenario: No self sign-up

- **WHEN** someone without an invitation opens the beta's login
- **THEN** there's no sign-up option, and they can't create an account

#### Scenario: Google without an invitation

- **WHEN** someone without an invitation chooses "Continue with Google"
- **THEN** Auth0 denies the login with a message that Olmenta is invitation-only, and no Olmenta user is created

### Requirement: Account linking by verified email

A post-login Action SHALL link every login method of a person into one Auth0 user, so the same person always reaches the same Olmenta data whichever method they use. When someone signs in with a method other than "olmenta-users" (Google first; Apple or passwordless later):

- if their Auth0 user already holds an "olmenta-users" identity, the login continues;
- otherwise, if the method's email is verified and exactly one "olmenta-users" user has that same email, the Action makes that invited user the primary user, links the new identity to it as secondary, and the login continues as the primary user;
- otherwise the login is denied (unverified email, or no invitation).

Linking SHALL never happen when the new method's email is unverified. The invited side is trusted because only the owner can create "olmenta-users" users (sign-ups are disabled). The access token's `sub` SHALL be the primary user's id, so the API needs no change. The Action, the Management API client it uses (only `read:users` and `update:users`) and the manual steps SHALL be documented in `docs/auth0-setup.md`.

#### Scenario: Password first, Google later

- **WHEN** Ana, invited as `ana@gmail.com`, has been signing in with her password, and then chooses "Continue with Google" with the same address
- **THEN** her Google identity is linked to her invited user, the token's `sub` is unchanged, and she sees her own budget

#### Scenario: Google straight away

- **WHEN** Luis is invited as `luis@gmail.com` and signs in with Google before ever setting a password
- **THEN** the Google identity is linked to his invited user, and his first visit creates his Olmenta user

#### Scenario: Unverified email

- **WHEN** a login method reports the invited address but not as verified
- **THEN** nothing is linked and the login is denied

### Requirement: Development-user mode only in local and test

The API SHALL support `auth_mode = dev_user`, which resolves every request to the seeded development user without a token, for local development, the pytest suite, the e2e suite and the dev MCP server. The API SHALL refuse to start when `auth_mode` is `dev_user` and `app_env` is `dev`, `beta` or `prod`. The webapp SHALL skip sessions only when Auth0 isn't configured and `APP_ENV` is `local` or `test`. In that mode it SHALL answer only requests addressed to `localhost`, `127.0.0.1` or `[::1]`, and refuse any other host with 403, so a tunnel can't expose the development user.

#### Scenario: Misconfigured beta

- **WHEN** the API starts with `APP_ENV=beta` and `AUTH_MODE=dev_user`
- **THEN** it exits with an error naming the setting, and serves nothing

#### Scenario: Tunnel without Auth0

- **WHEN** the webapp runs without Auth0 variables and a request arrives for `dev.olmenta.com`
- **THEN** it answers 403, and no page or data is served

#### Scenario: Local without Auth0

- **WHEN** a developer runs the webapp and API locally without Auth0 variables
- **THEN** the app works as the seeded development user, as before

### Requirement: Who is signed in

`GET /me` SHALL return the signed-in user's `email`, `locale` and `created_at`. The shell's user card and Settings SHALL show the person's name (or email) and avatar from the session instead of a placeholder, with a "Log out" action. In `dev_user` mode they show the development user.

#### Scenario: The real person in the sidebar

- **WHEN** Ana is signed in
- **THEN** the sidebar shows Ana's name and email, and "Log out"

