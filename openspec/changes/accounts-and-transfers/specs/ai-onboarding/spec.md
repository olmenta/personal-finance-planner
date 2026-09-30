# ai-onboarding Delta Specification

## MODIFIED Requirements

### Requirement: Prompt-config-driven interview turns

The interview SHALL be driven by a versioned prompt configuration file in the repo declaring the questions (five YNAB-style phases: household & income — including expected monthly income, the approximate day it arrives, **which bank accounts and credit cards the user has** (names, as free text or common-bank checkboxes), and an **optional, skippable** question for the current balance of the primary bank account —, housing & utilities, true expenses, lifestyle & subscriptions, debt — where credit cards map to accounts and loans map to debt-paydown categories), the tone, and the extraction-field schema. Changing questions or extracted fields SHALL require only editing this configuration. `POST /onboarding/messages` SHALL send the user's reply, invoke the LLM through LiteLLM with structured output, and return a turn containing: the assistant `message`, an `input_kind` of `chips`, `checkboxes`, `text`, or `money` with `options` where applicable, and `done`. Extracted answer deltas SHALL be validated against the declared schema — unknown fields SHALL be dropped and logged, never persisted.

#### Scenario: Turn returns quick-input hints

- **WHEN** the interview reaches the utilities question
- **THEN** the turn carries `input_kind: "checkboxes"` with utility options so the user answers by tapping

#### Scenario: Free text understood

- **WHEN** the user types "my flat is fully electric, no gas" instead of using the checkboxes
- **THEN** the extracted utilities reflect electricity without gas and the interview moves on

#### Scenario: Accounts extracted from the interview

- **WHEN** the user answers "BBVA y una cuenta de Sabadell, y la Visa del BBVA"
- **THEN** the extraction carries two bank account names and one credit card name under the declared accounts fields

#### Scenario: Opening balance is skippable

- **WHEN** the interview asks for the primary bank account's current balance and the user declines or skips
- **THEN** the interview moves on, no balance field is extracted, and the rest of the setup is unaffected

#### Scenario: Questions change without code changes

- **WHEN** a new question is added to the prompt configuration with a new field in its extraction schema
- **THEN** the interview asks it and persists the new field with no backend code modification, under a bumped prompt version

#### Scenario: Hallucinated field dropped

- **WHEN** the model returns an extraction key not declared in the schema
- **THEN** the key is dropped and logged and the rest of the delta is kept

### Requirement: Generated setup proposal on completion

When the interview completes, the turn SHALL carry `done: true` and a setup proposal derived from the extracted answers: **accounts (name and type `bank | credit`, from the reported banks and credit cards)**, category groups each with categories (name, icon), payers, payees, and an income summary (`sources`, `expected_monthly_cents`, `income_day`). Loans reported in the debt phase SHALL surface as debt-paydown categories, not accounts (loan/tracking accounts are out of v1 scope); credit cards SHALL surface as accounts, not categories. The proposal SHALL be stored on the session so the review screen survives reloads. A `done` turn without a valid proposal SHALL be re-asked once, then surface the fallback path.

#### Scenario: Vehicle owner gets vehicle categories

- **WHEN** the user reported owning one car
- **THEN** the proposal includes fuel, insurance, inspection/taxes, and maintenance categories for it

#### Scenario: Credit card becomes an account, loan becomes a category

- **WHEN** the user reported a Visa card and a car loan in the debt phase
- **THEN** the proposal lists the Visa under accounts with type `credit` and a "car loan paydown" category, not the reverse

#### Scenario: Proposal persists for review

- **WHEN** the user finishes the interview and reloads during review
- **THEN** `GET /onboarding/session` returns the stored proposal unchanged

### Requirement: Transactional finalize from the reviewed proposal

`POST /onboarding/{session_id}/finalize` SHALL accept the user-reviewed proposal (checked items only, renames applied, user-added entries included) and apply it in a single transaction: **create the accepted accounts (reusing existing account names case-insensitively; credit cards start at zero balance and get their system payment category through the same account-creation path — existing debt and the payment day are set later from the accounts screen, or the payment day is inferred from imported statements)**, create category groups and categories reusing existing names case-insensitively instead of duplicating or erroring, seed the accepted payees and payers through the existing payee resolution, persist the preferences document, write the primary bank account's opening-balance transaction when the user provided a balance during the interview (confirmed, uncategorized, `source = "opening_balance"` — it funds To Be Assigned; skipped answer writes nothing), and mark the session `completed`. On any failure nothing SHALL be persisted. Finalizing a session that is not `active` SHALL return 409 `session_not_active`.

#### Scenario: Reviewed tree created

- **WHEN** the user unchecks "Gas", renames "Groceries" to "Supermercado", adds "Padel club", and finalizes
- **THEN** the created categories match exactly that reviewed set — no Gas category, the renamed and added ones present

#### Scenario: Accounts created from review

- **WHEN** the user keeps "BBVA" (bank) and "Visa BBVA" (credit) checked and finalizes
- **THEN** both accounts exist, the BBVA account holds the opening-balance transaction if a balance was given, the Visa starts at zero, and "Pago Visa BBVA" exists in the "Tarjetas de crédito" group

#### Scenario: Existing names reused, not duplicated

- **WHEN** the proposal contains a group "Vivienda" that already exists from the seed
- **THEN** its categories are created under the existing group and no duplicate group appears

#### Scenario: Opening balance lands with finalize

- **WHEN** the user answered "unos 1.800 €" to the balance question and finalizes
- **THEN** the primary bank account holds a confirmed +1.800,00 € `opening_balance` transaction and the month's To Be Assigned includes it

#### Scenario: Atomic failure

- **WHEN** persisting the preferences document fails mid-finalize
- **THEN** no categories or payees from this finalize remain

### Requirement: Onboarding webapp flow

The webapp SHALL serve the interview at `/onboarding` as a full-screen flow outside the app shell, composed from the coach UI primitives: a chat column rendering assistant turns with tap-to-answer chips/checkboxes and a free-text input, followed by a review screen presenting the proposal as editable checklists — **accounts (name and type),** categories grouped by category group, then payers and payees — where each entry can be unchecked or renamed in place and each section has an "Add new" affordance. Confirming SHALL call finalize and redirect into the app. The dashboard SHALL show a dismissible capsule linking to `/onboarding` while the user has no completed session.

#### Scenario: Tap-through interview

- **WHEN** a turn arrives with chips "Rent" / "Own"
- **THEN** tapping "Own" sends the answer without typing

#### Scenario: Review before anything is created

- **WHEN** the interview ends
- **THEN** the user sees the generated accounts, categories, payers, and payees as checklists and nothing has been persisted yet

#### Scenario: Accounts editable at review

- **WHEN** the user renames "BBVA" to "Cuenta nómina" and unchecks the second bank account
- **THEN** finalize creates "Cuenta nómina" and skips the unchecked account

#### Scenario: Add new during review

- **WHEN** the user adds "Padel club" under a category group in review
- **THEN** finalize creates it along with the checked generated entries

#### Scenario: Dashboard entry point

- **WHEN** a user without a completed onboarding session opens the dashboard
- **THEN** a dismissible "finish setting up" capsule links to `/onboarding`
