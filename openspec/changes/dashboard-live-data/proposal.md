# Proposal — Dashboard on live data

## Why

The dashboard (`webapp/src/app/(app)/page.tsx`) is the landing screen and the last main surface still rendering `mock-data.ts` — balance, income/expenses, the weekly spend chart, budget bars, and recent transactions are all fake while the budget and transactions screens (archived change `2026-06-10-add-bff-wiring`) are live. A user who adds an expense sees it on Transactions but not on Overview — the app contradicts itself.

## What Changes

- **Summary API**: new backend endpoint `GET /summary/{month}` returning all-time `balance_cents`, the month's `income_cents` and `expense_cents`, and per-week spending/income buckets — aggregated in SQL, so the client never fetches the full transaction history.
- **BFF route**: `GET /api/summary/[month]` Route Handler proxying it.
- **Dashboard on live data**:
  - BalanceCard ← all-time balance; Income/Expenses StatCards ← month totals.
  - SpendChart ← weekly buckets (legend becomes "Spent" / "Income" — "Saved" was mock fiction).
  - Budgets panel ← top categories by spent from the existing `GET /budget/{month}` view (limit = assigned + rollover).
  - Recent transactions ← first 4 of `GET /transactions?month=`, joined with categories for icon/name; "View all" links to `/transactions`.
  - Loading skeletons + retryable error states, same pattern as budget/transactions screens.
- **Out of scope**: coach capsule copy and "Welcome back, Maya" greeting stay static (no coach AI, no auth yet); goals screen stays mock; no month navigation.

## Capabilities

### New Capabilities

- `summary-api`: backend month summary contract — all-time balance, monthly income/expense totals, weekly buckets.

### Modified Capabilities

- `bff-proxy`: the proxied-routes requirement gains `GET /api/summary/[month]`.
- `webapp-server-state`: new requirement — dashboard reads summary/budget/transactions via the API with loading/error presentation (ADDED requirement; existing requirements unchanged).

## Impact

- `backend/app/`: new `routers/summary.py` (or extension of an existing router), aggregation in a service; tests.
- `webapp/src/app/api/summary/[month]/route.ts`: new Route Handler.
- `webapp/src/lib/api.ts`: `SummaryView` type + fetch helper.
- `webapp/src/app/(app)/page.tsx`: rewires to queries (`"use client"`); `BalanceCard`/`StatCard`/`BudgetBar`/`TransactionRow` consume formatted live values.
- `webapp/src/lib/mock-data.ts`: `balance`, `transactions`/`Txn`, `weeks` deleted; `goals` stays (goals screen), `budgets` + `chartLegend` stay (budgets report mode, until a reports change).
