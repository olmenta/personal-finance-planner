# payment-projection Specification

## Purpose

The 12-month upcoming-payments timeline with priority-allocation coverage, the annual plan summary against the expected income of the income schedules, and the "Próximos pagos" screen.

## Requirements

### Requirement: Upcoming payments projection

The API SHALL expose `GET /plan/upcoming?from=YYYY-MM`, returning 12 months.

- **First month.** It SHALL report the month overview's real coverage.
- **Each later month** SHALL be simulated from the projected end of the previous month:
  - scheduled categories keep what's left after their pending payments;
  - savings keep their available;
  - flexible categories start at zero;
  - positive To Be Assigned carries;
  - the first month's projected end SHALL also include its still-expected income (the amounts of its `pending` and `late` income occurrences, see income-schedules).
- **Money of a later month** is that month's expected income (Σ of its income-schedule occurrences) plus the carried To Be Assigned. It is allocated in priority order: (1) payments due that month, (2) flexible categories' current assignments, (3) catch-up set-asides for later payments, (4) `no_date` goals. A level that doesn't fit is filled pro-rata, and leftovers are carried unassigned.
- **Per month** the response SHALL report `expected_income_cents`, its occurrences with `covered` and `short_cents`, `flexible_funded_cents` versus `flexible_budget_cents`, `set_aside_funded_cents` versus `set_aside_wanted_cents`, and `unassigned_cents`. The top-level `income_cents` SHALL be the Σ of expected income over the 12 months.
- **No income schedules.** The response SHALL set `income_known = false` and report occurrences without coverage.

#### Scenario: Future payment at risk is flagged early

- **WHEN** income only covers each month's due payments and day-to-day, and a 500,00 € annual payment falls in March with nothing set aside
- **THEN** March reports that occurrence with `covered = false` and its `short_cents`, visible in the October projection

#### Scenario: Structural gap surfaces as unfunded set-asides

- **WHEN** the plan costs more per year than the expected income but each month's dated payments fit
- **THEN** every payment reports covered, and the months report `set_aside_funded_cents` below `set_aside_wanted_cents`

#### Scenario: Extra pay funds its month

- **WHEN** the user expects 2.000,00 € every month plus 2.000,00 € in June and December, and a 3.500,00 € payment falls in June
- **THEN** June reports `expected_income_cents = 400000` and the payment can be covered from that month's money, while May reports `expected_income_cents = 200000`

#### Scenario: Salary still due this month carries forward

- **WHEN** on 14 October the 2.800,00 € salary for day 27 is still `pending` and October's real To Be Assigned is 0
- **THEN** November's money is November's expected income plus 2.800,00 € carried from October

#### Scenario: No income known

- **WHEN** the user has no income schedules
- **THEN** the projection returns occurrences and totals with `income_known = false` and no coverage flags

### Requirement: Annual plan summary and expected income

`GET /plan/summary?from=YYYY-MM` SHALL return, for the 12-month window starting at `from`:

- `income_cents`: Σ of every income-schedule occurrence in the window, received or not;
- `scheduled_cents`: Σ of payment occurrences;
- `flexible_cents`: flexible categories' assignments of `from` × 12;
- `goals_cents`: Σ of `no_date` amounts;
- `gap_cents`: income − costs;
- `gap_monthly_cents`: `gap_cents` ÷ 12, rounded.

Expected income SHALL come only from income schedules. `GET /plan/income` and `PUT /plan/income` SHALL NOT exist. Probable income (bonuses) SHALL have no field.

#### Scenario: Plan doesn't fit the income

- **WHEN** the user expects 4.700,00 € every month and the window's costs total 60.978,07 €
- **THEN** the summary reports `income_cents = 5640000`, `gap_cents = -457807` and `gap_monthly_cents = -38151`

#### Scenario: Fourteen pagas counted once each

- **WHEN** the user expects 2.000,00 € monthly plus 2.000,00 € in June and December
- **THEN** the summary's `income_cents` is 2800000

### Requirement: Upcoming payments screen

The webapp SHALL provide an "Upcoming payments" screen (a sidebar entry, reachable from the dashboard on mobile). It SHALL show three summary cards:

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

- **WHEN** the user opens Upcoming payments
- **THEN** the gap card reads the yearly and monthly amounts and each month row shows its expected income, payment total and funding bars

#### Scenario: Asking for income

- **WHEN** the user has no income schedules
- **THEN** an inline prompt "Add your monthly income to see what's covered" creates a monthly income schedule through `POST /api/income-schedules`, and the rows then show coverage
