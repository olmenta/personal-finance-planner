# budget-api Delta Specification

## MODIFIED Requirements

### Requirement: Budget month view

The API SHALL expose `GET /budget/{month}` returning the `BudgetMonthView` contract the webapp renders: `month`, `income_cents`, `to_be_assigned_cents` (derived, cumulative — see below), `carried_in_cents`, `overspent_deducted_cents`, `uncategorized_cents` and `uncategorized_count` (the month's uncategorized spending — see below), and groups → categories with `assigned_cents`, `spent_cents`, `rollover_cents`, `available_cents` (derived), `overspent_cents` (`max(0, −available_cents)`), `rollover_reset_cents` (the category's previous-month overspending that was reset instead of carried), `cover_suggestion` (nullable; see "Overspending cover suggestion"), `suggestion_cents` and `suggestion_state`, plus quick-fill history fields `last_month_assigned_cents`, `avg_3m_cents` (mean of up to the three previous months' confirmed spending, rounded to whole euros in cents), and `last_month_spent_cents` — each `null` when the relevant history does not exist. Requesting a month with no record SHALL create it lazily with draft suggestions. `income_cents` SHALL count only positive confirmed transactions in cash or bank accounts **without** a category (uncategorized inflows fund To Be Assigned) **and without a `transfer_pair_id`** — transfer rows move money between accounts and never enter the budget plane; a positive confirmed transaction **with** a category is category activity (a refund), and `spent_cents` SHALL be the negated net of the category's signed confirmed activity in the month — expenses minus categorized inflows, transfer rows excluded; card purchases count as spending in their category at purchase time, like any other expense. Each category SHALL also report `credit_overspent_cents` (card spending not covered by its available, see the credit-cards capability). Credit accounts' payment categories SHALL appear in a system group "Tarjetas de crédito", flagged `kind = "credit_payment"` with their `payment_account_id`; for them `spent_cents` is the month's payments into the card and `available_cents` includes the funded moves from budgeted card spending. `to_be_assigned_cents` SHALL carry over between months: it equals `carried_in_cents` (the previous calendar month's To Be Assigned; for the budget's first month, the signed sum of all confirmed cash and bank transactions dated before it) plus the month's unbudgeted activity (the signed sum of confirmed cash and bank transactions without a category, excluding transfer rows — uncategorized rows on a credit account, such as its opening balance, are card debt and never reach To Be Assigned; positive ones are the `income_cents`), minus the month's total assignments, minus `overspent_deducted_cents` (the previous month's total uncovered **cash** overspending — credit overspending becomes card debt and is never deducted). It MAY be negative (over-assigned) and a negative value carries too. `uncategorized_cents` SHALL be the absolute sum, and `uncategorized_count` the number, of the month's confirmed outflows without a category on any of the user's accounts, excluding transfer rows and opening-balance rows; they are reported so the user can categorize them and SHALL NOT change any other figure of the view (on cash and bank accounts those euros are already part of the unbudgeted activity that lowered To Be Assigned). For every month, the signed sum of all confirmed transactions in cash and bank accounts up to the month's end SHALL equal `to_be_assigned_cents` plus the sum of all categories' `available_cents` (payment categories included) plus the month's total `credit_overspent_cents`.

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

- **WHEN** the user's first budget month is July and June's confirmed cash and bank transactions net +500,00 €
- **THEN** July reports `carried_in_cents = 50000`

#### Scenario: Budget identity holds

- **WHEN** any month is requested
- **THEN** `to_be_assigned_cents + Σ available_cents + Σ credit_overspent_cents` equals the signed sum of the user's confirmed cash and bank transactions dated up to that month's end

#### Scenario: Uncategorized spending is reported

- **WHEN** June has a confirmed −30,00 € transaction without a category in a bank account and a confirmed −12,00 € one without a category on a credit card
- **THEN** June's view reports `uncategorized_cents = 4200` and `uncategorized_count = 2`, and every other figure is what it was before these fields existed

#### Scenario: Transfers and opening balances are not uncategorized spending

- **WHEN** June contains a −200,00 € transfer twin and a credit card created with −340,00 € of opening debt
- **THEN** neither counts toward `uncategorized_cents` or `uncategorized_count`

#### Scenario: Categorizing moves the spending into the category

- **WHEN** the −30,00 € bank row is then categorized to Supermercado
- **THEN** `uncategorized_cents` drops by 3000, Supermercado's `spent_cents` rises by 3000, and `to_be_assigned_cents` rises by 3000
