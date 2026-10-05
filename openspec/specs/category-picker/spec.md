# category-picker Specification

## Purpose

The one category picker the webapp uses wherever a transaction's category is chosen: a searchable combobox over the user's active categories that can also create a category in place, so categorizing never forces the user to leave the flow they are in.

## Requirements
### Requirement: Searchable category picker

Every place where the webapp asks the user for a transaction's category — the statement import review, the Add and Edit transaction dialogs, and the AI categorization review — SHALL use one shared category picker: a combobox that lists the user's active categories under their group headings and filters them as the user types (case-insensitive, matching anywhere in the name). Archived categories and categories in system groups (the credit-card "Tarjetas de crédito" group) SHALL NOT be offered. Where a row may stay without a category, the picker SHALL offer that choice with the context's label ("Ready to assign" for inflows, "Uncategorized" for outflows). The picker SHALL be fully usable with the keyboard (open, type, arrow through options, Enter to select, Escape to close).

#### Scenario: Filter by typing

- **WHEN** the user opens the picker and types "rest"
- **THEN** only categories whose name contains "rest" (e.g. "Restaurantes") remain listed, still under their group heading

#### Scenario: Card payment categories not offered

- **WHEN** the user has a credit card with its "Pago Visa BBVA" payment category
- **THEN** the picker never lists "Pago Visa BBVA" nor the "Tarjetas de crédito" group

#### Scenario: Keyboard selection

- **WHEN** the user focuses the picker, types "super", presses the down arrow and Enter
- **THEN** the highlighted category is selected and the picker closes

### Requirement: Create a category from the picker

When the typed text matches no active category name exactly (case-insensitive), the picker SHALL offer "Crear «<text>»". Choosing it SHALL show an inline form inside the picker with the name (prefilled, editable) and a group selector listing the user's non-system groups, preselected with the group used for the last category created from a picker on this device (falling back to the first non-system group). Confirming SHALL create the category through the categories API, select it in the picker that created it, and make it available immediately in every other open picker — including the other rows of the same review — without a page reload. If the name already exists in that group, the picker SHALL select the existing category instead of failing.

#### Scenario: Create while reviewing an import

- **WHEN** the user types "Mascotas" in a review row's picker, chooses "Crear «Mascotas»", picks the "Hogar" group and confirms
- **THEN** "Mascotas" exists under "Hogar", that row has it selected, and the next row's picker lists it

#### Scenario: Last group remembered

- **WHEN** the user creates another category from a picker after creating "Mascotas" under "Hogar"
- **THEN** the creation form preselects "Hogar"

#### Scenario: Exact match offers no creation

- **WHEN** the user types "supermercado" and "Supermercado" exists
- **THEN** the picker lists "Supermercado" and does not offer "Crear «supermercado»"

#### Scenario: Existing name resolves to the existing category

- **WHEN** the creation request returns 409 `category_exists` for the chosen group
- **THEN** the picker selects the existing category with that name and shows no error

