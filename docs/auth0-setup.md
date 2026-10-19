# Auth0 setup

How Olmenta signs people in (openspec change `auth0-users`, spec `authentication`). Olmenta has its own EU tenant, **`olmenta.eu.auth0.com`**, so the login page, the emails and the branding are Olmenta's alone.

## What gets created

| Object | Dev | Beta | Prod (later) |
|---|---|---|---|
| Application (Regular Web Application) | Olmenta (dev) | Olmenta (beta) | Olmenta (prod) |
| App URLs | `http://localhost:3000`, `https://dev.olmenta.com` | `https://beta.olmenta.com` | `https://app.olmenta.com` |
| API identifier (audience) | `https://api-dev.olmenta.com` | `https://api-beta.olmenta.com` | `https://api.olmenta.com` |

Shared by every environment:

- **Connections:** the database connection **olmenta-users** (sign-ups disabled) and **Google**.
- **The post-login Action "Olmenta login":**
  - lets a Google login in only when an invited user has the same email;
  - links it to that user;
  - adds the email to the access token.
- **A Machine-to-Machine application, "Olmenta login Action":** the Action uses it to look up and link users.

How the pieces fit:

- **API identifiers are names, not hosts.** They don't need DNS records: the API is never public, and the browser only talks to the webapp.
- **One login for every environment:** the tenant session gives single sign-on, so signing in once works for dev, beta and prod. Each API only accepts tokens for its own identifier, so a beta token is rejected by prod.
- **One person, one user, several login methods:** whether someone uses their password or Google, the Action makes sure they end up as the same Auth0 user, so the token's `sub` (and their Olmenta data) is always the same.

## 1. Tenant clean-up

- Applications → **Default App**: delete it, or leave it with no connections.
- Authentication → Database → **Username-Password-Authentication**: delete it once `olmenta-users` exists. Social → turn off any default Google connection that uses Auth0's development keys (step 2 replaces it).

## 2. The connections

**olmenta-users** (Authentication → Database → Create DB Connection):

1. Name it `olmenta-users`.
2. **User identifiers:** only **Email Address**, not Username or Phone. People sign in with their email; the Action links accounts by that email; the API provisions the Olmenta user from it.
3. **Authentication methods:** only **Password**.
   - Passkey and email OTP are off for the beta.
   - Passkeys can be added later without touching anything else: they need a fallback method, and Password stays as that fallback.
4. Turn on **Disable Sign Ups**. The beta is invitation-only.
5. Leave **Promote Connection to Domain Level** off, then **Create**.
6. After creating it:
   - **Attributes → Email → Configure:** email required and unique. For the verification method, keep **Link**: the invitation link verifies the address.
   - **Authentication Methods → Password:** keep the default policy (**Good**, at least 8 characters). Turn on **Password Dictionary** and **Disallow Personal Data**.
7. Applications tab: enable it for the Olmenta applications.

**Google** (Authentication → Social → Google / Gmail):

1. In Google Cloud Console, select (or create) the project "Olmenta".
2. **Create the consent screen first.** Google won't create an OAuth client without one; if you go to Credentials first, it sends you here. Open APIs & Services → OAuth consent screen (it opens the **Google Auth Platform**) → **Get started**, and fill in the wizard:
   1. **App information:** app name "Olmenta", user support email.
   2. **Audience:** **External**.
   3. **Contact information:** your email.
   4. **Finish:** accept the policy, then **Create**.

   Then, in Google Auth Platform:
   - **Data access:** the default `openid`, `email` and `profile` scopes are all it needs. Don't add others.
   - **Audience → Publish app** (In production). In "Testing", only the test users you list can sign in. With only these non-sensitive scopes, Google doesn't ask for a verification review.
3. **Create the OAuth client:** APIs & Services → Credentials → **Create credentials → OAuth client ID** (or Google Auth Platform → Clients → **Create client**), application type **Web application**, name `Olmenta Auth0`:
   - authorized JavaScript origin `https://olmenta.eu.auth0.com`;
   - authorized redirect URI `https://olmenta.eu.auth0.com/login/callback`;
   - if a custom domain such as `auth.olmenta.com` is added later, add its origin and callback too.
4. In Auth0, paste that client ID and secret. **Don't use Auth0's development keys**: they're for trying things out, not for real users.
5. Attributes: keep `email` and `profile`. Under Permissions, leave everything off, including **Offline Access**: it asks Google for a refresh token to call Google APIs for the user, and Olmenta calls none. Staying signed in comes from Auth0's own refresh tokens: the API's Allow Offline Access setting (step 3) and the `offline_access` scope the webapp requests.
6. Applications tab: enable it for the Olmenta applications.

Google sign-ups can't be turned off in Auth0. That's why the Action (step 5) denies any Google login that doesn't match an invitation.

## 3. The APIs

Applications → APIs → Create API, once per environment:

- **Name:** `Olmenta API (dev)` / `(beta)` / `(prod)`.
- **Identifier:** see the table above. It can't be changed later.
- **Signing algorithm:** RS256.
- **Settings:** turn on **Allow Offline Access** (refresh tokens, so people stay signed in), and set the token expiration to 3600 seconds.

## 4. The applications

Applications → Create Application → **Regular Web Applications**, once per environment:

| Setting | Dev | Beta |
|---|---|---|
| Allowed Callback URLs | `http://localhost:3000/auth/callback, https://dev.olmenta.com/auth/callback` | `https://beta.olmenta.com/auth/callback` |
| Allowed Logout URLs | `http://localhost:3000, https://dev.olmenta.com` | `https://beta.olmenta.com` |
| Allowed Web Origins | `http://localhost:3000, https://dev.olmenta.com` | `https://beta.olmenta.com` |

- **Refresh tokens:** in Advanced Settings → Grant Types, keep **Authorization Code** and **Refresh Token**. Under Refresh Token Rotation, turn rotation on.
- **Connections tab:** `olmenta-users` and `google-oauth2`, nothing else.

**The Machine-to-Machine application for the Action:**

1. Applications → Create Application → **Machine to Machine**, name `Olmenta login Action`.
2. Authorize it for the **Auth0 Management API** with only the `read:users` and `update:users` permissions.
3. Its domain, client ID and client secret become the Action's secrets (step 5).

## 5. The post-login Action "Olmenta login"

Actions → Library → Create Action → Build from scratch, **Login / Post Login**, runtime Node 22, name `Olmenta login`.

Secrets (the key icon):

| Secret | Value |
|---|---|
| `DOMAIN` | `olmenta.eu.auth0.com` |
| `CLIENT_ID` | the client ID of "Olmenta login Action" |
| `CLIENT_SECRET` | its client secret |

```js
/**
 * Olmenta login (post-login).
 *
 * 1. Invitation gate and account linking: a login method other than the
 *    "olmenta-users" database connection (Google today) gets in only when an
 *    invited "olmenta-users" user has the same email. That method's email
 *    must be verified. The Action links it to the invited user, which stays
 *    the primary user, so the token's `sub` never changes. Everything else
 *    is denied.
 * 2. Adds the email to access tokens for Olmenta's APIs.
 */
const DATABASE = "olmenta-users";
const AUDIENCES = [
  "https://api-dev.olmenta.com",
  "https://api-beta.olmenta.com",
  "https://api.olmenta.com",
];
const NOT_INVITED =
  "Olmenta is invitation-only. Sign in with the email address your invitation was sent to.";
const TOKEN_CACHE_KEY = "management-token";

async function managementToken(event, api) {
  const cached = api.cache.get(TOKEN_CACHE_KEY);
  if (cached && cached.value) return cached.value;
  const response = await fetch(`https://${event.secrets.DOMAIN}/oauth/token`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      grant_type: "client_credentials",
      client_id: event.secrets.CLIENT_ID,
      client_secret: event.secrets.CLIENT_SECRET,
      audience: `https://${event.secrets.DOMAIN}/api/v2/`,
    }),
  });
  if (!response.ok) throw new Error(`management token: ${response.status}`);
  const { access_token, expires_in } = await response.json();
  // Cache lifetimes are in milliseconds, at most 24 h.
  const ttl = Math.min(expires_in * 800, 23 * 3600 * 1000);
  api.cache.set(TOKEN_CACHE_KEY, access_token, { ttl });
  return access_token;
}

async function management(event, api, path, init = {}) {
  const token = await managementToken(event, api);
  const response = await fetch(`https://${event.secrets.DOMAIN}/api/v2${path}`, {
    ...init,
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
  });
  if (!response.ok) throw new Error(`management ${path}: ${response.status}`);
  return response.json();
}

async function linkToInvitedUser(event, api) {
  const user = event.user;
  if (user.identities.some((identity) => identity.connection === DATABASE)) return true;
  if (!user.email || !user.email_verified) return false;

  const sameEmail = await management(
    event,
    api,
    `/users-by-email?email=${encodeURIComponent(user.email.toLowerCase())}`,
  );
  const invited = sameEmail.filter(
    (candidate) =>
      candidate.user_id !== user.user_id &&
      candidate.identities.some((identity) => identity.connection === DATABASE),
  );
  if (invited.length !== 1) return false;

  const primary = invited[0];
  const secondary = user.identities[0];
  // Switch to the primary user before linking, or the login can't be built.
  api.authentication.setPrimaryUser(primary.user_id);
  await management(event, api, `/users/${encodeURIComponent(primary.user_id)}/identities`, {
    method: "POST",
    body: JSON.stringify({ provider: secondary.provider, user_id: secondary.user_id }),
  });
  return true;
}

exports.onExecutePostLogin = async (event, api) => {
  if (event.connection.name !== DATABASE) {
    let allowed = false;
    try {
      allowed = await linkToInvitedUser(event, api);
    } catch (error) {
      console.error("account linking failed:", error.message);
      return api.access.deny("We couldn't sign you in right now. Try again in a few minutes.");
    }
    if (!allowed) return api.access.deny(NOT_INVITED);
  }

  const audience = event.resource_server && event.resource_server.identifier;
  if (!AUDIENCES.includes(audience)) return;
  api.accessToken.setCustomClaim("https://olmenta.com/email", event.user.email);
  api.accessToken.setCustomClaim("https://olmenta.com/email_verified", event.user.email_verified);
};
```

Deploy it. Then go to Actions → Triggers → post-login, drag it into the flow, and apply.

How it behaves:

- **Password login** (`olmenta-users`): no lookup, only the email claim.
- **Google, already linked:** Auth0 hands the Action the primary user, which holds an `olmenta-users` identity, so the login continues with no lookup.
- **Google, first time, invited:** the Google identity is linked under the invited user, and the session continues as that user. It works whether or not the person has set their password yet.
- **Google without an invitation, or with an unverified email:** denied with the invitation message. Auth0 still keeps that Google user (social sign-ups can't be stopped), but it never gets a token or reaches Olmenta. You can delete it from User Management.
- **The Management API fails:** the login is denied, never let in unlinked. The tenant logs (Monitoring → Logs) show the error.

Why linking is automatic: only you can create `olmenta-users` users, so nobody can plant an account with someone else's email to capture their Google login. Auth0's "suggested linking" pattern (the person proves both accounts in a page of ours) would only matter once sign-ups open.

## 6. Environment variables

**Webapp** (`webapp/.env`):

| Variable | Value |
|---|---|
| `APP_ENV` | `local` / `dev` / `beta` / `prod` |
| `AUTH0_DOMAIN` | `olmenta.eu.auth0.com` (no `https://`) |
| `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` | from the environment's application |
| `AUTH0_SECRET` | `openssl rand -hex 32` (different per environment) |
| `APP_BASE_URL` | `http://localhost:3000`, `https://dev.olmenta.com` or `https://beta.olmenta.com` |
| `AUTH0_AUDIENCE` | the environment's API identifier |

**API** (`backend/.env`):

| Variable | Value |
|---|---|
| `APP_ENV` | same as the webapp |
| `AUTH_MODE` | `auth0` (required in dev/beta/prod; the API refuses to start with `dev_user` there) |
| `AUTH0_DOMAIN` | `olmenta.eu.auth0.com` |
| `AUTH0_AUDIENCE` | the environment's API identifier |

Without `AUTH0_DOMAIN`, with `APP_ENV=local` and `AUTH_MODE=dev_user`, everything runs as before as the seeded development user: no login. The tests, the e2e suite and the dev MCP server run this way.

## 7. Inviting someone

1. User Management → Users → Create User: their email, connection `olmenta-users`, any temporary password.
2. Send them the invitation: on the user's page, **Send Password Reset Email**, or create a change-password ticket with "mark email as verified" and send the link yourself. They choose their password and sign in at the environment's URL.
3. If their address is a Google account, they can skip the password and use **Continue with Google** with that same address; the Action links it.
4. The first time they sign in, Olmenta creates their user with a cash account and starts the onboarding.

To remove access, block or delete the user in Auth0. Their data stays in the environment's database until deleted from Olmenta.

## 8. Login checklist (manual, per environment)

Run this on `http://localhost:3000` (or `https://dev.olmenta.com` through cloudflared) with the dev application, and again on beta after deploying:

- [ ] Opening `/budgets` without a session goes to Auth0's login, and after signing in lands back on `/budgets`.
- [ ] The sidebar and Settings show your name and email; "Log out" ends the session, and the next page asks you to sign in again.
- [ ] A second invited user sees an empty Olmenta (onboarding), not your data.
- [ ] There's no sign-up option on the login page.
- [ ] **Password, then Google:** an invited user signs in with their password, logs out, then uses "Continue with Google" with the same address. They see the same budget, and in Auth0 their user shows two identities.
- [ ] **Google first:** a newly invited user who never set a password signs in with Google and lands in the onboarding. Their Auth0 user is the `auth0|…` one, with Google linked.
- [ ] **Google without an invitation:** a Google account with no invitation is denied with the invitation-only message.
- [ ] A token for another environment is rejected: with the dev API running, call it with a beta token (`curl -H "Authorization: Bearer <beta token>" http://localhost:8000/me` → 401).
