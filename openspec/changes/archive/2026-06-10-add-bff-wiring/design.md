# Design — BFF wiring

## Context

The backend (FastAPI, `backend/app/`) serves `GET /categories`, `POST|GET /transactions`, `GET /budget/{month}` + assignment/confirm mutations, tested against in-memory SQLite. The webapp renders the same `BudgetMonthView` shape from `webapp/src/lib/mock-data.ts` through `useBudgetMonth` (client `useState`). Architecture rule (CLAUDE.md, project-definition §6): the browser never calls the Python API directly — Next.js Route Handlers act as the BFF. TanStack Query is the planned server-state library. Two shape gaps exist: the backend view lacks the quick-fill fields (`last_month_assigned_cents`, `avg_3m_cents`, `last_month_spent_cents`) that `AssignRow` renders, and the webapp types carry presentation fields (`tone`) the API should not own.

## Goals / Non-Goals

**Goals:**

- All budget/transactions/categories reads and writes flow browser → Route Handler → FastAPI.
- Budget screen survives reload; assignment edits are optimistic with rollback.
- Single source of truth for API types in the webapp (`lib/api.ts`), matching `backend/app/schemas.py`.
- Backend serves the quick-fill fields so the assignment UI needs no mock fallback.

**Non-Goals:**

- Auth (single seeded dev user persists), Stripe, CSV import, AI coach data.
- Dashboard and goals screens (stay on mock until their APIs exist).
- WebSockets/SSE, offline support, request deduplication beyond what TanStack Query gives for free.

## Decisions

### D1 — Thin catch-all-free proxy: one Route Handler per backend route

Explicit handlers (`app/api/categories/route.ts`, `app/api/transactions/route.ts`, `app/api/budget/[month]/route.ts`, `app/api/budget/[month]/assignments/[categoryId]/route.ts`, `app/api/budget/[month]/confirm-suggestions/route.ts`) over a single `[...path]` catch-all. Rationale: the surface is six routes; explicit handlers keep an allowlist (no accidental exposure of future backend endpoints), give per-route typing, and are where auth headers will be injected later. Shared `proxyFetch(path, init)` helper in `webapp/src/lib/server/backend.ts` handles `BACKEND_URL` resolution, JSON pass-through, the 502 `backend_unavailable` envelope, and `cache: "no-store"`. Alternative rejected: catch-all proxy — less code but forwards everything and types nothing.

### D2 — Server types mirrored by hand, not generated

`webapp/src/lib/api.ts` declares the TS interfaces (`BudgetMonthView`, `BudgetCategoryView`, `TransactionOut`, `CategoryGroupOut`, …) by hand, mirroring `backend/app/schemas.py`. Rationale: six schemas; OpenAPI codegen (openapi-typescript) adds a toolchain step and drift-management for marginal value at this size. Revisit when the surface grows (CSV import, goals). The webapp-only `tone` field moves out of the shared types: a `toneForCategory(icon)` map in `lib/api.ts` derives chip tone client-side.

### D3 — `useBudgetMonth` keeps its public shape, swaps its guts

The hook keeps returning `{ month, toBeAssignedCents, draftIds, isFirstMonth, assign, confirmSuggestions }` so `budgets/page.tsx`, `AssignGroups`, `AssignRow` change minimally. Internally: `useQuery(["budget", month])`, `useMutation` for assign with `onMutate` optimistic cache write (patch category + recompute `to_be_assigned_cents` locally), `onError` snapshot rollback, `onSettled` invalidate; confirm-suggestions mutation invalidates on success. `toBeAssignedCents` now reads the server-derived field (optimistically patched), not a client reduction. Alternative rejected: new hook + rewrite of consumers — churn without benefit.

### D4 — Month selection fixed to current month for now

The screens read the current calendar month (`new Date()` → `YYYY-MM`) as the query key. Month navigation UI is out of scope; the API already supports any month, so navigation is additive later.

### D5 — Quick-fill fields computed in `budget_view.py`

`last_month_assigned_cents`: previous month's assignment amount (null if no previous BudgetMonth). `last_month_spent_cents`: previous month's confirmed-transaction sum (null likewise). `avg_3m_cents`: mean of confirmed spending over up to 3 previous months that exist, rounded to whole euros in cents (matches the mock's behavior); null when zero previous months. Computed in the existing view service with one grouped query over prior months — no schema/migration change (derived from existing tables).

### D6 — QueryClientProvider in a client `Providers` component

`webapp/src/app/providers.tsx` (`"use client"`) wraps children in `QueryClientProvider`; root layout stays a server component. Defaults: `staleTime: 30s`, `retry: 1`, refetch on window focus on (cheap, money data wants freshness). No SSR hydration/prefetch in this change — screens are already client components; first paint shows skeletons.

## Risks / Trade-offs

- [Optimistic to-be-assigned drifts from server rounding/rules] → `onSettled` always invalidates the month query; server value wins within one round-trip.
- [Hand-mirrored types drift from Pydantic schemas] → single file (`lib/api.ts`) referenced from backend schema docstring; backend tests pin the JSON shape (quick-fill scenarios) so drift breaks CI, not the UI silently.
- [Dev requires two processes (uvicorn + next dev)] → document in README; `backend_unavailable` error state makes the failure obvious instead of a hung skeleton.
- [Concurrent mutations (rapid assigns) racing invalidation] → TanStack Query mutation defaults serialize per-key cache writes; rollback snapshots taken per mutation; acceptable for single-user v1.

## Migration Plan

1. Backend first (quick-fill fields + tests) — additive, deployable alone.
2. Webapp: providers + api client + proxy routes — dead code until screens switch, deployable alone.
3. Swap `useBudgetMonth` + transactions screen; trim `mock-data.ts` to dashboard/goals leftovers.
Rollback: revert webapp commits; backend field additions are additive and harmless to old clients.

## Open Questions

- None blocking. `avg_3m_cents` definition (spent-based, not assigned-based) chosen to match the mock's intent; revisit if the coach later defines its own suggestion math.
