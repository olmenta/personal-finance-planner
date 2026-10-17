## MODIFIED Requirements

### Requirement: Upcoming payments screen

The webapp SHALL provide the "Future" screen at `/future` (one of the five destinations; `/upcoming` redirects to it, see navigation), titled "Future" and showing upcoming payments. It SHALL show three summary cards:

- expected income for the next 12 months, with an "Edit income" link to the income editor;
- planned costs, split into payments, day-to-day and goals;
- the yearly and monthly gap.

Below the cards SHALL come one expandable row per month showing:

- its expected income and total payments;
- a "payments covered" or "short X €" chip;
- two funding bars, "day-to-day" and "set aside".

A row SHALL expand to the month's payment list with per-payment status, plus an explanation when set-asides fall short.

When the user has no income schedules, the screen SHALL ask for income inline instead of showing coverage. The inline prompt takes an amount and a day and creates a `monthly` income schedule through `POST /api/income-schedules`.

#### Scenario: Reading the year at a glance

- **WHEN** the user opens Future
- **THEN** the gap card reads the yearly and monthly amounts and each month row shows its expected income, payment total and funding bars

#### Scenario: Asking for income

- **WHEN** the user has no income schedules
- **THEN** an inline prompt "Add your monthly income to see what's covered" creates a monthly income schedule through `POST /api/income-schedules`, and the rows then show coverage
