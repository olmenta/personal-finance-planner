# data-model Delta Specification

## ADDED Requirements

### Requirement: Import batches

The backend SHALL persist an `ImportBatch` entity (`id`, `user_id`, `account_id`, `source`, `filename`, `status` of `staged | confirmed | discarded`, `row_count`, `skipped_duplicates`, `created_at`), and `transactions.import_batch_id` SHALL be a real foreign key to it. The schema change SHALL be applied through an Alembic migration with a working downgrade.

#### Scenario: Migration adds the table

- **WHEN** `uv run alembic upgrade head` runs on a database at the previous revision
- **THEN** the `import_batches` table exists and `transactions.import_batch_id` references it

## MODIFIED Requirements

### Requirement: Transaction integrity

Transactions SHALL record their `source` (`manual`, `import_bbva`, `import_sabadell`, `import_custom`), a `status` of `staged` or `confirmed`, and a `dedupe_hash` computed from `(account, date, amount, external_ref or description)` with a unique constraint per account. Manual entries SHALL default to `confirmed` and salt their hash per row (repeated identical manual entries are legitimate); imported rows SHALL hash without salt so identical bank rows collide.

#### Scenario: Duplicate insert rejected

- **WHEN** two transactions with identical account, date, amount and description are inserted with unsalted hashes
- **THEN** the second insert fails the unique `dedupe_hash` constraint

#### Scenario: Imported row records its origin

- **WHEN** a row is staged from a BBVA import
- **THEN** it carries `source = "import_bbva"` and the `import_batch_id` of its batch
