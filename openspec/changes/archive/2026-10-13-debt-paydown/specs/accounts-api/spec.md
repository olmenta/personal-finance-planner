## ADDED Requirements

### Requirement: Convert a credit account into an installment loan

The API SHALL expose `POST /accounts/{id}/convert-to-loan` with `installment_cents > 0`, `installments_left ≥ 1`, `next_month`, optional `day` and optional rate. It SHALL apply the debts capability's conversion in one transaction. Converting a non-credit or archived account SHALL return 409 `not_convertible`. An unknown or foreign account SHALL return 404 `account_not_found`. The accounts screen SHALL offer the action on credit accounts as "This is a loan, not a card".

#### Scenario: Only credit accounts convert

- **WHEN** a client converts a bank account
- **THEN** the API returns 409 `not_convertible`
