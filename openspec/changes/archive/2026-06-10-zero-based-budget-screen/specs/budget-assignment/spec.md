# Spec — budget-assignment

## ADDED Requirements

### Requirement: To-be-assigned indicator

The budget screen SHALL display a "to be assigned" hero showing the month's unassigned amount, computed as `income_cents − Σ assigned_cents`, formatted in euros (es-ES, tabular numerals). The indicator SHALL remain visible while the assignment list scrolls (sticky), and SHALL reflect every assignment edit without a page reload.

#### Scenario: Positive remainder

- **WHEN** the month's income is 2.350,00 € and assignments total 1.938,00 €
- **THEN** the hero shows "412,00 € to assign" in the brand violet treatment
- **AND** the amount updates immediately when any category assignment changes

#### Scenario: Every euro assigned

- **WHEN** assignments total exactly the month's income
- **THEN** the hero shows "Every euro assigned" in the mint accent treatment
- **AND** no warning or error styling is present

#### Scenario: Over-assigned

- **WHEN** assignments exceed the month's income by 85,00 €
- **THEN** the hero shows "−85,00 € over — unassign somewhere" in the expense-red treatment

#### Scenario: Sticky on scroll (mobile)

- **WHEN** the viewport is narrower than 1024px and the user scrolls the assignment list
- **THEN** a compact bar with the to-be-assigned amount stays pinned below the header

### Requirement: Category assignment list

The screen SHALL render one panel per category group, each row showing the category (icon chip + name), its assigned amount, spent amount, and available amount where `available = assigned + rollover − spent`. The available amount SHALL be colored by sign: mint when positive, neutral gray when zero, expense red when negative. Only the assigned amount SHALL be editable.

#### Scenario: Row math

- **WHEN** a category has 32,00 € rollover, 120,00 € assigned and 138,00 € spent
- **THEN** its available shows "14,00 €" in mint

#### Scenario: Overspent category

- **WHEN** a category's spent exceeds assigned plus rollover
- **THEN** its available shows the negative amount in expense red
- **AND** its progress bar renders in the over-budget (red) state

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
