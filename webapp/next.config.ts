import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  // The e2e suite runs its own dev server next to yours; a separate build
  // directory keeps the two from overwriting each other's chunks.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
};

export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  // Source-map upload auth; builds work fine without it (upload is skipped).
  authToken: process.env.SENTRY_AUTH_TOKEN,
  widenClientFileUpload: true,
  tunnelRoute: "/monitoring",
  silent: !process.env.CI,
});
