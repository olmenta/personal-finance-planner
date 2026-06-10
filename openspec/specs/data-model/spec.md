# data-model Specification

## Purpose

Persistent backend data model for the v1 personal finance planner: core entities, integer-cent monetary storage, transaction integrity guarantees, development seed data, and the rule that derived budget values are computed at read time rather than stored.

## Requirements

### Requirement: Core schema with integer-cent amounts

The backend SHALL persist the v1 core entities — User, Account, CategoryGroup, Category, Transaction, BudgetMonth, BudgetAssignment — with all monetary amounts stored as integer cents and currency fixed to EUR (column present for future multi-currency). Schema changes SHALL be applied through Alembic migrations.

#### Scenario: Amounts round-trip as cents

- **WHEN** a transaction of 12,49 € is stored
- **THEN** the database row holds `amount_cents = 1249` and `currency = "EUR"`
- **AND** reading it back yields exactly 1249 (no float drift)

#### Scenario: Migrations create the schema

- **WHEN** `uv run alembic upgrade head` runs against an empty database
- **THEN** all core tables exist with their constraints

### Requirement: Transaction integrity

Transactions SHALL record their `source` (v1: `manual`), a `status` of `staged` or `confirmed`, and a `dedupe_hash` computed from `(account, date, amount, description)` with a unique constraint per account. Manual entries SHALL default to `confirmed`.

#### Scenario: Duplicate insert rejected

- **WHEN** two transactions with identical account, date, amount and description are inserted
- **THEN** the second insert fails the unique `dedupe_hash` constraint

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
