# data-model Delta Specification

## MODIFIED Requirements

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
