import { defineConfig } from "eslint/config";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

export default defineConfig([
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    ignores: [".next/**", ".next-e2e/**", "playwright-report/**", "test-results/**", "node_modules/**", "next-env.d.ts"],
  },
  {
    rules: {
      // Pre-existing sync-state effects in AmountInput/NumpadSheet — keep the
      // signal without failing the baseline until they are refactored.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
]);
