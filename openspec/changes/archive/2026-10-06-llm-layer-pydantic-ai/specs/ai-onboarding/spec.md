# ai-onboarding Delta Specification

## MODIFIED Requirements

### Requirement: Prompt-config-driven interview turns

The interview SHALL be driven by a versioned prompt configuration file in the repo declaring the questions (five YNAB-style phases: household & income — including **each fixed income source (name, payer, net amount, the approximate day it arrives, and whether a salary comes in 12 or 14 payments a year; bonuses that depend on targets are acknowledged but never extracted as income)**, **which bank accounts and credit cards the user has** (names, as free text or common-bank checkboxes), and an **optional, skippable** question for the current balance of the primary bank account —, housing & utilities, true expenses, lifestyle & subscriptions, debt — where credit cards map to accounts and loans map to debt-paydown categories), the tone, and the extraction-field schema. Changing questions or extracted fields SHALL require only editing this configuration. `POST /onboarding/messages` SHALL send the user's reply, invoke the model through the LLM layer (route `onboarding`, see llm-layer) with structured output, and return a turn containing: the assistant `message`, an `input_kind` of `chips`, `checkboxes`, `text`, or `money` with `options` where applicable, and `done`. Extracted answer deltas SHALL be validated against the declared schema — unknown fields SHALL be dropped and logged, never persisted.

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

#### Scenario: Two incomes with extra pays

- **WHEN** the user answers "cobro 2.000 netos el 27 en 14 pagas de Acme, y mi pareja 1.500 el día 1"
- **THEN** the extraction carries two income sources: Acme 2.000,00 € on day 27 with 14 payments, and a second 1.500,00 € on day 1 with 12 payments

#### Scenario: Bonus not extracted as income

- **WHEN** the user mentions "y un bonus si la empresa cumple objetivos"
- **THEN** no income source is extracted for the bonus and the interview moves on
