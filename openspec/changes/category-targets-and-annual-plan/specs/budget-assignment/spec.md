# budget-assignment Delta Specification

## ADDED Requirements

### Requirement: Income breakdown from the to-be-assigned hero

Tapping the to-be-assigned amount (or its income line) on the budget screen SHALL open a breakdown of where the month's money to assign comes from: each income of the month one by one (payer or description, day, amount in the income color), the month's income total against the expected fixed monthly income when known ("expected 4.700,00 € · received 3.500,00 €"), the amount carried in from the previous month, the previous month's uncovered overspending deducted, and the month's total assignments, ending in the to-be-assigned figure. Incomes SHALL come from the month's confirmed uncategorized inflows (the same rule as `income_cents`); the expected figure SHALL come from `GET /api/plan/income`. Refunds (categorized inflows) SHALL NOT appear as income.

#### Scenario: Salary listed with expected versus received

- **WHEN** October has a 3.500,00 € salary on day 27 and expected fixed income is 4.700,00 €
- **THEN** the breakdown lists "Nómina · day 27 · 3.500,00 €" and the line "expected 4.700,00 € · received 3.500,00 €"

#### Scenario: Breakdown adds up to the hero

- **WHEN** the breakdown shows carried in 2.000,00 €, income 0, deducted 0 and assigned 1.909,20 €
- **THEN** its final line equals the hero's 90,80 € to assign

#### Scenario: No income yet this month

- **WHEN** the month has no confirmed uncategorized inflows
- **THEN** the breakdown says no income has arrived yet this month and, when expected income is known, shows it as still to come
