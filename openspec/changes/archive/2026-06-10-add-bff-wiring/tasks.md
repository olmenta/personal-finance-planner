# Tasks — BFF wiring

## 1. Backend: quick-fill fields (budget-api delta)

- [x] 1.1 Add `last_month_assigned_cents`, `avg_3m_cents`, `last_month_spent_cents` (all `int | None`) to `BudgetCategoryView` in `backend/app/schemas.py`
- [x] 1.2 Compute the three fields in `backend/app/services/budget_view.py` per design D5 (prev-month assignment, prev-month confirmed spend, ≤3-month spend mean rounded to whole euros; null without history)
- [x] 1.3 Tests in `backend/tests/test_budget.py`: quick-fill from history scenario and first-month-all-null scenario; `uv run pytest` green

## 2. Webapp: server-state foundation

- [x] 2.1 `volta run npm install @tanstack/react-query` in `webapp/`
- [x] 2.2 Create `webapp/src/app/providers.tsx` (`"use client"`, QueryClientProvider, defaults per design D6) and mount it in the root layout
- [x] 2.3 Create `webapp/src/lib/api.ts`: TS interfaces mirroring `backend/app/schemas.py` (incl. quick-fill fields), typed fetch helpers against `/api/*`, and `toneForCategory` map (tone leaves the shared types)

## 3. Webapp: BFF proxy routes

- [x] 3.1 Create `webapp/src/lib/server/backend.ts`: `proxyFetch` helper — `BACKEND_URL` (default `http://localhost:8000`), JSON/status pass-through, `cache: "no-store"`, 502 `{"code": "backend_unavailable"}` on fetch failure
- [x] 3.2 Route Handlers: `app/api/categories/route.ts` (GET), `app/api/transactions/route.ts` (GET with query string + POST)
- [x] 3.3 Route Handlers: `app/api/budget/[month]/route.ts` (GET), `app/api/budget/[month]/assignments/[categoryId]/route.ts` (PUT), `app/api/budget/[month]/confirm-suggestions/route.ts` (POST)
- [x] 3.4 Add `BACKEND_URL` to `webapp/.env.example` (or create it) and document the two-process dev setup (uvicorn + next dev) in the README

## 4. Budget screen on live data

- [x] 4.1 Rewrite `webapp/src/lib/useBudgetMonth.ts` over `useQuery(["budget", month])` + mutations, keeping the existing return shape (design D3); current calendar month as key (D4)
- [x] 4.2 Optimistic assign: `onMutate` cache patch (category + to-be-assigned), `onError` rollback, `onSettled` invalidate; surface retryable error state
- [x] 4.3 Confirm-suggestions mutation invalidating the month query on success
- [x] 4.4 Update `budgets/page.tsx`, `AssignGroups`, `AssignRow` to the server types (tone via `toneForCategory`); add loading skeleton + error/retry state (no layout shift)

## 5. Transactions screen on live data

- [x] 5.1 Queries for `GET /api/transactions?month=` and `GET /api/categories`; client-side join for icon/name in `transactions/page.tsx`
- [x] 5.2 Wire the add-transaction flow to `POST /api/transactions`; on success invalidate transactions list and budget month queries
- [x] 5.3 Loading skeleton, error/retry, and action-inviting empty state for the list

## 6. Cleanup and verification

- [x] 6.1 Trim `webapp/src/lib/mock-data.ts` to what dashboard/goals still consume; delete the `BudgetMonthView` mock block and now-unused types
- [x] 6.2 `volta run npm run lint` and `volta run npm run build` green in `webapp/`; `uv run pytest` green in `backend/` (note: `next lint` has no ESLint config in this repo — pre-existing; build's type-check used instead)
- [x] 6.3 Manual end-to-end check with both processes running: assign → reload persists; add expense → budget spent updates; backend stopped → error states with retry (no mock fallback)
