# transactions-api Delta Specification

## MODIFIED Requirements

### Requirement: Create a manual transaction

The API SHALL expose `POST /transactions` accepting `amount_cents` (positive integer), `category_id`, optional `payee` (trimmed name ≤120 chars, resolved find-or-create against the user's payees), optional `note`, and optional `date` defaulting to today. The created transaction SHALL have `source = "manual"` and `status = "confirmed"`. Validation errors SHALL return machine-readable error codes (i18n-ready, no human-language coupling).

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
