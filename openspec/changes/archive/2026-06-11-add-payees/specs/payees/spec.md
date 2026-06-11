# payees Delta Specification

## ADDED Requirements

### Requirement: Payees are born from transaction writes

The backend SHALL persist payees per user and resolve them on transaction writes: when a transaction is created (or edited) with a `payee` name, the backend SHALL reuse the user's existing payee matching case-insensitively on the trimmed name, or create it. There SHALL be no separate payee-creation endpoint in v1, and one payee entity SHALL serve both directions — "Payee" on expenses and "Payer" on incomes is presentation only. Imported transactions SHALL keep `payee_id` null (bank descriptions are not auto-promoted to payees).

#### Scenario: New payee created on first use

- **WHEN** the user adds an expense with payee "Mercadona" for the first time
- **THEN** a payee "Mercadona" exists for the user and the transaction references it

#### Scenario: Case-insensitive reuse

- **WHEN** a later transaction is written with payee "MERCADONA"
- **THEN** no new payee is created and the transaction references the existing "Mercadona"

#### Scenario: Imported rows carry no payee

- **WHEN** a bank statement import is confirmed
- **THEN** its transactions have `payee_id = null`

### Requirement: Payee list with category memory

The API SHALL expose `GET /payees` returning the user's payees ordered by most recent use, each with `id`, `name`, and `last_category_id` — the category of the user's most recent confirmed transaction with that payee, or null when none exists.

#### Scenario: Memory follows latest use

- **WHEN** the user's last "Mercadona" transaction was categorized "Supermercado"
- **THEN** `GET /payees` lists Mercadona with that category id as `last_category_id`

#### Scenario: Fresh payee has no memory

- **WHEN** a payee exists only on an uncategorized transaction
- **THEN** its `last_category_id` is null
