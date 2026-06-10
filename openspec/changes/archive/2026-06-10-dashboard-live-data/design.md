# Design — Dashboard live data

## Context

Budget and transactions screens are live behind the BFF (`webapp/src/app/api/*` → FastAPI); the dashboard still renders `mock-data.ts`. The server-state layer (TanStack Query, `lib/api.ts`, `QueryStates`) and the proxy helper (`lib/server/backend.ts`) already exist — this change extends them rather than introducing anything new. The only missing data is aggregate: all-time balance, month income/expense totals, weekly buckets. Backend has no aggregate endpoint; shipping the full transaction history to compute balance client-side would grow unboundedly.

## Goals / Non-Goals

**Goals:**

- One new aggregate endpoint (`GET /summary/{month}`) computed in SQL.
- Dashboard fully live: balance, stat cards, weekly chart, budget bars, recent transactions.
- Reuse: existing query keys (`["budget", month]`, `["transactions", month]`, `["categories"]`), `SkeletonPanel`/`ErrorPanel`, `euroCents`, `toneForCategory`.

**Non-Goals:**

- Coach insights (capsule copy stays static), user greeting (no auth), goals screen, report mode in budgets, month navigation, caching/digest precomputation.

## Decisions

### D1 — One summary endpoint, not three

`GET /summary/{month}` returns `{ balance_cents, income_cents, expense_cents, weeks: [{start, spent_cents, income_cents}] }`. One round-trip feeds the balance card, both stat cards, and the chart. Alternatives rejected: separate `/balance` + `/summary` (two trips, no consumer wants them separately); client-side aggregation over `GET /transactions` (balance needs *all* history — unbounded payload).

### D2 — Week buckets are Monday-based calendar weeks, clamped to the month

Buckets start on the Mondays overlapping the month; the first bucket is clamped to the 1st. Label client-side as W1…W5/W6. Spanish locale expects Monday weeks (ISO 8601). Computed in Python over one grouped-by-date SQL query (`date, SUM(positive), SUM(negative)` for the month) — date→bucket mapping in Python keeps the SQL portable (SQLite tests + Postgres dev) instead of dialect-specific `date_trunc('week', …)`.

### D3 — Service layer beside the budget service

`backend/app/services/summary.py` with `build_summary(db, user, month) -> SummaryView`; router `backend/app/routers/summary.py` (`GET /summary/{month}`, month validated like the budget router). Balance: single `SUM(amount_cents)` over confirmed transactions. Month totals reuse the same filters as `budget_view.income_cents`/`spent_by_category` (confirmed only, signed split).

### D4 — Dashboard becomes a client component composing existing queries

`page.tsx` gets `"use client"` and uses four queries: `["summary", month]` (new), `["budget", month]`, `["transactions", month]`, `["categories"]` — the last three share cache with the budget/transactions screens, so navigation between screens is warm. Per-panel loading/error: the balance row, chart, budgets panel, and recent list each render their own `SkeletonPanel`, one shared `ErrorPanel` if the summary query fails (it feeds the page's hero numbers). Add-transaction invalidation: extend `AddTransactionDialog` to also invalidate `["summary", currentMonth()]` — it already invalidates transactions + budget.

### D5 — Presentation mapping stays in the page

- BalanceCard expects split `amount`/`cents` strings → small `splitEuro(cents)` helper next to the page (or in `format.ts`) producing `("87.457", ",85 €")`.
- Budgets panel: flatten budget view categories, sort by `spent_cents` desc, take 4, map to `BudgetBar` props (`spent`/`limit` formatted, `percent = round(spent / (assigned + rollover) * 100)`, capped display ≥ 101 when over); categories with zero limit and zero spent are skipped.
- Recent transactions: first 4 of the month list (already newest-first), `TransactionRow` props via the same category join as the transactions screen.
- Chart bar heights: `height% = value / max(all bucket values)`, zero-safe.

## Risks / Trade-offs

- [Week bucket definition may not match a future reports feature] → it's one private function; spec pins only "every transaction in exactly one bucket, totals add up", not the bucket boundaries.
- [Four queries on one screen → staggered pop-in] → per-panel skeletons sized to final layout (no shift); three of four queries are usually cache-warm.
- [Balance defined as Σ confirmed transactions ignores account opening balances] → accounts have no opening-balance field in v1; when Open Banking lands, balance moves behind the same endpoint without a contract change.

## Migration Plan

1. Backend endpoint + tests (additive, deployable alone).
2. BFF route + `api.ts` type/helper (dead until used).
3. Dashboard rewire + mock-data trim.
Rollback: revert webapp commit; backend endpoint is additive.

## Open Questions

- None blocking.
