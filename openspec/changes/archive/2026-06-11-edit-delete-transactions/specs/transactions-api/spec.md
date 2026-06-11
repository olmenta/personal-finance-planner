# transactions-api Delta Specification

## ADDED Requirements

### Requirement: Update a transaction

The API SHALL expose `PATCH /transactions/{id}` to partially update a confirmed transaction owned by the user. Editable fields: `amount_cents` (positive magnitude) with `kind` (`expense` | `income`) signing it server-side — when `amount_cents` is sent without `kind`, the row's current sign is kept; `category_id` (validated against the user's categories); `note` (`null` clears the description); `payee` (trimmed name resolved find-or-create against the user's payees, empty string clears it); and `date`. Omitted fields SHALL stay unchanged, and the row's `dedupe_hash` SHALL remain immutable so re-imports keep colliding with edited rows. Budget and summary reads SHALL reflect the edit immediately. A transaction that does not exist, belongs to another user, or is not `confirmed` SHALL return 404 with code `transaction_not_found`.

#### Scenario: Amount and category corrected

- **WHEN** a confirmed expense of −12,49 € is patched with `amount_cents = 1499` and a different `category_id`
- **THEN** the row stores `amount_cents = -1499` under the new category, and the month's budget `spent_cents` reflects the new amount on the next read

#### Scenario: Direction flipped

- **WHEN** a confirmed expense is patched with `kind = "income"` and `amount_cents = 5000`
- **THEN** the row stores `amount_cents = +5000`

#### Scenario: Imported row keeps its dedupe identity

- **WHEN** an imported row's category and description are edited and the same bank file is uploaded again
- **THEN** the re-import reports that row as a skipped duplicate and the edit survives

#### Scenario: Payee corrected

- **WHEN** a confirmed transaction is patched with `payee = "Mercadona"` and later with `payee = ""`
- **THEN** the row first references the (possibly newly created) Mercadona payee and afterwards no payee at all

#### Scenario: Staged row not editable here

- **WHEN** `PATCH /transactions/{id}` targets a staged import row
- **THEN** the API returns 404 with code `transaction_not_found`

#### Scenario: Unknown category rejected

- **WHEN** a patch carries a `category_id` that does not belong to the user
- **THEN** the API returns 404 with code `category_not_found` and the row is unchanged

### Requirement: Delete a transaction

The API SHALL expose `DELETE /transactions/{id}` to permanently remove a confirmed transaction owned by the user, returning 204. Budget and summary reads SHALL reflect the removal immediately. The same 404 `transaction_not_found` rule as update SHALL apply to missing, foreign, or staged rows.

#### Scenario: Deleted row leaves the totals

- **WHEN** a confirmed June expense is deleted
- **THEN** `GET /transactions?month=2026-06` no longer includes it and the June budget `spent_cents` shrinks accordingly

#### Scenario: Deleting an imported row allows it back on re-import

- **WHEN** an imported row is deleted and the same bank file is uploaded again
- **THEN** that row is staged again for review instead of being skipped
