## MODIFIED Requirements

### Requirement: Payees are born from transaction writes

The backend SHALL persist payees per user and resolve them on transaction writes: when a transaction is created (or edited) with a `payee` name, the backend SHALL reuse the user's existing payee matching case-insensitively on the trimmed name, or create it. There SHALL be no public payee-creation endpoint in v1, and one payee entity SHALL serve both directions — "Payee" on expenses and "Payer" on incomes is presentation only. Income schedule writes SHALL resolve their `payer` name the same way and reference the resulting payee (see income-schedules). The onboarding finalize flow MAY seed payees the user explicitly accepted on the onboarding review screen, using the same case-insensitive resolution. Imported transactions SHALL NOT auto-promote raw bank descriptions to payees; they MAY reference an AI-proposed cleaned payee that is staged for review before confirm, and the categorization review flow MAY apply payees the user accepted. Discarding an import batch SHALL remove payees that no other transaction and no income schedule references.

#### Scenario: New payee created on first use

- **WHEN** the user adds an expense with payee "Mercadona" for the first time
- **THEN** a payee "Mercadona" exists for the user and the transaction references it

#### Scenario: Case-insensitive reuse

- **WHEN** a later transaction is written with payee "MERCADONA"
- **THEN** no new payee is created and the transaction references the existing "Mercadona"

#### Scenario: Imported rows carry reviewed payees, not raw strings

- **WHEN** a bank statement import is confirmed after review
- **THEN** its transactions reference the AI-proposed cleaned payees shown during review (null where none was proposed), never the raw bank description

#### Scenario: Discarded batch leaves no orphan payees

- **WHEN** an import batch whose rows created new payees is discarded
- **THEN** payees referenced by no remaining transaction and no income schedule are deleted

#### Scenario: Onboarding seeds accepted payees

- **WHEN** the user accepts "Netflix" and "Company X Salary" on the onboarding review screen and finalizes
- **THEN** both exist as payees for the user (reusing any case-insensitive match), available to autocomplete and import suggestions before any transaction references them

#### Scenario: Income schedule creates its payer

- **WHEN** the user saves an income schedule with payer "Inquilino Piso" and no such payee exists
- **THEN** a payee "Inquilino Piso" exists for the user, the schedule references it, and it appears in `GET /payees`

#### Scenario: Schedule-referenced payee survives an import discard

- **WHEN** an import batch created the payee "Acme SL", an income schedule then referenced it, and the batch is discarded
- **THEN** the payee "Acme SL" is kept
