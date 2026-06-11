# data-model Delta Specification

## ADDED Requirements

### Requirement: Payees

The backend SHALL persist a `Payee` entity (`id`, `user_id`, `name`) with a per-user case-insensitive unique constraint on the name, and `transactions.payee_id` SHALL be a nullable foreign key to it. The schema change SHALL be applied through an Alembic migration with a working downgrade.

#### Scenario: Migration adds the table and FK

- **WHEN** `uv run alembic upgrade head` runs on a database at the previous revision
- **THEN** the `payees` table exists and `transactions.payee_id` references it

#### Scenario: Duplicate name rejected case-insensitively

- **WHEN** a payee "mercadona" is inserted for a user who already has "Mercadona"
- **THEN** the insert fails the unique constraint
