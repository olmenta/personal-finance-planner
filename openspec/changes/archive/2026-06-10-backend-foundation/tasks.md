# Tasks — Backend foundation

## 1. Project plumbing

- [x] 1.1 `uv add sqlalchemy alembic pydantic-settings "psycopg[binary]"` and `uv add --group dev httpx` (TestClient); verify `uv sync`
- [x] 1.2 `app/config.py` (pydantic-settings: required `DATABASE_URL`, optional `TEST_DATABASE_URL`, loaded from `backend/.env`) and `app/db.py` (engine, session factory, FastAPI session dependency); write `backend/.env` (Neon dev: pooler host for app, direct host for migrations — password NOT committed) + `backend/.env.example`

## 2. Models & migrations

- [x] 2.1 `app/models.py`: User, Account, CategoryGroup, Category, Transaction (signed `amount_cents`, `source`, `status`, `dedupe_hash` unique per account, manual-entry salt), BudgetMonth, BudgetAssignment (`suggestion_state`) — portable column types only
- [x] 2.2 Alembic init (`backend/alembic/`), env wired to `config.py` URL (direct Neon host) and model metadata; initial migration; `uv run alembic upgrade head` applies to the Neon dev database
- [x] 2.3 `app/seed.py`: idempotent dev user + cash account + Spanish category tree (Vivienda, Comida, Transporte, Estilo de vida — same categories as the webapp mock); NO seeded income — income arrives via the AI onboarding change (design Decision 8)

## 3. Transactions API

- [x] 3.1 `app/schemas.py`: TransactionCreate (`amount_cents > 0`, `kind` expense|income default expense, optional `note`/`date`), TransactionOut; machine-readable error envelope (`{"code": …}`)
- [x] 3.2 `routers/transactions.py`: POST (maps kind→signed cents, source `manual`, status `confirmed`, 422 invalid amount, 404 unknown category) and GET with `?month=` filter, newest first
- [x] 3.3 Tests (pytest against `TEST_DATABASE_URL` Neon branch, per-test transaction rollback): minimal entry defaults to today (Europe/Madrid), invalid amount 422, unknown category 404, month filter, dedupe constraint (and manual same-day duplicates allowed via salt)

## 4. Budget API

- [x] 4.1 `services/budget_view.py`: spent/income aggregation (confirmed only), available + to-be-assigned derivation, recursive rollover from previous months
- [x] 4.2 Lazy month materialization with draft suggestions copied from the previous month; zero/no-draft on first month
- [x] 4.3 `routers/budget.py`: GET `/budget/{month}` (BudgetMonthView shape matching `webapp/src/lib/mock-data.ts`), PUT assignment (`edited`, returns recalculated to-be-assigned), POST confirm-suggestions (drafts→confirmed, edits untouched)
- [x] 4.4 Tests: view contract fields, spec row math (32+120−138=14 €), staged excluded from spent, assignment recalculates TBA to 0, first-month empty, drafts from May, confirm preserves edits, positive rollover carryover

## 5. Wire-up & verify

- [x] 5.1 Mount routers in `main.py`; categories router (`GET /categories` grouped); run `uv run alembic upgrade head && uv run python -m app.seed && uv run uvicorn app.main:app` and smoke-test endpoints
- [x] 5.2 `uv run pytest` green; every spec scenario has a covering test
