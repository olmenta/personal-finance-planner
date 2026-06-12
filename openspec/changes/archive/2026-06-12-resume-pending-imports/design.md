# Design — Resume pending imports

## Context

`POST /imports` stages a batch; the only handle on it is the `ImportBatchView` held in `ImportBankTransactionsDialog`'s React state. Closing the dialog drops that handle: the batch stays `staged` indefinitely, its rows are excluded from every read surface (by design), and its unsalted dedupe hashes block any re-upload of the same file ("0 ready, N duplicates skipped" with no cause shown). Nothing prevents multiple staged batches accumulating — a real session produced one 257-row ghost plus a 0-row husk. The backend already has the full lifecycle (`staged | confirmed | discarded`) and a per-batch view endpoint; what's missing is discoverability and an invariant.

## Goals / Non-Goals

**Goals:**

- A staged batch is always one click away: visible on the transactions screen, resumable into the same review UI.
- At most one staged batch per user, enforced at upload time — the ghost-batch state becomes unrepresentable.
- The duplicates-skipped message explains itself in the cases that remain.

**Non-Goals:**

- Multiple concurrent pending imports (one bank file at a time is the honest v1 workflow; revisit if multi-account lands).
- Persisting review progress (category/payee edits in the dialog) across sessions — resume restores the staged batch as the server knows it.
- Auto-discard or auto-confirm of stale batches — destruction stays explicit.
- Backfill/cleanup migration for pre-existing ghost batches (dev-only data; the invariant prevents new ones).

## Decisions

### D1 — Invariant at the write, not a constraint in the schema

`POST /imports` SHALL first check for an existing batch with `status = "staged"` for the user and return 409 `import_pending` (with the pending batch id in the error detail) instead of staging a second one. App-level enforcement is enough: single-user v1, one code path writes batches, and a partial unique index on `(user_id) WHERE status = 'staged'` can be added later without API change if concurrent writers ever appear. Alternative rejected: auto-discarding the previous staged batch on upload — silently destroys review-in-progress, fights the "nothing lands or dies unseen" posture of the review step.

### D2 — `GET /imports/pending`, singular

One endpoint returning the user's staged batch as a full `ImportBatchView` (same shape the dialog already consumes), 404 `no_pending_import` when none. Singular because D1 makes plurality impossible — no list endpoint, no pagination, no client-side "pick the right batch" logic. Declared before `GET /imports/{batch_id}` so FastAPI doesn't route "pending" as a batch id. Alternative rejected: `GET /imports?status=staged` list — generic surface for a cardinality the system forbids.

### D3 — Banner on the transactions screen + resuming dialog

The transactions screen queries `["imports", "pending"]` (`fetchPendingImport`, returning `null` on 404) and, when a batch exists, renders a banner above the list: filename, row count, and a "Resume review" action that opens `ImportBankTransactionsDialog` directly in its review step with the fetched batch. The dialog's own open path also checks the query first: if a pending batch exists, it shows the review step instead of the source picker (with discard available, as today). Upload, confirm, and discard all invalidate `["imports", "pending"]`. The banner uses the standard panel style with an info tone — not the coach voice, not a dismissible toast (it must persist until the user acts; persistence is the point).

### D4 — Skip message explains its remaining causes

With ghosts impossible, "skipped duplicates" can only mean collisions with confirmed transactions. The review summary copy changes from a bare count to "N rows already imported — skipped"; the all-skipped case ("0 ready") gets an explicit empty state inviting the user to check the transactions list rather than implying failure. No new data is needed — the distinction is total once D1 holds.

### D5 — 409 surfaced as a path forward, not an error wall

If the dialog ever does hit 409 `import_pending` (race: banner stale, second tab), it swaps to the review step by fetching the pending batch — the error becomes navigation. The machine-readable code keeps i18n-readiness like every other error.

## Risks / Trade-offs

- [User wants to import two different banks back-to-back] → finish or discard the first review; the review takes seconds and the constraint is visible, not mysterious.
- [Banner adds a permanent query to the transactions screen] → one tiny request, cached under TanStack Query, invalidated only by import mutations.
- [Pre-existing ghost batches predate the invariant] → none can exist in prod (not launched); dev DBs get cleaned by hand once, after which D1 holds.
- [Race between two uploads] → second one 409s via the app-level check; partial unique index is the documented escalation if it ever matters.

## Migration Plan

1. Backend: 409 guard on POST + `GET /imports/pending` + tests (additive).
2. BFF route + `fetchPendingImport`.
3. Banner + dialog resume mode + skip-copy change.
Rollback: revert webapp commit; backend guard removal restores old behavior; no migration.

## Open Questions

- None blocking.
