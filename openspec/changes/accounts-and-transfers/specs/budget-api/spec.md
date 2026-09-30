# budget-api Delta Specification

> Builds on the `refund-categorized-inflows` wording — that change must sync first.

## MODIFIED Requirements

### Requirement: Budget month view

The API SHALL expose `GET /budget/{month}` returning the `BudgetMonthView` contract the webapp renders: `month`, `income_cents`, `to_be_assigned_cents` (derived), and groups → categories with `assigned_cents`, `spent_cents`, `rollover_cents`, `available_cents` (derived), `suggestion_cents` and `suggestion_state`, plus quick-fill history fields `last_month_assigned_cents`, `avg_3m_cents` (mean of up to the three previous months' confirmed spending, rounded to whole euros in cents), and `last_month_spent_cents` — each `null` when the relevant history does not exist. Requesting a month with no record SHALL create it lazily with draft suggestions. `income_cents` SHALL count only positive confirmed transactions **without** a category (uncategorized inflows fund To Be Assigned) **and without a `transfer_pair_id`** — transfer rows move money between accounts and never enter the budget plane; a positive confirmed transaction **with** a category is category activity (a refund), and `spent_cents` SHALL be the negated net of the category's signed confirmed activity in the month — expenses minus categorized inflows, transfer rows excluded; card purchases count as spending in their category at purchase time, like any other expense. Each category SHALL also report `credit_overspent_cents` (card spending not covered by its available, see the credit-cards capability). Credit accounts' payment categories SHALL appear in a system group "Tarjetas de crédito", flagged `kind = "credit_payment"` with their `payment_account_id`; for them `spent_cents` is the month's payments into the card and `available_cents` includes the funded moves from budgeted card spending. Opening balances of credit accounts SHALL NOT count in `income_cents`.

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

#### Scenario: Transfers never enter the budget

- **WHEN** June contains a 200,00 € transfer between two of the user's accounts
- **THEN** June's `income_cents`, `to_be_assigned_cents`, and every category's `spent_cents` are exactly what they would be without the transfer

#### Scenario: Card purchase moves money to the payment group

- **WHEN** Supermercado has 400,00 € available and a 200,00 € grocery purchase on "Visa BBVA" is confirmed
- **THEN** Supermercado reports `spent_cents = 20000` and `available_cents = 20000`, "Pago Visa BBVA" in the "Tarjetas de crédito" group reports `available_cents = 20000`, and `to_be_assigned_cents` is unchanged

#### Scenario: Quick-fill fields from history

- **WHEN** a category was assigned 120,00 € in May with 119,00 € spent, and June is requested
- **THEN** June's view reports `last_month_assigned_cents = 12000` and `last_month_spent_cents = 11900` for that category

#### Scenario: First month has no quick-fill

- **WHEN** the first-ever month is requested
- **THEN** every category's `last_month_assigned_cents`, `avg_3m_cents`, and `last_month_spent_cents` are `null`

### Requirement: Rollover carries unspent balances forward

A category's `rollover_cents` for month M SHALL equal its available balance at the end of month M−1 (`assigned + rollover − spent`, floored at the chain's actual value, including negative carryover from cash overspending), **plus that month's `credit_overspent_cents`** — credit overspending is funded by card debt and SHALL NOT carry into the category — and zero when no previous month exists. Payment categories carry their available forward the same way, so money set aside for a card persists until the card is paid.

#### Scenario: Positive carryover

- **WHEN** a category ends May with 32,00 € available
- **THEN** June's view reports `rollover_cents = 3200` for that category

#### Scenario: Credit overspending resets

- **WHEN** Supermercado ends May at −50,00 € available entirely because of card spending not covered by its budget
- **THEN** June's view reports `rollover_cents = 0` for Supermercado and the 50,00 € remains as the card's uncovered debt

#### Scenario: Set-aside card money carries forward

- **WHEN** "Pago Visa BBVA" ends May with 320,00 € available because the card is charged on 10 June
- **THEN** June's view reports `rollover_cents = 32000` for "Pago Visa BBVA"
