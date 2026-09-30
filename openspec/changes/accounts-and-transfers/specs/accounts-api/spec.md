# accounts-api Delta Specification

## ADDED Requirements

### Requirement: Account CRUD

The API SHALL expose `GET /accounts` (the user's accounts with `id`, `name`, `type`, `institution`, derived `balance_cents`, `archived`), `POST /accounts` (`name`, `type` of `cash | bank | credit`, optional `institution`, optional `opening_balance_cents`), and `PATCH /accounts/{id}` (rename, `institution`, `archived`). There SHALL be no account delete — archiving hides the account from pickers while its transactions keep counting. A duplicate active account name for the user SHALL return 409 `account_exists`; an unknown or foreign account SHALL return 404 `account_not_found`.

#### Scenario: Create a bank account

- **WHEN** the user creates `{name: "Banco B", type: "bank"}`
- **THEN** `GET /accounts` lists it with `balance_cents = 0`

#### Scenario: Archive hides but keeps counting

- **WHEN** an account with transactions is archived
- **THEN** it leaves the account pickers, its transactions remain confirmed, and the all-time balance is unchanged

### Requirement: Derived account balance

An account's `balance_cents` SHALL be the sum of its confirmed transactions' signed amounts — never a stored column. Staged rows SHALL NOT count.

#### Scenario: Balance follows transactions

- **WHEN** an account has confirmed transactions of +2.000,00 € and −350,00 €
- **THEN** `GET /accounts` reports `balance_cents = 165000` for it

### Requirement: Opening balance funds To Be Assigned

When `opening_balance_cents` is provided at creation, the backend SHALL write one confirmed, uncategorized transaction in the new account, dated the creation day, with `source = "opening_balance"` and a salted dedupe hash. A positive opening balance therefore counts as income (To Be Assigned); a negative one (a credit card carrying debt) lowers To Be Assigned by the same amount.

#### Scenario: Positive opening balance is income

- **WHEN** "Banco B" is created with `opening_balance_cents = 50000`
- **THEN** the month's `income_cents` rises by 50000 and the account balance is 500,00 €

#### Scenario: Credit card debt lowers TBA

- **WHEN** "Tarjeta Visa" is created with `type = "credit"` and `opening_balance_cents = -34000`
- **THEN** the account balance is −340,00 € and the month's To Be Assigned drops by 340,00 €

### Requirement: Main account default

The user's oldest active account SHALL be the main account. Transaction writes that omit `account_id` SHALL land in it; clients listing accounts SHALL be able to identify it (first in creation order).

#### Scenario: Omitted account falls back to main

- **WHEN** a manual expense is created without `account_id`
- **THEN** it lands in the user's oldest active account
