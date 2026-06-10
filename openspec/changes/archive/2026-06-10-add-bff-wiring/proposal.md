# Proposal — BFF wiring: webapp on real API

## Why

The backend now serves the budget and transactions contracts for real (archived change `2026-06-10-backend-foundation`), but the webapp still renders `webapp/src/lib/mock-data.ts` through client-only state (`useBudgetMonth`). Edits vanish on reload and the < 5 s expense-entry promise can't be kept end-to-end. This change wires the webapp to the FastAPI backend through Next.js Route Handlers (BFF) — the architecture rule that the browser never calls the Python API directly.

## What Changes

- **BFF proxy layer**: Next.js Route Handlers under `webapp/src/app/api/` that forward to FastAPI (`BACKEND_URL` env), passing through status codes and machine-readable error codes (`{"code": ...}`) unchanged.
- **Server-state layer**: install TanStack Query; `QueryClientProvider` in the app shell; typed API client in `webapp/src/lib/api.ts` mirroring the backend Pydantic schemas.
- **Budget screen on live data**: replace `useBudgetMonth`'s mock state with queries/mutations against `GET /budget/{month}`, `PUT /budget/{month}/assignments/{category_id}` (optimistic update with rollback on error), and `POST /budget/{month}/confirm-suggestions`. Derived values (`to_be_assigned_cents`, `available_cents`) come from the server view, no longer recomputed from mock state.
- **Transactions screen on live data**: list from `GET /transactions?month=`, joined client-side with `GET /categories` for icon/name; add-transaction flow posts to `POST /transactions` and invalidates the budget month (spent changes).
- **Backend view extension**: `BudgetCategoryView` gains the quick-fill fields the assignment UI already renders — `last_month_assigned_cents`, `avg_3m_cents`, `last_month_spent_cents` (null when no history).
- **Out of scope**: dashboard and goals screens stay on mock data (no goals API yet); presentation-only fields (`tone`) stay client-side, derived from the category; no auth (single dev user), no Stripe, no CSV import.

## Capabilities

### New Capabilities

- `bff-proxy`: Next.js Route Handler proxy contract — routing, backend base-URL config, error and status pass-through, no direct browser→FastAPI traffic.
- `webapp-server-state`: TanStack Query data layer — budget/transactions/categories queries, optimistic assignment mutation with rollback, cache invalidation after writes, loading/error presentation.

### Modified Capabilities

- `budget-api`: budget month view gains per-category quick-fill history fields (`last_month_assigned_cents`, `avg_3m_cents`, `last_month_spent_cents`), null on a first month.

## Impact

- `webapp/package.json`: add `@tanstack/react-query` (via Volta).
- `webapp/src/app/api/**`: new Route Handlers (categories, transactions, budget month + mutations).
- `webapp/src/lib/`: new `api.ts` (typed client + shared types); `useBudgetMonth.ts` rewritten over queries/mutations; `mock-data.ts` shrinks to the dashboard/goals leftovers.
- `webapp/src/app/(app)/budgets/page.tsx`, `transactions/page.tsx`, `webapp/src/components/budget/*`: read from the new hooks.
- `backend/app/schemas.py`, `backend/app/services/budget_view.py`, `backend/tests/`: quick-fill fields + tests.
- New env: `BACKEND_URL` for the Next.js server (`.env.local`, documented in README/CLAUDE.md conventions).
