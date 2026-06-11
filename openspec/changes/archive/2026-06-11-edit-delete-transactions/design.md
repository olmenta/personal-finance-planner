# Design — Edit and delete transactions

## Context

Transactions enter via manual `POST /transactions` and the import pipeline; both write signed `amount_cents` (expenses negative) and a `dedupe_hash` (salted for manual, unsalted for imports — `uq_txn_account_dedupe` unique per account). Budget and summary are computed from confirmed transactions on every read, never stored, so corrections need no recompute machinery. `GET /transactions` already filters to `status == "confirmed"`. The UI lists rows on the transactions screen; shadcn `dialog` and `dropdown-menu` are installed; `AddTransactionDialog` is the established dialog pattern.

## Goals / Non-Goals

**Goals:**

- In-place correction of amount, direction, category, description, and date for any confirmed transaction (manual or imported).
- Permanent single-row delete with one confirmation.
- Budget/summary/list views consistent immediately after either action, including when an edit moves a row across months.

**Non-Goals:**

- Editing or deleting staged import rows (the batch review owns those: confirm/discard).
- Bulk edit/delete, undo/restore, audit trail of changes (v1.x candidates).
- Splitting a transaction or moving it between accounts (single dev account in v1).

## Decisions

### D1 — PATCH with create-like semantics for amount

`PATCH /transactions/{id}` accepts `TransactionUpdate` — all fields optional: `amount_cents` (positive int) + `kind` (`expense|income`), `category_id`, `note`, `date`. The amount is expressed exactly like `TransactionCreate` (positive magnitude + direction) and signed server-side; when `amount_cents` is sent without `kind`, the row's current sign is kept. This keeps one mental model across create and edit instead of exposing raw signed cents in one place and magnitudes in another. `note: null` clears the description; omitted fields don't change. Alternative rejected: full PUT — forces the client to resend everything and risks clobbering concurrent changes for no benefit here.

### D2 — `dedupe_hash` is immutable after creation

Editing never recomputes the hash. For imported rows this is load-bearing: the hash is what makes re-importing the same bank file idempotent, so an edited imported row must keep its original identity or the next re-import would resurrect the pre-edit version as a "new" row. For manual rows the hash is salted per-row and only exists to satisfy the unique constraint, so recomputing buys nothing. Deleting an imported row does mean a later re-import of the same file stages that row again — accepted and predictable (the file is the source); the review step shows it before anything lands.

### D3 — Confirmed-only, owner-scoped, 404 otherwise

Both endpoints resolve the row by `id + user_id + status == "confirmed"`; anything else is 404 `transaction_not_found`. Staged rows are invisible outside the import review (same posture as `GET /transactions`), and a 404 — rather than 403/409 — avoids leaking other users' row ids. Category on edit is validated against the user's categories (404 `category_not_found`, same as create).

### D4 — Hard delete

`DELETE /transactions/{id}` removes the row; 204. No soft-delete column: nothing references confirmed transactions (FK only points the other way to `import_batches`), totals are computed on read, and GDPR favors actually deleting. The UI's single confirmation dialog is the safety net; undo can come later as v1.x without schema impact.

### D5 — Row actions menu + prefilled edit dialog

Each row on the transactions screen gets a trailing `more-horizontal` icon button opening a shadcn `DropdownMenu` (Edit / Delete — delete styled with `--expense`). Edit opens `EditTransactionDialog`, structurally a sibling of `AddTransactionDialog` (segmented Expense/Income, amount, description, category select, date) prefilled from the row; submit sends only the PATCH. Delete opens a small confirmation dialog ("Delete transaction?" with the row's description and amount; actions "Cancel" / "Delete transaction"). On success both mutations invalidate `["transactions"]` plus `["budget", m]` / `["summary", m]` for every affected month — for edits that's the old **and** new date's month. Alternative rejected: inline row editing — more layout shift and state for no speed gain over a prefilled dialog.

## Risks / Trade-offs

- [Editing an imported row then re-importing the file could double-count if hashes changed] → D2: hash immutable, re-import still collides and is skipped.
- [Deleted imported row reappears as staged on re-import] → accepted; the review step makes it visible and the user confirms or discards.
- [Concurrent edit of the same row (two tabs)] → last write wins; single-user v1, acceptable.
- [Hard delete is unrecoverable] → explicit confirmation dialog; undo deferred to v1.x.

## Migration Plan

1. Backend endpoints + schemas + tests (additive).
2. BFF route + api.ts helpers (dead until used).
3. UI menu + dialogs.
Rollback: revert webapp commit; backend endpoints additive; no migration.

## Open Questions

- None blocking.
