# Tasks — Dashboard live data

## 1. Backend: summary API

- [x] 1.1 `SummaryView` + `SummaryWeek` schemas in `backend/app/schemas.py` (`balance_cents`, `income_cents`, `expense_cents`, `weeks[{start, spent_cents, income_cents}]`)
- [x] 1.2 `backend/app/services/summary.py`: `build_summary` — all-time confirmed balance, month totals, Monday-based week buckets clamped to the month (design D2/D3)
- [x] 1.3 `backend/app/routers/summary.py`: `GET /summary/{month}`; register in `main.py`
- [x] 1.4 Tests in `backend/tests/test_summary.py`: month totals exclude staged, all-time balance spans months, buckets cover every transaction and sum to month totals, empty month returns zeros; `uv run pytest` green

## 2. BFF + client

- [x] 2.1 Route Handler `webapp/src/app/api/summary/[month]/route.ts` (GET via `proxyFetch`)
- [x] 2.2 `webapp/src/lib/api.ts`: `SummaryView`/`SummaryWeek` types + `fetchSummary(month)`
- [x] 2.3 `AddTransactionDialog`: also invalidate `["summary", currentMonth()]` on success

## 3. Dashboard rewire

- [x] 3.1 `page.tsx` → `"use client"` with queries: summary, budget month, transactions, categories (design D4)
- [x] 3.2 Balance card + income/expense stat cards from summary (`splitEuro` helper for the BalanceCard amount/cents split)
- [x] 3.3 SpendChart from `weeks` buckets — heights normalized to the max bucket, labels W1…Wn, legend "Spent"/"Income"
- [x] 3.4 Budgets panel: top 4 categories by spent from the budget view mapped to `BudgetBar` (percent vs assigned+rollover); badge shows real active count
- [x] 3.5 Recent transactions: first 4 of the month list with category join (`TransactionRow`); "View all" links to `/transactions`; empty state invites first entry
- [x] 3.6 Per-panel `SkeletonPanel` loading + `ErrorPanel` retry on summary failure (no layout shift)

## 4. Cleanup and verification

- [x] 4.1 Delete `balance`, `transactions`, `Txn`, `weeks` from `webapp/src/lib/mock-data.ts` (keep `goals`, `budgets`, `chartLegend`)
- [x] 4.2 `volta run npm run build` green in `webapp/`; `uv run pytest` green in `backend/`
- [x] 4.3 E2E with both processes: dashboard shows real balance/totals; add expense from dashboard → stat card, chart, budget bar, recent list update; backend stopped → retryable error state (502 `backend_unavailable` path reuses the proxy verified in add-bff-wiring)
