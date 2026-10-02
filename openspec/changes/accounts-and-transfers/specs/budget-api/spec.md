# budget-api Delta Specification

> Builds on the `budget-rules` wording (carry-over To Be Assigned, overspending reset) — that change lands and syncs first.

## MODIFIED Requirements

### Requirement: Budget month view

The API SHALL expose `GET /budget/{month}` returning the `BudgetMonthView` contract the webapp renders: `month`, `income_cents`, `to_be_assigned_cents` (derived, cumulative — see below), `carried_in_cents`, `overspent_deducted_cents`, and groups → categories with `assigned_cents`, `spent_cents`, `rollover_cents`, `available_cents` (derived), `overspent_cents` (`max(0, −available_cents)`), `rollover_reset_cents` (the category's previous-month overspending that was reset instead of carried), `cover_suggestion` (nullable; see "Overspending cover suggestion"), `suggestion_cents` and `suggestion_state`, plus quick-fill history fields `last_month_assigned_cents`, `avg_3m_cents` (mean of up to the three previous months' confirmed spending, rounded to whole euros in cents), and `last_month_spent_cents` — each `null` when the relevant history does not exist. Requesting a month with no record SHALL create it lazily with draft suggestions. `income_cents` SHALL count only positive confirmed transactions **without** a category (uncategorized inflows fund To Be Assigned) **and without a `transfer_pair_id`** — transfer rows move money between accounts and never enter the budget plane; a positive confirmed transaction **with** a category is category activity (a refund), and `spent_cents` SHALL be the negated net of the category's signed confirmed activity in the month — expenses minus categorized inflows, transfer rows excluded; card purchases count as spending in their category at purchase time, like any other expense. Each category SHALL also report `credit_overspent_cents` (card spending not covered by its available, see the credit-cards capability). Credit accounts' payment categories SHALL appear in a system group "Tarjetas de crédito", flagged `kind = "credit_payment"` with their `payment_account_id`; for them `spent_cents` is the month's payments into the card and `available_cents` includes the funded moves from budgeted card spending. `to_be_assigned_cents` SHALL carry over between months: it equals `carried_in_cents` (the previous calendar month's To Be Assigned; for the budget's first month, the signed sum of all confirmed transactions dated before it) plus the month's unbudgeted activity (the signed sum of confirmed transactions without a category, excluding transfer rows and credit-account opening balances — positive ones are the `income_cents`), minus the month's total assignments, minus `overspent_deducted_cents` (the previous month's total uncovered **cash** overspending — credit overspending becomes card debt and is never deducted). It MAY be negative (over-assigned) and a negative value carries too. For every month, the signed sum of all confirmed transactions in cash and bank accounts up to the month's end SHALL equal `to_be_assigned_cents` plus the sum of all categories' `available_cents` (payment categories included) plus the month's total `credit_overspent_cents`.

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

#### Scenario: Unassigned money carries to the next month

- **WHEN** September has 4.700,00 € of income, 4.400,00 € assigned and no overspending, and October has no income yet and nothing assigned
- **THEN** October reports `carried_in_cents = 30000` and `to_be_assigned_cents = 30000`

#### Scenario: Late salary funds next month

- **WHEN** a 3.500,00 € salary lands on 27 September and the user leaves it unassigned
- **THEN** September ends with that amount in To Be Assigned and October's view starts with it as `carried_in_cents`, available to assign to October's categories

#### Scenario: Over-assigned month carries the negative

- **WHEN** September's assignments exceed its available money by 85,00 €
- **THEN** September reports `to_be_assigned_cents = -8500` and October's `carried_in_cents` is `-8500`

#### Scenario: History before the budget seeds To Be Assigned

- **WHEN** the user's first budget month is July and June's confirmed transactions net +500,00 €
- **THEN** July reports `carried_in_cents = 50000`

#### Scenario: Budget identity holds

- **WHEN** any month is requested
- **THEN** `to_be_assigned_cents + Σ available_cents + Σ credit_overspent_cents` equals the signed sum of the user's confirmed cash and bank transactions dated up to that month's end

### Requirement: Rollover carries unspent balances forward

A category's `rollover_cents` for month M SHALL equal its available balance at the end of month M−1 (`assigned + rollover − spent`) when that balance is zero or positive, and zero when it is negative — an overspent category SHALL start the next month clean. Of a negative end balance, the part explained by that month's `credit_overspent_cents` is card debt (it stays on the card, uncovered by its payment category) and the rest is cash overspending, deducted from month M's To Be Assigned (`overspent_deducted_cents`). Payment categories carry their available forward the same way, so money set aside for a card persists until the card is paid. The chain SHALL walk every calendar month from the budget's first month to M: a month the user never opened counts as zero assignments with its actual spending, and SHALL NOT be materialized by the walk. Rollover is zero for the budget's first month.

#### Scenario: Positive carryover

- **WHEN** a category ends May with 32,00 € available
- **THEN** June's view reports `rollover_cents = 3200` for that category

#### Scenario: Uncovered overspending resets the category

- **WHEN** Supermercado ends September at −50,00 € available from debit-card spending and nothing covered it
- **THEN** October's view reports `rollover_cents = 0` and `rollover_reset_cents = 5000` for Supermercado and `overspent_deducted_cents = 5000`, and October's To Be Assigned is 50,00 € lower than it would otherwise be

#### Scenario: Credit overspending resets without touching To Be Assigned

- **WHEN** Supermercado ends May at −50,00 € available entirely because of card spending not covered by its budget
- **THEN** June's view reports `rollover_cents = 0` for Supermercado, `overspent_deducted_cents` does not include those 50,00 €, and they remain as the card's uncovered debt

#### Scenario: Set-aside card money carries forward

- **WHEN** "Pago Visa BBVA" ends May with 320,00 € available because the card is charged on 10 June
- **THEN** June's view reports `rollover_cents = 32000` for "Pago Visa BBVA"

#### Scenario: Unopened month keeps the chain

- **WHEN** the user opened September and November but never October, and a category had 100,00 € available at the end of September and 30,00 € of confirmed spending in October
- **THEN** November's view reports `rollover_cents = 7000` for it, and no October budget month is created by the read
