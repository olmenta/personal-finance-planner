# ai-onboarding Delta Specification

## ADDED Requirements

### Requirement: Onboarding session lifecycle

The backend SHALL expose an onboarding session per user with status `active`, `completed`, or `abandoned`. `POST /onboarding/start` SHALL return the user's existing `active` session (with its transcript) when one exists, otherwise create one recording the current prompt version. The session SHALL persist every exchanged turn so the interview survives page reloads, and `GET /onboarding/session` SHALL return the active session (transcript, latest turn, proposal when present) or 404 `no_active_session`.

#### Scenario: Fresh start creates a session

- **WHEN** a user with no active session calls `POST /onboarding/start`
- **THEN** an `active` session is created with the configured prompt version and the opening assistant turn is returned

#### Scenario: Reload resumes mid-interview

- **WHEN** a user who answered three questions reloads the page and the webapp calls `GET /onboarding/session`
- **THEN** the full transcript and the pending assistant turn are returned and the interview continues where it left off

#### Scenario: Start is idempotent on an active session

- **WHEN** `POST /onboarding/start` is called while a session is already `active`
- **THEN** the existing session is returned and no second session is created

### Requirement: Prompt-config-driven interview turns

The interview SHALL be driven by a versioned prompt configuration file in the repo declaring the questions (five YNAB-style phases: household & income — including expected monthly income and the approximate day it arrives —, housing & utilities, true expenses, lifestyle & subscriptions, debt), the tone, and the extraction-field schema. Changing questions or extracted fields SHALL require only editing this configuration. `POST /onboarding/messages` SHALL send the user's reply, invoke the LLM through LiteLLM with structured output, and return a turn containing: the assistant `message`, an `input_kind` of `chips`, `checkboxes`, `text`, or `money` with `options` where applicable, and `done`. Extracted answer deltas SHALL be validated against the declared schema — unknown fields SHALL be dropped and logged, never persisted.

#### Scenario: Turn returns quick-input hints

- **WHEN** the interview reaches the utilities question
- **THEN** the turn carries `input_kind: "checkboxes"` with utility options so the user answers by tapping

#### Scenario: Free text understood

- **WHEN** the user types "my flat is fully electric, no gas" instead of using the checkboxes
- **THEN** the extracted utilities reflect electricity without gas and the interview moves on

#### Scenario: Questions change without code changes

- **WHEN** a new question is added to the prompt configuration with a new field in its extraction schema
- **THEN** the interview asks it and persists the new field with no backend code modification, under a bumped prompt version

#### Scenario: Hallucinated field dropped

- **WHEN** the model returns an extraction key not declared in the schema
- **THEN** the key is dropped and logged and the rest of the delta is kept

### Requirement: Generated setup proposal on completion

When the interview completes, the turn SHALL carry `done: true` and a setup proposal derived from the extracted answers: category groups each with categories (name, icon), payers, payees, and an income summary (`sources`, `expected_monthly_cents`, `income_day`). The proposal SHALL be stored on the session so the review screen survives reloads. A `done` turn without a valid proposal SHALL be re-asked once, then surface the fallback path.

#### Scenario: Vehicle owner gets vehicle categories

- **WHEN** the user reported owning one car
- **THEN** the proposal includes fuel, insurance, inspection/taxes, and maintenance categories for it

#### Scenario: Proposal persists for review

- **WHEN** the user finishes the interview and reloads during review
- **THEN** `GET /onboarding/session` returns the stored proposal unchanged

### Requirement: Preferences memory persisted per user

Extracted answers SHALL persist as one JSONB document per user (`UserPreferences`, unique per user) recording the prompt version that produced it, written through a `PreferencesStore` interface. The document SHALL include the income fields (`expected_monthly_cents`, `income_day`); no budget table SHALL store income — monthly income remains derived from confirmed transactions.

#### Scenario: Preferences written at finalize

- **WHEN** onboarding is finalized
- **THEN** the user has exactly one preferences document containing the extracted answers and the prompt version

#### Scenario: Income lives in preferences only

- **WHEN** the user reported 2.400 € arriving around day 27
- **THEN** `expected_monthly_cents` and `income_day` are stored in preferences and no budget month income field is written

### Requirement: Transactional finalize from the reviewed proposal

`POST /onboarding/{session_id}/finalize` SHALL accept the user-reviewed proposal (checked items only, renames applied, user-added entries included) and apply it in a single transaction: create category groups and categories reusing existing names case-insensitively instead of duplicating or erroring, seed the accepted payees and payers through the existing payee resolution, persist the preferences document, and mark the session `completed`. On any failure nothing SHALL be persisted. Finalizing a session that is not `active` SHALL return 409 `session_not_active`.

#### Scenario: Reviewed tree created

- **WHEN** the user unchecks "Gas", renames "Groceries" to "Supermercado", adds "Padel club", and finalizes
- **THEN** the created categories match exactly that reviewed set — no Gas category, the renamed and added ones present

#### Scenario: Existing names reused, not duplicated

- **WHEN** the proposal contains a group "Vivienda" that already exists from the seed
- **THEN** its categories are created under the existing group and no duplicate group appears

#### Scenario: Atomic failure

- **WHEN** persisting the preferences document fails mid-finalize
- **THEN** no categories or payees from this finalize remain

### Requirement: Deterministic fallback when the interview is unavailable

When no LLM API key is configured, or a turn call fails after retry, the backend SHALL return 503 `onboarding_unavailable` rather than degrade silently. The webapp SHALL then offer setting up with the default starter template, and that path SHALL finalize with the default category tree and no preferences document.

#### Scenario: No API key

- **WHEN** `POST /onboarding/start` runs without an LLM key configured
- **THEN** the response is 503 `onboarding_unavailable` and the webapp offers the starter template instead of the chat

#### Scenario: Template fallback completes setup

- **WHEN** the user accepts the starter template
- **THEN** the default category tree is created and the user proceeds to the app without an interview transcript

### Requirement: Onboarding webapp flow

The webapp SHALL serve the interview at `/onboarding` as a full-screen flow outside the app shell, composed from the coach UI primitives: a chat column rendering assistant turns with tap-to-answer chips/checkboxes and a free-text input, followed by a review screen presenting the proposal as editable checklists — categories grouped by category group, then payers and payees — where each entry can be unchecked or renamed in place and each section has an "Add new" affordance. Confirming SHALL call finalize and redirect into the app. The dashboard SHALL show a dismissible capsule linking to `/onboarding` while the user has no completed session.

#### Scenario: Tap-through interview

- **WHEN** a turn arrives with chips "Rent" / "Own"
- **THEN** tapping "Own" sends the answer without typing

#### Scenario: Review before anything is created

- **WHEN** the interview ends
- **THEN** the user sees the generated categories, payers, and payees as checklists and nothing has been persisted yet

#### Scenario: Add new during review

- **WHEN** the user adds "Padel club" under a category group in review
- **THEN** finalize creates it along with the checked generated entries

#### Scenario: Dashboard entry point

- **WHEN** a user without a completed onboarding session opens the dashboard
- **THEN** a dismissible "finish setting up" capsule links to `/onboarding`

### Requirement: Transcript privacy

The interview transcript and extracted answers SHALL be stored only in the onboarding session and preferences tables, SHALL NOT appear in logs or telemetry, and SHALL be deleted with the user's account. Interview content sent to the model provider SHALL follow the established data-processor posture.

#### Scenario: No transcript in logs

- **WHEN** a turn fails and is logged
- **THEN** the log carries the error and session id but no message content
