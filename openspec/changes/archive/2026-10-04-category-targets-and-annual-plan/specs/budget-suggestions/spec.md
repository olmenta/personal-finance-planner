# budget-suggestions Delta Specification

## MODIFIED Requirements

### Requirement: Draft assignments from prior month

When a budget month opens, the system SHALL assign each category with payments its computed monthly amount — shown read-only and labelled "From your payments", never as a draft — and, when prior-month data is available, pre-fill every other category as a draft equal to the previous month's assignment. Draft amounts SHALL be visually distinct from confirmed amounts and SHALL count toward the to-be-assigned calculation.

#### Scenario: Month opens with history

- **WHEN** June opens and May had assignments
- **THEN** every category shows May's assignment as a draft value
- **AND** the to-be-assigned hero reflects the drafted total

#### Scenario: First month — no history

- **WHEN** a budget month opens and no prior month exists
- **THEN** assignments start at zero with no draft state
- **AND** the screen shows an empty-state inviting the first assignment (directional copy, no apology)

#### Scenario: Category with payments is computed, not drafted

- **WHEN** October opens and "Colegio Tomi" has payments
- **THEN** its assignment equals its suggested monthly amount, the row reads "From your payments", and the amount is not editable
