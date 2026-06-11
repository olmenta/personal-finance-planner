# Proposal — Edit and delete transactions

## Why

Transactions are append-only today: a typo in the amount, a wrong category, or a duplicate manual entry is permanent, which silently corrupts budget and dashboard numbers. Imports made this worse — a misfiled imported row can only be fixed by working around it. Correcting mistakes in place is table stakes for trusting the budget.

## What Changes

- **Edit a transaction**: `PATCH /transactions/{id}` updates amount (with expense/income direction), category, description, and date of a confirmed transaction the user owns; budget and summary reflect the change immediately (they are computed, never stored). The `dedupe_hash` stays immutable so re-importing a bank file never resurrects an edited row.
- **Delete a transaction**: `DELETE /transactions/{id}` removes a confirmed transaction permanently; totals recompute. Staged import rows stay out of scope — they are managed only through the import batch review (confirm/discard).
- **UI**: each row on the transactions screen gets an actions menu (edit / delete); edit opens a prefilled dialog mirroring "Add transaction"; delete asks one confirmation with a clearly destructive action button. On success the transactions, budget, and summary queries for the affected month(s) are invalidated — including both the old and new month when an edit moves the date.
- **BFF**: new `/api/transactions/{id}` Route Handler proxying PATCH and DELETE.

## Capabilities

### New Capabilities

(none — this extends existing capabilities)

### Modified Capabilities

- `transactions-api`: new requirements — update a transaction (partial edit, signed-amount semantics preserved) and delete a transaction; both confirmed-only and owner-scoped.
- `bff-proxy`: proxied-routes requirement gains `PATCH /api/transactions/{id}` and `DELETE /api/transactions/{id}`.
- `webapp-server-state`: new requirement — edit/delete flows from the transactions list with cache invalidation across affected months.

## Impact

- `backend/app/routers/transactions.py`: `PATCH` + `DELETE` handlers; `schemas.py`: `TransactionUpdate`.
- `backend/tests/test_transactions.py`: edit/delete coverage (incl. budget recompute, staged rows rejected, cross-user 404).
- `webapp/src/app/api/transactions/[id]/route.ts`: new Route Handler.
- `webapp/src/lib/api.ts`: `updateTransaction`, `deleteTransaction` helpers + `TransactionUpdate` type.
- `webapp/src/app/(app)/transactions/page.tsx` + new `EditTransactionDialog` / row actions menu (shadcn `dropdown-menu` already installed).
- No schema migration — data model unchanged.
