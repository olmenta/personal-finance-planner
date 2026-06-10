# Spec — budget-suggestions

## ADDED Requirements

### Requirement: Draft assignments from prior month

When a budget month opens with prior-month data available, the system SHALL pre-fill each category's assignment as a draft equal to the previous month's assignment. Draft amounts SHALL be visually distinct from confirmed amounts and SHALL count toward the to-be-assigned calculation.

#### Scenario: Month opens with history

- **WHEN** June opens and May had assignments
- **THEN** every category shows May's assignment as a draft value
- **AND** the to-be-assigned hero reflects the drafted total

#### Scenario: First month — no history

- **WHEN** a budget month opens and no prior month exists
- **THEN** assignments start at zero with no draft state
- **AND** the screen shows an empty-state inviting the first assignment (directional copy, no apology)

### Requirement: Bulk confirmation via coach capsule

The screen SHALL surface pending drafts through a coach insight capsule with a single confirm-all action. Confirming SHALL mark all remaining drafts as confirmed. Draft assignments SHALL NOT be committed silently: leaving the screen without confirming keeps them as drafts.

#### Scenario: Confirm all

- **WHEN** the user activates "Confirm all" on the capsule
- **THEN** every draft assignment becomes confirmed
- **AND** the capsule disappears

#### Scenario: Partial manual edits

- **WHEN** the user edits 3 of 14 drafted categories manually
- **THEN** those 3 become "edited" and leave the draft set
- **AND** the capsule action updates to confirm the remaining 11

#### Scenario: Dismissal is not confirmation

- **WHEN** the user dismisses the capsule without confirming
- **THEN** draft assignments remain in draft state and stay editable

### Requirement: Per-category suggestion states

Each category assignment SHALL carry one of three suggestion states: `draft` (proposed, unconfirmed), `confirmed` (accepted as proposed), or `edited` (user changed the amount). Editing a draft or confirmed amount SHALL set the state to `edited`.

#### Scenario: Edit converts state

- **WHEN** the user changes a drafted 150,00 € assignment to 180,00 €
- **THEN** that category's suggestion state becomes `edited`
- **AND** subsequent bulk confirmation does not overwrite the 180,00 €
