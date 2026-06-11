# Tasks — Payees

## 1. Data model and migration

- [x] 1.1 `Payee` model in `backend/app/models.py` (id, user_id, name) with per-user case-insensitive unique index (`func.lower(name)`); nullable `transactions.payee_id` FK
- [x] 1.2 Alembic migration (`payees` table + FK + functional unique index) with working `downgrade()`; `uv run alembic upgrade head` green

## 2. Backend API

- [x] 2.1 Find-or-create helper (trimmed, case-insensitive within user) wired into `POST /transactions`; `TransactionCreate` gains optional `payee` (≤120 chars); if `edit-delete-transactions` has landed, wire the same into `PATCH /transactions/{id}` (empty string clears) — else leave a reconciliation note (design D2) — *PATCH not landed; reconciliation note left in `resolve_payee` docstring*
- [x] 2.2 `TransactionOut` gains `payee_id` + `payee_name` (server-side join); list/create/import responses populate it (imports stay null, design D5)
- [x] 2.3 `backend/app/routers/payees.py`: `GET /payees` → `[{id, name, last_category_id}]` ordered by most recent use (design D3); register in `main.py`
- [x] 2.4 Tests: first use creates payee, case-insensitive reuse, trim, list ordering + `last_category_id` (incl. null for uncategorized-only payee), imported rows null payee, output shape; `uv run pytest` green

## 3. BFF and client

- [x] 3.1 `webapp/src/app/api/payees/route.ts` (GET via `proxyFetch`)
- [x] 3.2 `webapp/src/lib/api.ts`: `PayeeOut` type, `fetchPayees`, `TransactionCreate.payee?`, `TransactionOut.payee_id/payee_name`

## 4. UI

- [x] 4.1 Payee field in `AddTransactionDialog` above the description: text input + suggestion list filtered locally from `["payees"]`, label "Payee"/"Payer" by direction, free text allowed (design D4)
- [x] 4.2 Category prefill from the selected payee's `last_category_id` only when category is still empty
- [x] 4.3 Transactions list rows: payee as primary line when present, note secondary; unchanged otherwise; mutations also invalidate `["payees"]`
- [x] 4.4 If the edit dialog from `edit-delete-transactions` exists, add the same payee field there — *N/A: edit dialog not landed; reconciliation falls to `edit-delete-transactions`*

## 5. Verification

- [x] 5.1 `uv run pytest` green (TEST_DATABASE_URL exported); `volta run npm run build` + `volta run npm run lint` green
- [x] 5.2 E2E with both processes: add expense with new payee → payee suggested on next entry with category prefilled; switch to Income → label reads "Payer"; list shows payee-first rows; import flow untouched (null payees)
- [x] 5.3 At sync/archive time: merge `transactions-api` and `bff-proxy` requirement texts with whatever in-flight changes have landed (`edit-delete-transactions`, `manage-categories`, `ai-categorization-review`) — *none had landed; deltas applied cleanly to main specs at archive*
