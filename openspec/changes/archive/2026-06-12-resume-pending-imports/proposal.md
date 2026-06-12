# Proposal — Resume pending imports (one staged batch at a time)

## Why

A staged import batch is reachable for exactly one dialog-lifetime: close the review without confirming or discarding and it becomes a ghost — invisible everywhere in the UI, yet occupying every dedupe hash, so every re-upload of the same file reports "0 ready, N duplicates skipped" with no explanation. This happened in practice with a real 257-row BBVA file and required manual API surgery to unblock.

## What Changes

- **One pending import at a time**: uploading while a staged batch exists returns 409 `import_pending` — the user finishes or discards the pending review first. This makes the silent duplicates-skipped trap structurally impossible.
- **Pending batch is queryable**: `GET /imports/pending` returns the user's staged batch (full review view) or 404 `no_pending_import`. Singular by design — the one-at-a-time rule means there is never a list.
- **Resume banner**: the transactions screen shows a banner whenever a pending import exists ("Import of *filename* awaiting review — N transactions") with a Resume action that reopens the review dialog at the review step, and the import dialog itself resumes the pending batch instead of offering a fresh upload.
- **Self-explanatory skip message**: the review summary distinguishes rows skipped as duplicates of confirmed transactions from rows in the file that were all already imported (the only remaining skip cases once the pending trap is gone).

## Capabilities

### New Capabilities

(none — this extends existing capabilities)

### Modified Capabilities

- `statement-import`: new requirements — single pending batch invariant (upload 409s while one exists) and the pending-batch read endpoint.
- `bff-proxy`: proxied-routes requirement gains `GET /api/imports/pending`.
- `webapp-server-state`: statement-import flow requirement gains the resume path — pending banner on the transactions screen, dialog resumes instead of re-uploading, 409 surfaced as an actionable message.

## Impact

- `backend/app/routers/imports.py`: pending lookup on POST (409) + new `GET /imports/pending`; no schema migration (`status = "staged"` already exists, the invariant is enforced at write time).
- `backend/tests/test_imports.py`: 409 on second upload, pending fetch, 404 when none, confirm/discard clears the invariant.
- `webapp/src/app/api/imports/pending/route.ts`; `api.ts` `fetchPendingImport`; `ImportBankTransactionsDialog` resume mode; transactions page banner under a `["imports","pending"]` query invalidated by upload/confirm/discard.
- Route-ordering note: `GET /imports/pending` must be declared before `GET /imports/{batch_id}` in FastAPI.
