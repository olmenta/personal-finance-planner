# transactions-api Specification

## Purpose

HTTP API surface for transactions: creating manual entries and listing transactions with month filtering, returning machine-readable error codes.

## Requirements

### Requirement: Create a manual transaction

The API SHALL expose `POST /transactions` accepting `amount_cents` (positive integer), `category_id` (required for expenses, 422 `category_required` when missing; optional for income — uncategorized income funds To Be Assigned), optional `payee` (trimmed name ≤120 chars, resolved find-or-create against the user's payees), optional `note`, and optional `date` defaulting to today. The created transaction SHALL have `source = "manual"` and `status = "confirmed"`. Validation errors SHALL return machine-readable error codes (i18n-ready, no human-language coupling).

#### Scenario: Minimal entry

- **WHEN** a client posts `{ "amount_cents": 1249, "category_id": "<id>" }`
- **THEN** the API returns 201 with the transaction dated today, source `manual`, status `confirmed`, and no payee

#### Scenario: Entry with payee

- **WHEN** a client posts an entry with `payee = "Mercadona"`
- **THEN** the transaction references the user's (possibly newly created) Mercadona payee

#### Scenario: Invalid amount

- **WHEN** a client posts `amount_cents = 0` or a negative value
- **THEN** the API returns 422 with a machine-readable error code

#### Scenario: Unknown category

- **WHEN** a client posts a `category_id` that does not exist
- **THEN** the API returns 404 with a machine-readable error code

#### Scenario: Income without category

- **WHEN** a client posts `{ "amount_cents": 240000, "kind": "income" }` with no `category_id`
- **THEN** the API returns 201 with a positive uncategorized transaction

#### Scenario: Expense requires category

- **WHEN** a client posts an expense with no `category_id`
- **THEN** the API returns 422 with code `category_required`

### Requirement: List transactions

The API SHALL expose `GET /transactions` returning confirmed transactions only, ordered by date descending, filterable by month (`?month=YYYY-MM`), with each row carrying `payee_id` and `payee_name` (null when the transaction has no payee). Staged transactions (pending import review) SHALL be visible only through the import batch view, never in this list.

#### Scenario: Month filter

- **WHEN** a client requests `GET /transactions?month=2026-06`
- **THEN** only transactions dated in June 2026 are returned, newest first

#### Scenario: Staged rows excluded

- **WHEN** an import batch has staged rows for the requested month
- **THEN** `GET /transactions?month=` does not include them until the batch is confirmed

#### Scenario: Payee joined into the row

- **WHEN** a listed transaction references a payee
- **THEN** the row includes the payee's id and name

### Requirement: Update a transaction

The API SHALL expose `PATCH /transactions/{id}` to partially update a confirmed transaction owned by the user. Editable fields: `amount_cents` (positive magnitude) with `kind` (`expense` | `income`) signing it server-side — when `amount_cents` is sent without `kind`, the row's current sign is kept; `category_id` (validated against the user's categories; an **explicit `null` clears the category** — un-marking a refund so the inflow counts as income again — while an absent field leaves it untouched); `note` (`null` clears the description); `payee` (trimmed name resolved find-or-create against the user's payees, empty string clears it); and `date`. Omitted fields SHALL stay unchanged, and the row's `dedupe_hash` SHALL remain immutable so re-imports keep colliding with edited rows. Budget and summary reads SHALL reflect the edit immediately. A transaction that does not exist, belongs to another user, or is not `confirmed` SHALL return 404 with code `transaction_not_found`.

#### Scenario: Amount and category corrected

- **WHEN** a confirmed expense of −12,49 € is patched with `amount_cents = 1499` and a different `category_id`
- **THEN** the row stores `amount_cents = -1499` under the new category, and the month's budget `spent_cents` reflects the new amount on the next read

#### Scenario: Direction flipped

- **WHEN** a confirmed expense is patched with `kind = "income"` and `amount_cents = 5000`
- **THEN** the row stores `amount_cents = +5000`

#### Scenario: Null category un-marks a refund

- **WHEN** a categorized +12,50 € inflow is patched with `category_id: null`
- **THEN** the row becomes uncategorized and counts as income on the next budget and summary reads

#### Scenario: Absent category stays untouched

- **WHEN** a categorized inflow is patched changing only the note
- **THEN** its category is unchanged

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
