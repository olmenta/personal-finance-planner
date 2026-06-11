# Tasks — Edit and delete transactions

## 1. Backend API

- [x] 1.1 `TransactionUpdate` schema in `backend/app/schemas.py` (all optional: `amount_cents > 0`, `kind`, `category_id`, `note` nullable to clear, `date`)
- [x] 1.2 `PATCH /transactions/{id}` in `backend/app/routers/transactions.py`: resolve by id + user + `status == "confirmed"` else 404 `transaction_not_found`; validate category (404 `category_not_found`); sign amount from `kind` or keep current sign; never touch `dedupe_hash` (design D1–D3)
- [x] 1.3 `DELETE /transactions/{id}`: same resolution rule, hard delete, 204 (design D4)
- [x] 1.4 Tests in `backend/tests/test_transactions.py`: partial edit fields, sign kept without `kind`, direction flip, note cleared with null, unknown/foreign/staged id → 404, unknown category → 404, budget `spent_cents` reflects edit and delete, edited imported row still skipped on re-import (hash immutable), deleted imported row staged again on re-import; `uv run pytest` green

## 2. BFF and client

- [x] 2.1 `webapp/src/app/api/transactions/[id]/route.ts`: PATCH + DELETE via `proxyFetch`
- [x] 2.2 `webapp/src/lib/api.ts`: `TransactionUpdate` type, `updateTransaction(id, patch)`, `deleteTransaction(id)`

## 3. UI

- [x] 3.1 Row actions menu on the transactions screen: trailing `more-horizontal` IconButton → shadcn `DropdownMenu` with "Edit" and "Delete" (delete in `--expense` tone) (design D5)
- [x] 3.2 `EditTransactionDialog`: prefilled sibling of `AddTransactionDialog` (Expense/Income segmented control, amount, description, category select, date); PATCH on save; invalidate `["transactions"]` + `["budget", m]` / `["summary", m]` for old and new months
- [x] 3.3 Delete confirmation dialog naming the transaction (description + amount), destructive "Delete transaction" action; on confirm DELETE + same invalidation for the row's month
- [x] 3.4 Error states in both dialogs: retryable message on failure, no dead ends

## 4. Verification

- [x] 4.1 `uv run pytest` green in `backend/` (TEST_DATABASE_URL exported); `volta run npm run build` + `volta run npm run lint` green in `webapp/`
- [x] 4.2 E2E with both processes: edit an imported row's amount → list/budget/dashboard update; move a row across months → both months refresh; delete a row → totals shrink; re-upload the bank file → edited row skipped, deleted row staged again
