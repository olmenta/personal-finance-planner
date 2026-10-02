# budget-suggestions Delta Specification

## MODIFIED Requirements

### Requirement: Draft assignments from prior month

When a budget month opens, the system SHALL pre-fill each scheduled category (and each savings category with a goal) as a draft equal to its suggested monthly amount from its payments, and, when prior-month data is available, every other category as a draft equal to the previous month's assignment. Drafts computed from payments SHALL be labelled "Suggested from your payments". Draft amounts SHALL be visually distinct from confirmed amounts and SHALL count toward the to-be-assigned calculation.

#### Scenario: Month opens with history

- **WHEN** June opens and May had assignments
- **THEN** every category shows May's assignment as a draft value
- **AND** the to-be-assigned hero reflects the drafted total

#### Scenario: First month — no history

- **WHEN** a budget month opens and no prior month exists
- **THEN** assignments start at zero with no draft state
- **AND** the screen shows an empty-state inviting the first assignment (directional copy, no apology)

#### Scenario: Scheduled category suggests from its payments

- **WHEN** October opens and "Colegio Tomi" is scheduled
- **THEN** its draft equals its suggested monthly amount and the row reads "Suggested from your payments"
