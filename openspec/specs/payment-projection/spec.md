# payment-projection Specification

## Purpose

The 12-month upcoming-payments timeline with priority-allocation coverage, the annual plan summary with editable expected fixed income, and the "Próximos pagos" screen.

## Requirements

### Requirement: Upcoming payments projection

The API SHALL expose `GET /plan/upcoming?from=YYYY-MM` returning 12 months. The first month SHALL report the month overview's real coverage. Each later month SHALL be simulated from the projected end of the previous month (scheduled categories keep what's left after their pending payments, savings keep their available, flexible categories start at zero, positive To Be Assigned carries), allocating the expected fixed monthly income plus carried To Be Assigned in priority order — (1) payments due that month, (2) flexible categories' current assignments, (3) catch-up set-asides for later payments, (4) `no_date` goals — pro-rata within a level that doesn't fit, leftovers carried unassigned. Each month SHALL report its occurrences with `covered` and `short_cents`, `flexible_funded_cents` versus `flexible_budget_cents`, `set_aside_funded_cents` versus `set_aside_wanted_cents`, and `unassigned_cents`. When no expected fixed income is known, the response SHALL set `income_known = false` and report occurrences without coverage.

#### Scenario: Future payment at risk is flagged early

- **WHEN** income only covers each month's due payments and day-to-day, and a 500,00 € annual payment falls in March with nothing set aside
- **THEN** March reports that occurrence with `covered = false` and its `short_cents`, visible in the October projection

#### Scenario: Structural gap surfaces as unfunded set-asides

- **WHEN** the plan costs more per year than the expected income but each month's dated payments fit
- **THEN** every payment reports covered, and the months report `set_aside_funded_cents` below `set_aside_wanted_cents`

#### Scenario: No income known

- **WHEN** the user never provided expected monthly income
- **THEN** the projection returns occurrences and totals with `income_known = false` and no coverage flags

### Requirement: Annual plan summary and expected income

`GET /plan/summary?from=YYYY-MM` SHALL return, for the 12-month window starting at `from`: `income_cents` (expected fixed monthly income × 12), `scheduled_cents` (Σ occurrences), `flexible_cents` (flexible categories' assignments of `from` × 12), `goals_cents` (Σ `no_date` amounts), `gap_cents` (income − costs) and `gap_monthly_cents`. `GET /plan/income` and `PUT /plan/income {expected_monthly_cents ≥ 0}` SHALL read and write the expected fixed monthly income stored in the preferences document (`income.expected_monthly_cents`, the field onboarding fills). Probable income (bonuses) SHALL have no field.

#### Scenario: Plan doesn't fit the income

- **WHEN** expected income is 4.700,00 €/month and the window's costs total 60.978,07 €
- **THEN** the summary reports `income_cents = 5640000`, `gap_cents = -457807` and `gap_monthly_cents = -38151`

#### Scenario: Editing expected income

- **WHEN** the user sets expected income to 4.700,00 €
- **THEN** `GET /plan/income` returns `expected_monthly_cents = 470000` and the preferences document's `income.expected_monthly_cents` holds the same value

### Requirement: Upcoming payments screen

The webapp SHALL provide an "Upcoming payments" screen (sidebar entry; reachable from the dashboard on mobile) with three summary cards (expected fixed income for the next 12 months, planned costs split into payments / day-to-day / goals, and the yearly and monthly gap), then one expandable row per month showing its total payments, a "payments covered" or "short X €" chip, and two funding bars ("day-to-day" and "set aside"), expanding to the month's payment list with per-payment status and an explanation when set-asides fall short. When expected income is unknown, the screen SHALL ask for it inline instead of showing coverage.

#### Scenario: Reading the year at a glance

- **WHEN** the user opens Upcoming payments
- **THEN** the gap card reads the yearly and monthly amounts and each month row shows its payment total and funding bars

#### Scenario: Asking for income

- **WHEN** expected income is unknown
- **THEN** an inline prompt "Add your monthly income to see what's covered" saves it through `PUT /api/plan/income` and the rows then show coverage
