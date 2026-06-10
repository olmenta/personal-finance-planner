# Spec — transactions-api

## ADDED Requirements

### Requirement: Create a manual transaction

The API SHALL expose `POST /transactions` accepting `amount_cents` (positive integer), `category_id`, optional `note`, and optional `date` defaulting to today. The created transaction SHALL have `source = "manual"` and `status = "confirmed"`. Validation errors SHALL return machine-readable error codes (i18n-ready, no human-language coupling).

#### Scenario: Minimal entry

- **WHEN** a client posts `{ "amount_cents": 1249, "category_id": "<id>" }`
- **THEN** the API returns 201 with the transaction dated today, source `manual`, status `confirmed`

#### Scenario: Invalid amount

- **WHEN** a client posts `amount_cents = 0` or a negative value
- **THEN** the API returns 422 with a machine-readable error code

#### Scenario: Unknown category

- **WHEN** a client posts a `category_id` that does not exist
- **THEN** the API returns 404 with a machine-readable error code

### Requirement: List transactions

The API SHALL expose `GET /transactions` returning transactions ordered by date descending, filterable by month (`?month=YYYY-MM`).

#### Scenario: Month filter

- **WHEN** a client requests `GET /transactions?month=2026-06`
- **THEN** only transactions dated in June 2026 are returned, newest first
