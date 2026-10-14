## MODIFIED Requirements

### Requirement: Draft suggestions from the previous month

When a budget month is created, each category with payments SHALL be assigned its suggested monthly amount (the larger of its normal and catch-up amounts, see payment-schedules) in state `confirmed` — it is computed, not a draft to accept — also in the budget's first month; every other category's assignment SHALL be drafted from the previous month's assignment (state `draft`), and if no previous month exists, it SHALL start at zero with no draft. `POST /budget/{month}/confirm-suggestions` SHALL mark the given categories' drafts as `confirmed` without changing amounts, and SHALL NOT overwrite `edited` assignments.

#### Scenario: New month pre-fills from history

- **WHEN** June is first requested and May has assignments
- **THEN** June's assignments for categories without payments equal May's with `suggestion_state = "draft"`

#### Scenario: First month starts empty

- **WHEN** the first-ever month is requested
- **THEN** every category without payments is assigned zero, and no category is in `draft` state

#### Scenario: Confirm preserves edits

- **WHEN** a client confirms suggestions after editing one category manually
- **THEN** drafted categories become `confirmed` and the edited category keeps its amount and `edited` state

#### Scenario: Scheduled category drafts its computed amount

- **WHEN** October is first requested and "Colegio Tomi" is scheduled with a suggested amount of 721,40 € while September had 632,00 € assigned
- **THEN** October's assignment for "Colegio Tomi" is 721,40 €

#### Scenario: First month still assigns categories with payments

- **WHEN** the first-ever month is requested and "Alquiler" has a 952,00 € monthly payment
- **THEN** "Alquiler" is assigned 952,00 € while categories without payments start at zero
