## MODIFIED Requirements

### Requirement: Category assignment list

The screen SHALL render one panel per category group, each row showing the category (icon chip + name) and three labeled amounts, in this order: **Assigned**, **Spent** (labeled **Paid** for card payment categories) and **Available**, where `available = assigned + rollover − spent`.

- **Desktop (1024px and wider):** the labels SHALL appear once at the top of each group panel as column headers aligned with the amounts, and the group's subtotals of assigned, spent and available SHALL sit in the same columns.
- **Mobile:** each row SHALL show the three amounts on a second line under the name, each with its label.
- **Spent** SHALL be the API's `spent_cents` in neutral text, negative when refunds exceed purchases. It SHALL NOT repeat in the subtitle under the name.
- **Carry-over:** when a category carries money from last month (`rollover_cents ≠ 0`), the row SHALL show it under the assigned amount ("+32,00 € from last month"), so the visible amounts add up to Available. For card payment categories, the money set aside from card purchases SHALL appear there too.
 The available amount SHALL be colored by sign: mint when positive, neutral gray when zero, expense red when negative. Only the assigned amount SHALL be editable. An overspent row SHALL offer a one-tap cover action built from the API's `cover_suggestion` ("Cubrir desde Restaurantes" / "Cubrir desde lo sin asignar"), and every row SHALL offer a "Move money" action.

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

#### Scenario: Three labeled amounts

- **WHEN** Supermercado has 300,00 € assigned, nothing carried over and 138,00 € spent, on a 1280px-wide screen
- **THEN** its row shows 300,00 € under "Assigned", 138,00 € under "Spent" and 162,00 € under "Available", and the group's header row labels those three columns with their subtotals

#### Scenario: Carry-over visible

- **WHEN** a category has 32,00 € rollover, 120,00 € assigned and 138,00 € spent
- **THEN** its row shows "+32,00 € from last month" under the assigned amount, 138,00 € spent and 14,00 € available

#### Scenario: Labeled on mobile

- **WHEN** the viewport is 390px wide
- **THEN** each row shows Assigned, Spent and Available with their labels on a second line under the name, and tapping the assigned amount opens the numpad sheet

#### Scenario: Card payment category

- **WHEN** a card's payment category received a 150,00 € payment this month
- **THEN** its middle amount is labeled "Paid" and shows 150,00 €
