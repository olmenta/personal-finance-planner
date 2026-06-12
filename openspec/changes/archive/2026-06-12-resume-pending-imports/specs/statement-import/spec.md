# statement-import Delta Specification

## ADDED Requirements

### Requirement: Single pending import batch

The backend SHALL allow at most one `staged` import batch per user. `POST /imports` SHALL return 409 with code `import_pending` (carrying the pending batch id) while a staged batch exists, instead of staging a second one. Confirming or discarding the pending batch SHALL clear the invariant. This makes orphaned staged batches — invisible rows blocking re-imports through dedupe collisions — unrepresentable.

#### Scenario: Second upload blocked

- **WHEN** a user with a staged batch uploads another statement file
- **THEN** the API returns 409 with code `import_pending` and the existing batch id, and no new batch or rows are created

#### Scenario: Upload allowed after discard

- **WHEN** the user discards their pending batch and uploads again
- **THEN** the upload stages normally

### Requirement: Pending batch endpoint

The API SHALL expose `GET /imports/pending` returning the user's staged batch as a full batch view (same shape as `GET /imports/{id}`, staged rows included), or 404 with code `no_pending_import` when none exists. The endpoint is singular by design — the single-pending invariant means there is never a list.

#### Scenario: Pending batch fetched

- **WHEN** the user has a staged batch and requests `GET /imports/pending`
- **THEN** the response is the batch view with its staged rows, suggestions, and skip count

#### Scenario: No pending batch

- **WHEN** the user has no staged batch
- **THEN** the API returns 404 with code `no_pending_import`
