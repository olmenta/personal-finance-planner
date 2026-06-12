/* Sentry Node.js (BFF route handlers, server components). sendDefaultPii
   stays false — request bodies can carry transaction data (GDPR). */

import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  sendDefaultPii: false,
  tracesSampleRate: process.env.NODE_ENV === "development" ? 1 : 0.1,
  // Next.js dev-mode internals (stale HMR chunks, devtools manifest lookups)
  // surface as server errors during development — not app bugs.
  ignoreErrors: [
    "__webpack_modules__[moduleId] is not a function",
    /React Client Manifest/,
  ],
});
