# budget-assignment Delta Specification

## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Move money sheet

The budget screen SHALL provide a move-money sheet (opened from a row's "Move money" action or from "Elegir otra" on a cover prompt) with a source picker (categories with positive available, plus "Sin asignar" when To Be Assigned is positive, each showing its available), a target, and an amount prefilled with the target's overspending when there is one. Confirming SHALL call the moves API; amounts above the source's available SHALL be prevented in the form, not only rejected by the server.

#### Scenario: Re-plan within the month

- **WHEN** the user opens "Move money" on Viajes, picks Restaurantes as the target and 40,00 €
- **THEN** both rows update, the hero is unchanged, and the sheet closes

#### Scenario: Amount capped by the source

- **WHEN** the chosen source has 25,00 € available
- **THEN** the amount field does not accept more than 25,00 € and the confirm button stays disabled above it
