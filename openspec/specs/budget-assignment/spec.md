# budget-assignment Specification

## Purpose

Zero-based budget assignment surface: the budget screen where the user distributes the month's income across categories, tracks the remaining "to be assigned" amount, and switches between assignment and reporting views.
## Requirements
### Requirement: To-be-assigned indicator

The budget screen SHALL display a "to be assigned" hero showing the month's unassigned amount as served by the API (`to_be_assigned_cents`, which carries over between months — never recomputed client-side as income minus assignments), formatted in euros (es-ES, tabular numerals). The indicator SHALL remain visible while the assignment list scrolls (sticky), and SHALL reflect every assignment edit without a page reload.

#### Scenario: Positive remainder

- **WHEN** the month's income is 2.350,00 €, nothing carried in, and assignments total 1.938,00 €
- **THEN** the hero shows "412,00 € to assign" in the brand violet treatment
- **AND** the amount updates immediately when any category assignment changes

#### Scenario: Every euro assigned

- **WHEN** assignments total exactly the money available to assign
- **THEN** the hero shows "Every euro assigned" in the mint accent treatment
- **AND** no warning or error styling is present

#### Scenario: Over-assigned

- **WHEN** assignments exceed the money available to assign by 85,00 €
- **THEN** the hero shows "−85,00 € over — unassign somewhere" in the expense-red treatment

#### Scenario: Sticky on scroll (mobile)

- **WHEN** the viewport is narrower than 1024px and the user scrolls the assignment list
- **THEN** a compact bar with the to-be-assigned amount stays pinned below the header

#### Scenario: Carry-in and deduction explained

- **WHEN** October's view reports `carried_in_cents = 30000` and `overspent_deducted_cents = 5000`
- **THEN** the hero shows, under the amount, "Incluye 300,00 € de septiembre · −50,00 € por el gasto de más sin cubrir"

### Requirement: Category assignment list

The screen SHALL render one panel per category group, each row showing the category (icon chip + name), its assigned amount, spent amount, and available amount where `available = assigned + rollover − spent`. The available amount SHALL be colored by sign: mint when positive, neutral gray when zero, expense red when negative. Only the assigned amount SHALL be editable. An overspent row SHALL offer a one-tap cover action built from the API's `cover_suggestion` ("Cubrir desde Restaurantes" / "Cubrir desde lo sin asignar"), and every row SHALL offer a "Move money" action.

#### Scenario: Row math

- **WHEN** a category has 32,00 € rollover, 120,00 € assigned and 138,00 € spent
- **THEN** its available shows "14,00 €" in mint

#### Scenario: Overspent category

- **WHEN** a category's spent exceeds assigned plus rollover
- **THEN** its available shows the negative amount in expense red
- **AND** its progress bar renders in the over-budget (red) state
- **AND** the row shows the cover action for its `cover_suggestion`, and tapping it covers the overspending without further confirmation

#### Scenario: Editing an assignment (desktop)

- **WHEN** the viewport is 1024px or wider and the user clicks a row's assigned amount
- **THEN** an inline amount input receives focus with its value selected
- **AND** committing the value updates the row's available and the to-be-assigned hero

#### Scenario: Editing an assignment (mobile)

- **WHEN** the viewport is narrower than 1024px and the user taps a row's assigned amount
- **THEN** a numpad bottom sheet opens for that category
- **AND** confirming the amount closes the sheet and updates the row and hero

#### Scenario: Rollover breakdown

- **WHEN** the user expands a category row
- **THEN** the row shows the formula breakdown "rollover + assigned − spent = available" with the month's actual amounts
- **AND** when the previous month ended overspent, the breakdown notes that the category started clean and the amount was deducted from To Be Assigned

### Requirement: Per-row quick-fill actions

Each category row SHALL offer quick-fill actions that set the assigned amount from history: last month's assignment, the 3-month average, last month's spent, and zero.

#### Scenario: Quick-fill from last month

- **WHEN** the user picks "Last month" on a category that had 150,00 € assigned in the previous month
- **THEN** the category's assigned amount becomes 150,00 €
- **AND** the to-be-assigned hero updates accordingly

### Requirement: Assign and Report modes

The budget screen SHALL provide two modes via a segmented control: "Assign" (the zero-based assignment surface, default) and "Report" (the spending distribution view). Switching modes SHALL preserve the selected month.

#### Scenario: Default mode

- **WHEN** the user navigates to the budget screen
- **THEN** the Assign mode is active

#### Scenario: Mode switch keeps month

- **WHEN** the user is viewing May in Assign mode and switches to Report
- **THEN** the Report mode shows May's data

### Requirement: Move money sheet

The budget screen SHALL provide a move-money sheet (opened from a row's "Move money" action or from "Elegir otra" on a cover prompt) with a source picker (categories with positive available, plus "Sin asignar" when To Be Assigned is positive, each showing its available), a target, and an amount prefilled with the target's overspending when there is one. Confirming SHALL call the moves API; amounts above the source's available SHALL be prevented in the form, not only rejected by the server.

#### Scenario: Re-plan within the month

- **WHEN** the user opens "Move money" on Viajes, picks Restaurantes as the target and 40,00 €
- **THEN** both rows update, the hero is unchanged, and the sheet closes

#### Scenario: Amount capped by the source

- **WHEN** the chosen source has 25,00 € available
- **THEN** the amount field does not accept more than 25,00 € and the confirm button stays disabled above it

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

### Requirement: Uncategorized spending block

When the month's `uncategorized_count` is greater than zero, the budget screen SHALL render a "Sin categorizar" block above the category groups, in warning style (never the expense red reserved for overspending), showing `uncategorized_cents` and the number of movements and stating that they need a category. The block SHALL offer a "Categorizar ahora" action that requests AI categorization proposals and opens the categorization review on the budget screen itself; applying it SHALL refresh the budget month. When AI proposals are unavailable, the review's empty state SHALL point to categorizing manually from the transactions screen. The block SHALL NOT block assigning, moving money, or any other action, and SHALL disappear once nothing in the month is uncategorized.

#### Scenario: Block shows what needs a category

- **WHEN** June has three uncategorized outflows totaling 74,50 €
- **THEN** the budget screen shows the "Sin categorizar" block with "74,50 €" and "3" above the first group, in warning style

#### Scenario: Categorize from the budget

- **WHEN** the user taps "Categorizar ahora" and applies the proposed categories
- **THEN** the review closes, the categories' spent amounts include those rows, and the block disappears

#### Scenario: Nothing is blocked

- **WHEN** the block is visible
- **THEN** the user can still assign, move money, and cover overspending as usual

#### Scenario: No block when everything is categorized

- **WHEN** the month's `uncategorized_count` is 0
- **THEN** no "Sin categorizar" block is rendered

