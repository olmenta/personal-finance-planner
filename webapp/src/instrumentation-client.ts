/* Sentry browser init. GDPR posture: no default PII, replays fully masked —
   a finance app must never ship balances or payee names in telemetry. */

import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  sendDefaultPii: false,
  tracesSampleRate: process.env.NODE_ENV === "development" ? 1 : 0.1,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1,
  // Noise that isn't ours: browser extensions and Next.js dev-mode internals
  // (stale HMR chunks, devtools manifest lookups).
  denyUrls: [
    /^chrome-extension:\/\//i,
    /^moz-extension:\/\//i,
    /^safari-(web-)?extension:\/\//i,
    /\/extensions\//i,
  ],
  ignoreErrors: [
    "__webpack_modules__[moduleId] is not a function",
    /React Client Manifest/,
  ],
  integrations: [
    Sentry.replayIntegration({
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],
});

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
