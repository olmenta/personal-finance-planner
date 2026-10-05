# budget-api Specification

## Purpose

HTTP API surface for the zero-based budget: the per-month budget view contract the webapp renders, category assignment upserts, draft suggestions seeded from the previous month, and rollover of unspent balances.
## Requirements
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

### Requirement: Assign to a category

The API SHALL expose `PUT /budget/{month}/assignments/{category_id}` accepting `amount_cents ≥ 0`, upserting the assignment and setting its suggestion state to `edited`. The response SHALL include the recalculated `to_be_assigned_cents`.

#### Scenario: Assignment updates to-be-assigned

- **WHEN** income is 2.350,00 €, total assigned is 1.938,00 €, and a client raises one category by 412,00 €
- **THEN** the response reports `to_be_assigned_cents = 0`

### Requirement: Draft suggestions from the previous month

When a budget month is created, each category with payments SHALL be assigned its suggested monthly amount (the larger of its normal and catch-up amounts, see payment-schedules) in state `confirmed` — it is computed, not a draft to accept — also in the budget's first month; every other category's assignment SHALL be drafted from the previous month's assignment (state `draft`), and if no previous month exists, it SHALL start at zero with no draft. `POST /budget/{month}/confirm-suggestions` SHALL mark the given categories' drafts as `confirmed` without changing amounts, and SHALL NOT overwrite `edited` assignments.

#### Scenario: New month pre-fills from history

- **WHEN** June is first requested and May has assignments
- **THEN** June's assignments equal May's with `suggestion_state = "draft"`

#### Scenario: First month starts empty

- **WHEN** the first-ever month is requested
- **THEN** all assignments are zero and no category is in `draft` state

#### Scenario: Confirm preserves edits

- **WHEN** a client confirms suggestions after editing one category manually
- **THEN** drafted categories become `confirmed` and the edited category keeps its amount and `edited` state

#### Scenario: Scheduled category drafts its computed amount

- **WHEN** October is first requested and "Colegio Tomi" is scheduled with a suggested amount of 721,40 € while September had 632,00 € assigned
- **THEN** October's assignment for "Colegio Tomi" is 721,40 €

#### Scenario: First month still assigns categories with payments

- **WHEN** the first-ever month is requested and "Alquiler" has a 952,00 € monthly payment
- **THEN** "Alquiler" is assigned 952,00 € while categories without payments start at zero

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

### Requirement: Move money between categories

The API SHALL expose `POST /budget/{month}/moves` accepting `from_category_id` (a category id, or `null` meaning To Be Assigned), `to_category_id`, and `amount_cents > 0`. It SHALL, atomically, lower the source category's assignment (or draw from To Be Assigned) and raise the target's by the amount, marking both assignments `edited`, and return the recalculated month view. The amount SHALL NOT exceed the source's current `available_cents` (422 `insufficient_available`) or, for `null`, the month's positive To Be Assigned (422 `insufficient_to_be_assigned`); a source assignment MAY become negative when the moved money comes from its rollover. Moving to the same category SHALL return 422 `same_category`; an unknown or foreign category SHALL return 404 `category_not_found`. `PUT /budget/{month}/assignments/{category_id}` keeps its `amount_cents ≥ 0` rule.

#### Scenario: Cover overspending from another category

- **WHEN** Supermercado is at −50,00 € available and Restaurantes has 120,00 € available, and the client moves 50,00 € from Restaurantes to Supermercado
- **THEN** Supermercado's available becomes 0, Restaurantes' becomes 70,00 €, and `to_be_assigned_cents` is unchanged

#### Scenario: Cover from To Be Assigned

- **WHEN** the month has 80,00 € To Be Assigned and the client moves 50,00 € from `null` to Supermercado
- **THEN** Supermercado's assignment rises by 50,00 € and `to_be_assigned_cents` drops to 30,00 €

#### Scenario: Moving money that isn't there

- **WHEN** a client tries to move 200,00 € out of a category with 120,00 € available
- **THEN** the API returns 422 with code `insufficient_available` and nothing changes

#### Scenario: Move from rollover makes the assignment negative

- **WHEN** Vacaciones has 0 assigned this month but 600,00 € of rollover, and 100,00 € are moved out of it
- **THEN** Vacaciones' assignment is −100,00 € and its available is 500,00 €

### Requirement: Overspending cover suggestion

For every category with `overspent_cents > 0`, the month view SHALL include a `cover_suggestion` of `{source_category_id | null, amount_cents}` chosen greedily, largest overspending first: the month's positive To Be Assigned (`null`) when there is any left, otherwise the non-overspent category with the largest available; `amount_cents` SHALL be the smaller of the overspending and the source's remaining available. Sources SHALL be consumed across suggestions so no two suggestions promise the same money. Categories that are not overspent SHALL carry `cover_suggestion = null`.

#### Scenario: To Be Assigned is the first source

- **WHEN** Supermercado is overspent by 50,00 € and the month has 30,00 € To Be Assigned and Restaurantes 120,00 € available
- **THEN** Supermercado's `cover_suggestion` is `{source_category_id: null, amount_cents: 3000}`

#### Scenario: Largest available category otherwise

- **WHEN** To Be Assigned is 0 and Restaurantes (120,00 €) and Ocio (40,00 €) have money, and Supermercado is overspent by 50,00 €
- **THEN** the suggestion is `{source_category_id: <Restaurantes>, amount_cents: 5000}`

#### Scenario: Two overspent categories don't share the same euros

- **WHEN** Supermercado is overspent by 50,00 € and Combustible by 20,00 €, and only Restaurantes has money (60,00 €)
- **THEN** Supermercado's suggestion takes 50,00 € from Restaurantes and Combustible's takes the remaining 10,00 €

### Requirement: Monthly amounts in the budget view

Each category in `GET /budget/{month}` SHALL include `kind` (`credit_payment` for a card's payment category), `normal_cents` and `catch_up_cents` (both `null` for categories without schedules), computed as in payment-schedules for that month.

#### Scenario: Budget row shows both amounts

- **WHEN** October's view is requested and "Colegio Tomi" has schedules
- **THEN** its row carries `kind = "scheduled"`, `normal_cents = 58292` and `catch_up_cents = 72140`

