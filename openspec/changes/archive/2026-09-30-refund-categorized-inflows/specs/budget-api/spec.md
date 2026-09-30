# budget-api Delta Specification

## MODIFIED Requirements

### Requirement: Budget month view

The API SHALL expose `GET /budget/{month}` returning the `BudgetMonthView` contract the webapp renders: `month`, `income_cents`, `to_be_assigned_cents` (derived), and groups → categories with `assigned_cents`, `spent_cents`, `rollover_cents`, `available_cents` (derived), `suggestion_cents` and `suggestion_state`, plus quick-fill history fields `last_month_assigned_cents`, `avg_3m_cents` (mean of up to the three previous months' confirmed spending, rounded to whole euros in cents), and `last_month_spent_cents` — each `null` when the relevant history does not exist. Requesting a month with no record SHALL create it lazily with draft suggestions. `income_cents` SHALL count only positive confirmed transactions **without** a category (uncategorized inflows fund To Be Assigned); a positive confirmed transaction **with** a category is category activity (a refund), and `spent_cents` SHALL be the negated net of the category's signed confirmed activity in the month — expenses minus categorized inflows.

#### Scenario: View matches webapp contract

- **WHEN** a client requests `GET /budget/2026-06`
- **THEN** the response contains income, derived to-be-assigned, and per-category assigned/spent/rollover/available in integer cents

#### Scenario: Spent aggregates confirmed transactions only

- **WHEN** a category has confirmed transactions totaling 138,00 € and a staged transaction of 50,00 € in the month
- **THEN** the view reports `spent_cents = 13800` for that category

#### Scenario: Refund restores the category, not income

- **WHEN** Supermercado has confirmed expenses of 138,00 € and a confirmed +12,50 € inflow categorized to Supermercado in the month
- **THEN** the view reports `spent_cents = 12550` for Supermercado and the refund is not included in `income_cents`

#### Scenario: Uncategorized inflow is income

- **WHEN** a confirmed +2.350,00 € transaction without a category lands in the month
- **THEN** `income_cents` includes it and no category's `spent_cents` changes

#### Scenario: Quick-fill fields from history

- **WHEN** a category was assigned 120,00 € in May with 119,00 € spent, and June is requested
- **THEN** June's view reports `last_month_assigned_cents = 12000` and `last_month_spent_cents = 11900` for that category

#### Scenario: First month has no quick-fill

- **WHEN** the first-ever month is requested
- **THEN** every category's `last_month_assigned_cents`, `avg_3m_cents`, and `last_month_spent_cents` are `null`
