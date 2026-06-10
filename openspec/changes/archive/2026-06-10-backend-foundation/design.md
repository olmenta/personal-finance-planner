# Design — Backend foundation

## Context

`backend/` is a FastAPI stub (`/health` only) with uv-pinned Python 3.12 and pytest in dev deps but no tests. The target architecture ([project-definition.md](../../../project-definition.md) §6) is FastAPI on Cloud Run + Neon Postgres + SQLAlchemy 2.0/Alembic, fronted by a Next.js BFF. The webapp already renders a `BudgetMonthView` contract (defined in the archived `zero-based-budget-screen` change and synced to `openspec/specs/budget-assignment`) from mock data — this change builds the persistence and API that can serve it. Auth0, Stripe, CSV ingestion, AI and the BFF wiring are explicitly later changes.

## Goals / Non-Goals

**Goals:**

- §6.4 core schema (v1 subset) with Alembic migrations and integer-cent money.
- Seeded dev user + default Spanish category tree so the API is usable without onboarding.
- Endpoints for the two flows the webapp already has UI for: manual transactions and the budget month (view, assign, confirm suggestions).
- First pytest suite; every spec scenario covered by a test.

**Non-Goals:**

- Auth (single seeded dev user; Auth0 JWT validation is its own change).
- Subscription, ImportBatch, OnboardingSession, UserPreferences tables (added with their features).
- CSV adapters / ports-and-adapters pipeline (§6.3) — only the `source` column lands now.
- BFF route handlers and webapp API client — follow-up change swaps mock for API.
- Deployment (Cloud Run, Terraform, Neon provisioning).

## Decisions

### Decision 1: Postgres everywhere — Neon dev environment, no SQLite

No SQLite at any stage (user decision 2026-06-10). `DATABASE_URL` is required (no default); local development points at the **Neon dev environment**:

- Host: `ep-little-hill-ab4lvwvf.eu-west-2.aws.neon.tech` (pooler: `ep-little-hill-ab4lvwvf-pooler.eu-west-2.aws.neon.tech`)
- Database: `neondb` · Role: `neondb_owner`
- Credentials live in `backend/.env` (gitignored; `.env.example` documents the shape without the password). Use the **direct host for Alembic migrations**, the pooler for the app.

Driver: `psycopg` (v3, sync SQLAlchemy). Tests run against Postgres too — a dedicated Neon branch/database via `TEST_DATABASE_URL`, with per-test transaction rollback for isolation; Neon branching (§6.2) exists precisely for per-environment databases. Benefit: full dialect parity from day one and JSONB available the moment `UserPreferences` lands. Trade-off: tests need network; accepted.

### Decision 2: Signed cents internally; manual entry posts positive + `kind`

`Transaction.amount_cents` is **signed** (expenses negative, income positive) matching the §6.3 ingestion contract, so CSV adapters later need no remapping. The public `POST /transactions` keeps the UI's mental model: `amount_cents > 0` plus `kind: "expense" | "income"` (default `expense`); the router maps to the signed value. `spent_cents` aggregates negative confirmed transactions; `income_cents` of a month aggregates positive ones.

### Decision 3: `BudgetMonth` is lazily materialized; suggestions copy the previous month

`GET /budget/{month}` creates the month row + assignments on first access: each category's assignment drafts from the previous month (`suggestion_state = "draft"`), or zero with no draft when no history exists (first-month spec). `suggestion_state` is a column on `BudgetAssignment` (`draft|confirmed|edited`); `PUT …/assignments/{id}` sets `edited`, `POST …/confirm-suggestions` flips remaining `draft → confirmed` and never touches amounts or `edited` rows. Rationale: lazy creation avoids a month-rollover job; the AI suggestion engine later replaces only the draft-derivation function.

### Decision 4: Derived values computed in one query layer, never stored

`available = assigned + rollover − spent` and `to_be_assigned = income − Σ assigned` are computed in a `budget_view.py` service. Rollover for month M = the category's full available chain at end of M−1, computed recursively over existing BudgetMonth rows (bounded: months exist only once visited). No materialized snapshot until performance demands it (§6.4 note). Keeping derivation in one module gives the future materialization a single seam.

### Decision 5: Layout — routers + service module, models in one file

```
backend/app/
  main.py          # app factory, router mounting
  config.py        # pydantic-settings (DATABASE_URL)
  db.py            # engine, session dependency
  models.py        # all §6.4 core models (one file until it hurts)
  schemas.py       # Pydantic request/response (BudgetMonthView mirrors webapp)
  services/budget_view.py
  routers/{categories,transactions,budget}.py
  seed.py          # idempotent: dev user, cash account, category tree
backend/alembic/   # migration env + initial revision
backend/tests/     # pytest, in-memory SQLite fixtures
```

Errors return machine-readable codes (`{"code": "category_not_found"}`) per §6.7 — the frontend maps codes to translated strings.

### Decision 6: Dev-user scoping baked into queries now

All queries filter by `user_id` even though only the seeded dev user exists, so the Auth0 change only swaps "seeded user" for "user from JWT" without touching query logic.

### Decision 7: Calendar months, Europe/Madrid — confirmed

Budget months are calendar months keyed `YYYY-MM`; "today" defaults resolve in **Europe/Madrid**. Income that arrives on day ~27 does NOT shift the month boundary — late-month income is treated as funding the *next* month's assignment (the zero-based "age your money" pattern); the coach/suggestion layer will steer it there. Custom budget-period start days are deferred (see Risks).

### Decision 8: Income starts at 0 — provided later by AI onboarding

No seeded salary. `income_cents` aggregates positive confirmed transactions only; until onboarding captures income (its dedicated change), months read `income_cents = 0` and the to-be-assigned hero shows the honest negative once euros are assigned. Keeps the data truthful instead of faking a denominator.

## Risks / Trade-offs

- [Tests depend on network (Neon)] → per-test transaction rollback keeps them fast; a Neon test branch isolates them from dev data; offline work is degraded — accepted.
- [Income = 0 until onboarding → TBA goes negative as soon as anything is assigned] → expected and honest; the webapp hero's red state communicates it; onboarding change resolves it.
- [Recursive rollover walk gets slow with many months] → bounded by lazily-created months; materialized snapshot is a contained follow-up in `budget_view.py`.
- [No auth on mutating endpoints] → backend stays local-only this change; BFF/auth change gates exposure. Do not deploy this state.
- [Lazy month creation on GET (write-on-read)] → idempotent and transactional; acceptable until a scheduler exists.
- [`dedupe_hash` on manual entries may collide legitimately (two identical coffees same day)] → include a per-day sequence/created_at salt for `source = manual`; strict hashing applies to imported sources (its real purpose).

## Open Questions

*(all resolved 2026-06-10)*

- ~~Income for the demo~~ → income stays 0; the AI onboarding interview will ask for it (Decision 8).
- ~~Month boundaries~~ → calendar months, Europe/Madrid (Decision 7).
- ~~Local database~~ → Neon dev environment, no SQLite (Decision 1).
