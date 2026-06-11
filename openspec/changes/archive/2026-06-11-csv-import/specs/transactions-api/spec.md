# transactions-api Delta Specification

## MODIFIED Requirements

### Requirement: List transactions

The API SHALL expose `GET /transactions` returning confirmed transactions only, ordered by date descending, filterable by month (`?month=YYYY-MM`). Staged transactions (pending import review) SHALL be visible only through the import batch view, never in this list.

#### Scenario: Month filter

- **WHEN** a client requests `GET /transactions?month=2026-06`
- **THEN** only transactions dated in June 2026 are returned, newest first

#### Scenario: Staged rows excluded

- **WHEN** an import batch has staged rows for the requested month
- **THEN** `GET /transactions?month=` does not include them until the batch is confirmed
