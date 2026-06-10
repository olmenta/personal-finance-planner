# Proposal — Backend foundation

## Why

The backend is a `/health` stub: no models, no persistence, no endpoints. Every v1 feature (expense entry, zero-based budget, CSV import, onboarding) needs the data layer from [project-definition.md](../../../project-definition.md) §6.4 and a first API surface. The webapp already consumes a defined contract (`BudgetMonthView`, archived change `2026-06-10-zero-based-budget-screen`) against mock data — this change makes the backend able to serve it for real.

## What Changes

- SQLAlchemy 2.0 models for the v1 core subset of §6.4: `User` (single seeded dev user — Auth0 comes later), `Account`, `CategoryGroup`, `Category`, `Transaction` (integer cents, `source`, `dedupe_hash`, staged/confirmed status), `BudgetMonth`, `BudgetAssignment`.
- Alembic migrations wired to the models; `DATABASE_URL` env config (local SQLite default for zero-setup dev, PostgreSQL/Neon in deployment).
- Seed script (`uv run python -m app.seed`): dev user, cash account, and the default Spanish category tree (Vivienda, Comida, Transporte, Estilo de vida — matching the webapp mock) as the stand-in until AI onboarding generates personalized trees.
- First API routers (no auth yet, single dev user):
  - `GET /categories` — grouped category tree.
  - `POST /transactions` + `GET /transactions` — manual entry contract (amount_cents, category_id, optional note, date defaults to today) supporting the < 5 s entry promise.
  - `GET /budget/{month}` — serves the `BudgetMonthView` shape the webapp already renders; `PUT /budget/{month}/assignments/{category_id}` and `POST /budget/{month}/confirm-suggestions` mutations; drafts derived from the previous month's assignments.
- pytest suite: model/round-trip tests and API tests over in-memory SQLite fixtures (first backend tests in the repo).

## Capabilities

### New Capabilities

- `data-model`: persistence schema, migrations, cents/derivation rules, seeded defaults.
- `transactions-api`: create and list manual transactions.
- `budget-api`: budget month view (to-be-assigned, available, rollover), assignment mutations, draft suggestions from prior month.

### Modified Capabilities

<!-- none — budget-assignment / budget-suggestions specs describe the UI; the API contract here feeds them without changing their requirements -->

## Impact

- `backend/app/`: new `models.py`, `db.py`, `schemas.py`, `seed.py`, `routers/` (categories, transactions, budget); `main.py` gains routers.
- `backend/pyproject.toml`: add `sqlalchemy`, `alembic`, `pydantic-settings`, `httpx` (dev, for TestClient).
- `backend/alembic/`: new migration environment + initial migration.
- `backend/tests/`: new pytest suite.
- No webapp changes in this change (BFF wiring is a follow-up); no Auth0, Stripe, CSV, or AI integration yet.
