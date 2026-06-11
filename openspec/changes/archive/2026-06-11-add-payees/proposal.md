# Proposal — Payees (payee on expenses, payer on incomes)

## Why

"Who did I pay?" has no first-class answer: the free-text description doubles as merchant, note, and bank noise, so the same shop is spelled five ways and nothing can be learned from it. A YNAB-style payee — one entity, labeled "Payee" on expenses and "Payer" on incomes — gives repeat entry autocomplete and lets the app prefill the category the user last used with that payee, directly serving the < 5-seconds entry promise.

## What Changes

- **Payee entity**: new `payees` table (per-user, unique case-insensitive name) and nullable `transactions.payee_id` FK — one Alembic migration. One entity serves both directions, YNAB-style; only the UI label changes ("Payee" / "Payer").
- **Find-or-create on write**: manual transaction create (and edit, once `edit-delete-transactions` lands) accepts an optional `payee` name; the backend reuses the existing payee case-insensitively or creates it. No separate payee CRUD in v1 — payees are born from use. Rename/merge is v1.x.
- **Payee list with category memory**: `GET /payees` returns each payee with the `category_id` of the user's most recent transaction with it — the data behind autocomplete and category prefill.
- **Entry/visibility UI**: the add-transaction dialog gains a payee field (labeled by direction) with suggestions from the payee list; picking a known payee prefills the category when none is chosen yet. The transactions list shows the payee as the row's primary line with the note secondary; `TransactionOut` gains `payee_id` + `payee_name`.
- **Imports unchanged**: imported rows keep payee null in v1 — raw bank strings would flood the payee list; mapping bank descriptions to payees is a natural follow-up to the AI categorization work.
- **BFF**: `GET /api/payees` route.

## Capabilities

### New Capabilities

- `payees`: the payee entity contract — find-or-create on transaction write, listed with last-used-category memory.

### Modified Capabilities

- `data-model`: `Payee` entity, `transactions.payee_id` FK, migration.
- `transactions-api`: create requirement gains the optional `payee` field; the list requirement's row shape gains payee fields.
- `bff-proxy`: proxied-routes requirement gains `GET /api/payees`.
- `webapp-server-state`: new requirement — payee entry with autocomplete + category prefill; payee-first row rendering.

## Impact

- `backend/app/models.py` + Alembic migration (`payees` table, FK); `routers/transactions.py` (find-or-create), new `routers/payees.py`; `schemas.py`.
- `backend/tests/`: payee find-or-create (case-insensitive), list with last category, transaction output shape.
- `webapp/src/app/api/payees/route.ts`; `api.ts` types + `fetchPayees`; `AddTransactionDialog` payee field + prefill; transactions page row rendering.
- Conflicts to merge at sync time: `transactions-api` and `bff-proxy` are also touched by in-flight changes (`edit-delete-transactions`, `manage-categories`, `ai-categorization-review`).
