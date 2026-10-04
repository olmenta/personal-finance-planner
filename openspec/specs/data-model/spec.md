# data-model Specification

## Purpose

Persistent backend data model for the v1 personal finance planner: core entities, integer-cent monetary storage, transaction integrity guarantees, development seed data, and the rule that derived budget values are computed at read time rather than stored.

## Requirements

### Requirement: Core schema with integer-cent amounts

The backend SHALL persist the v1 core entities — User, Account, CategoryGroup, Category, Transaction, BudgetMonth, BudgetAssignment — with all monetary amounts stored as integer cents and currency fixed to EUR (column present for future multi-currency). `Account.type` SHALL accept `cash`, `bank`, and `credit` (credit cards: balances naturally negative); `Account.payment_day` (nullable integer 1–31) SHALL hold a credit card's charge day. `Category.payment_account_id` (nullable, unique, FK to Account) SHALL mark a credit card's system payment category, and `CategoryGroup.system` (boolean, default false) SHALL mark system-managed groups such as "Tarjetas de crédito". Schema changes SHALL be applied through Alembic migrations.

#### Scenario: Amounts round-trip as cents

- **WHEN** a transaction of 12,49 € is stored
- **THEN** the database row holds `amount_cents = 1249` and `currency = "EUR"`
- **AND** reading it back yields exactly 1249 (no float drift)

#### Scenario: Migrations create the schema

- **WHEN** `uv run alembic upgrade head` runs against an empty database
- **THEN** all core tables exist with their constraints

#### Scenario: Credit account persists

- **WHEN** an account with `type = "credit"` is created
- **THEN** it round-trips with that type and may hold a negative derived balance

#### Scenario: Payment category links its card

- **WHEN** a credit account is created
- **THEN** exactly one category references it through `payment_account_id`, inside a group with `system = true`

### Requirement: Transaction integrity

Transactions SHALL record their `source` (`manual`, `import_bbva`, `import_sabadell`, `import_custom`, `opening_balance`), a `status` of `staged` or `confirmed`, and a `dedupe_hash` computed from `(account, date, amount, external_ref or description)` with a unique constraint per account. Manual entries and opening balances SHALL default to `confirmed` and salt their hash per row (repeated identical manual entries are legitimate); imported rows SHALL hash without salt so identical bank rows collide. Transactions SHALL carry a nullable indexed `transfer_pair_id`: two rows sharing it form a transfer pair (equal magnitude, opposite signs, no category, no payee), applied through an Alembic migration with a working downgrade.

#### Scenario: Duplicate insert rejected

- **WHEN** two transactions with identical account, date, amount and description are inserted with unsalted hashes
- **THEN** the second insert fails the unique `dedupe_hash` constraint

#### Scenario: Imported row records its origin

- **WHEN** a row is staged from a BBVA import
- **THEN** it carries `source = "import_bbva"` and the `import_batch_id` of its batch

#### Scenario: Migration adds the pair column

- **WHEN** `uv run alembic upgrade head` runs on a database at the previous revision
- **THEN** `transactions.transfer_pair_id` exists, nullable and indexed

### Requirement: Import batches

The backend SHALL persist an `ImportBatch` entity (`id`, `user_id`, `account_id`, `source`, `filename`, `status` of `staged | confirmed | discarded`, `row_count`, `skipped_duplicates`, `created_at`), and `transactions.import_batch_id` SHALL be a real foreign key to it. The schema change SHALL be applied through an Alembic migration with a working downgrade.

#### Scenario: Migration adds the table

- **WHEN** `uv run alembic upgrade head` runs on a database at the previous revision
- **THEN** the `import_batches` table exists and `transactions.import_batch_id` references it

### Requirement: Payees

The backend SHALL persist a `Payee` entity (`id`, `user_id`, `name`) with a per-user case-insensitive unique constraint on the name, and `transactions.payee_id` SHALL be a nullable foreign key to it. The schema change SHALL be applied through an Alembic migration with a working downgrade.

#### Scenario: Migration adds the table and FK

- **WHEN** `uv run alembic upgrade head` runs on a database at the previous revision
- **THEN** the `payees` table exists and `transactions.payee_id` references it

#### Scenario: Duplicate name rejected case-insensitively

- **WHEN** a payee "mercadona" is inserted for a user who already has "Mercadona"
- **THEN** the insert fails the unique constraint

### Requirement: Seeded development data

The backend SHALL provide a seed script that creates the single development user, a default cash account, and the default Spanish category tree (groups: Vivienda, Comida, Transporte, Estilo de vida) as the stand-in until AI onboarding generates personalized trees. Seeding SHALL be idempotent.

#### Scenario: Seed is idempotent

- **WHEN** the seed script runs twice
- **THEN** the category tree and dev user exist exactly once

### Requirement: Derived budget values are computed, not stored

Category available balance (`assigned + rollover − spent`) and the month's to-be-assigned (`income − Σ assigned`) SHALL be derived at read time from transactions and assignments, never persisted as columns.

#### Scenario: Available reflects a new transaction immediately

- **WHEN** a category has 120,00 € assigned, 32,00 € rollover and a new 138,00 € expense is recorded
- **THEN** the next budget read reports 14,00 € available for that category with no extra write

### Requirement: Category kind and payment schedules persisted

Categories SHALL carry a non-null `kind` (`flexible` | `scheduled` | `savings`, default `flexible`). A `payment_schedules` table SHALL persist schedules (`id`, `user_id`, `category_id` FK, `name`, `amount_cents`, `pattern`, `months`, `month`, `every_n`, `start_month`, `count`, `once_month`, `day`, `estimated`), indexed by `(user_id, category_id)`, applied through an Alembic migration with a working downgrade. Schedules SHALL hold no derived amounts — normal and catch-up amounts are computed on read.

#### Scenario: Migration adds kind and schedules

- **WHEN** `uv run alembic upgrade head` runs on a database at the previous revision
- **THEN** `categories.kind` exists with default `flexible` and the `payment_schedules` table exists

#### Scenario: Downgrade removes them

- **WHEN** the migration is downgraded
- **THEN** `categories.kind` and `payment_schedules` are gone and the rest of the schema is unchanged
