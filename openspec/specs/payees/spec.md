# payees Specification

## Purpose

The payee entity contract: one per-user entity for "who was paid" (expense) and "who paid" (income), born from transaction writes rather than its own CRUD, listed with last-used-category memory to power autocomplete and category prefill.

## Requirements

### Requirement: Payees are born from transaction writes

The backend SHALL persist payees per user and resolve them on transaction writes: when a transaction is created (or edited) with a `payee` name, the backend SHALL reuse the user's existing payee matching case-insensitively on the trimmed name, or create it. There SHALL be no public payee-creation endpoint in v1, and one payee entity SHALL serve both directions — "Payee" on expenses and "Payer" on incomes is presentation only. The onboarding finalize flow MAY seed payees the user explicitly accepted on the onboarding review screen, using the same case-insensitive resolution. Imported transactions SHALL NOT auto-promote raw bank descriptions to payees; they MAY reference an AI-proposed cleaned payee that is staged for review before confirm, and the categorization review flow MAY apply payees the user accepted. Discarding an import batch SHALL remove payees no other transaction references.

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
- **THEN** payees referenced by no remaining transaction are deleted

#### Scenario: Onboarding seeds accepted payees

- **WHEN** the user accepts "Netflix" and "Company X Salary" on the onboarding review screen and finalizes
- **THEN** both exist as payees for the user (reusing any case-insensitive match), available to autocomplete and import suggestions before any transaction references them

### Requirement: Payee list with category memory

The API SHALL expose `GET /payees` returning the user's payees ordered by most recent use, each with `id`, `name`, and `last_category_id` — the category of the user's most recent confirmed transaction with that payee, or null when none exists.

#### Scenario: Memory follows latest use

- **WHEN** the user's last "Mercadona" transaction was categorized "Supermercado"
- **THEN** `GET /payees` lists Mercadona with that category id as `last_category_id`

#### Scenario: Fresh payee has no memory

- **WHEN** a payee exists only on an uncategorized transaction
- **THEN** its `last_category_id` is null
