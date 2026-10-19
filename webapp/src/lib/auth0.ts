import { Auth0Client } from "@auth0/nextjs-auth0/server";

/* Sessions with Auth0 (spec: authentication, auth0-users design D2).
   The access token is for this environment's API (AUTH0_AUDIENCE:
   https://api-dev|api-beta|api.olmenta.com); offline_access lets the SDK
   refresh it without a new login. Without AUTH0_DOMAIN, auth is disabled —
   allowed only in local and test (the seeded development user); anywhere
   else that's a misconfiguration and requests fail closed. */

const APP_ENV = process.env.APP_ENV ?? "local";

export const authDisabled = !process.env.AUTH0_DOMAIN && (APP_ENV === "local" || APP_ENV === "test");

const REQUIRED = [
  "AUTH0_DOMAIN",
  "AUTH0_CLIENT_ID",
  "AUTH0_CLIENT_SECRET",
  "AUTH0_SECRET",
  "APP_BASE_URL",
  "AUTH0_AUDIENCE",
] as const;

function createClient(): Auth0Client {
  // The SDK's own errors for a missing variable are cryptic ("ikm" must be…).
  const missing = REQUIRED.filter((name) => !process.env[name]);
  if (missing.length) {
    throw new Error(`Auth0 is not fully configured: set ${missing.join(", ")} (docs/auth0-setup.md)`);
  }
  return new Auth0Client({
    authorizationParameters: {
      audience: process.env.AUTH0_AUDIENCE,
      scope: "openid profile email offline_access",
    },
  });
}

export const auth0: Auth0Client | null = authDisabled ? null : createClient();
