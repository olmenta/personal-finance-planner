## ADDED Requirements

### Requirement: Income schedules CRUD

The API SHALL expose `GET /income-schedules`, `POST /income-schedules`, `PATCH /income-schedules/{id}` and `DELETE /income-schedules/{id}`. Income schedules belong to the user, not to a category. Each schedule SHALL carry `name`, `amount_cents > 0`, an optional payer, a `pattern` and the pattern's fields, an optional `day` (1–31), and `estimated` (default false, for income whose amount varies). The patterns and their fields SHALL be the payment-schedule patterns `monthly` (optional `count` with `start_month`), `some_months` (`months`), `annual` (`month`), `every_n` (`every_n`, `start_month`) and `once` (`once_month`), with the same validation. `no_date` SHALL be rejected.

The payer SHALL be stored as `payee_id`, a reference to the user's payee. Writes accept a `payer` name, resolved through the payee resolution rule (case-insensitive match on the trimmed name, or create) and stored as `payee_id`. An empty `payer` clears it. Reads return both `payee_id` and the payee's current name as `payer`.

Missing, contradictory or unsupported pattern fields SHALL return 422 `invalid_schedule`. An unknown or foreign schedule SHALL return 404. `GET /income-schedules` SHALL return the schedules ordered by day, each with its sentence fields and its yearly amount over the next 12 months.

Income schedules SHALL NOT create transactions, change To Be Assigned, or take part in budget math. There SHALL be no field for probable income (bonuses that depend on targets).

#### Scenario: Fourteen payments a year

- **WHEN** the user creates `{name: "Nómina", payer: "Acme SL", amount_cents: 200000, pattern: "monthly", day: 27}` and `{name: "Paga extra", payer: "Acme SL", amount_cents: 200000, pattern: "some_months", months: [6, 12], day: 20}`
- **THEN** both return 201, and June and December each expect 4.000,00 € while every other month expects 2.000,00 €

#### Scenario: Payer resolved to an existing payee

- **WHEN** the user has a payee "Acme SL" from an earlier transaction and creates a schedule with `payer: "ACME SL"`
- **THEN** the schedule references that payee's id, no new payee is created, and `GET /income-schedules` shows `payer: "Acme SL"`

#### Scenario: Payer created before any income arrives

- **WHEN** the user creates a schedule with `payer: "Inquilino Piso"` and no payee of that name exists
- **THEN** the payee "Inquilino Piso" is created, appears in `GET /payees`, and the schedule references it

#### Scenario: Undated income rejected

- **WHEN** a client posts `{name: "Freelance", amount_cents: 50000, pattern: "no_date"}`
- **THEN** the API returns 422 `invalid_schedule`

#### Scenario: Schedules don't touch the budget

- **WHEN** the user creates a 2.000,00 € monthly income schedule for day 27 on 6 October
- **THEN** October's `income_cents` and `to_be_assigned_cents` are unchanged

### Requirement: Expected income occurrences matched to real income

For each month, the backend SHALL list every income schedule's occurrences in that month. It SHALL match them, at read time and without persisting links, against the month's **income inflows**: confirmed uncategorized positive transactions that are not transfer twins (the `income_cents` rule), excluding `opening_balance` rows. Matching SHALL run in two passes:

1. **By payer.** Inflows whose `payee_id` equals a schedule's `payee_id` are taken in date order. Each goes whole to the earliest occurrence with that payer not yet received. The occurrences are ordered by day, and a missing day counts as the last day of the month. If the inflow also reaches at least 90 % of the sum including the next unreceived occurrence with that payer, it covers that one too, and so on. An inflow that finds no unreceived occurrence stays unmatched.
2. **By amount.** Each inflow still unmatched goes whole to the unreceived occurrence of a schedule without a payer whose amount is within 10 % of the inflow (25 % when `estimated`). When several fit, the closest amount wins, then the closest day.

Each occurrence SHALL report `received_cents` and a `status`:

- `received`: an inflow was assigned to it. When one inflow covers several occurrences, each receives its own amount and the last takes the difference. `difference_cents = received_cents − amount_cents`.
- `late`: nothing allocated, in the current month, and today (Europe/Madrid) is more than 3 days past its day.
- `pending`: nothing allocated, and not late.
- `missed`: nothing allocated in a past month.

Every future month's occurrences are `pending`. Inflows left unmatched SHALL be reported as unplanned income.

#### Scenario: Salary arrives a little lower

- **WHEN** "Nómina" (payer "Acme SL", 2.800,00 €, day 27) is expected and a 2.750,00 € inflow from payee "ACME SL" is confirmed on 27 October
- **THEN** October's occurrence is `received` with `received_cents = 275000` and `difference_cents = -5000`

#### Scenario: Salary and extra pay in one transfer

- **WHEN** in June "Nómina" (2.000,00 €, day 27) and "Paga extra" (2.000,00 €, day 20), both with payer "Acme SL", meet one 4.000,00 € inflow from "Acme SL" on 25 June
- **THEN** both occurrences are `received` with `difference_cents = 0`

#### Scenario: Salary hasn't arrived

- **WHEN** today is 31 October, "Nómina" is expected on day 27 and no matching inflow exists
- **THEN** the occurrence is `late`, and on 28 October it would still have been `pending`

#### Scenario: Matching by amount without payer

- **WHEN** a schedule without payer expects 1.200,00 € and an imported uncategorized inflow of 1.180,00 € with no payee arrives that month
- **THEN** the occurrence is `received` with `difference_cents = -2000`

#### Scenario: Bonus is unplanned income

- **WHEN** October's "Nómina" from "Acme SL" was already received and a second 900,00 € inflow from "Acme SL" arrives on 30 October
- **THEN** the salary occurrence keeps its difference unchanged and the 900,00 € inflow is listed under unplanned income

### Requirement: Month income contract

The API SHALL expose `GET /income/{month}` returning, in integer cents: `occurrences` (each with `schedule_id`, `name`, `payee_id`, `payer`, `day`, `amount_cents`, `estimated`, `received_cents`, `difference_cents`, `status`, and the matched `transaction_ids`), `unplanned` (the unmatched income inflows with `transaction_id`, payee or description, day and amount), `expected_cents` (Σ occurrence amounts), `received_cents` (Σ income inflows, equal to the month's `income_cents` minus opening balances), `still_expected_cents` (Σ amounts of `pending` and `late` occurrences), and `has_schedules`.

#### Scenario: Mid-month read

- **WHEN** on 14 October the user expects "Pensión" 900,00 € on day 1 (received) and "Nómina" 2.800,00 € on day 27
- **THEN** the response reports `expected_cents = 370000`, `received_cents = 90000`, `still_expected_cents = 280000`, "Pensión" `received` and "Nómina" `pending`

#### Scenario: No schedules

- **WHEN** the user has no income schedules and received a 2.400,00 € inflow
- **THEN** the response reports `has_schedules = false`, no occurrences, and the inflow under `unplanned`

### Requirement: Linking unplanned income to a schedule

The webapp SHALL let the user link an unplanned inflow to an expected occurrence of the same month without a link table, through payer equality:

- When the schedule has a payee, the inflow gets that payee through `PATCH /transactions/{id}`.
- When the schedule has no payee and the inflow has one, the schedule gets the inflow's payee through `PATCH /income-schedules/{id}`.
- When neither has one, the schedule's name becomes a payee resolved for both.

After linking, the next read SHALL report the occurrence as `received`, and later inflows from that payer SHALL match automatically.

#### Scenario: Link once, matched forever

- **WHEN** an unplanned 1.180,00 € inflow with payee "Inquilino Piso" is linked to "Alquiler piso" (no payer)
- **THEN** "Alquiler piso" references the payee "Inquilino Piso", the occurrence becomes `received`, and next month's inflow from "Inquilino Piso" matches without linking

### Requirement: Migration from the single expected income

A migration SHALL convert each preferences document's `income.expected_monthly_cents` (when it is a non-negative integer greater than zero) into one `monthly` income schedule named "Monthly income", with `day` taken from `income.income_day` when present and no payer. Users without that field SHALL get no schedules. After the migration, no code path SHALL read `expected_monthly_cents` for planning.

#### Scenario: Existing expected income migrated

- **WHEN** a user's preferences hold `expected_monthly_cents = 470000` and `income_day = 27`
- **THEN** after the migration the user has one `monthly` income schedule of 4.700,00 € on day 27, and the projection reports the same coverage as before for months without pending income

#### Scenario: Nothing to migrate

- **WHEN** a user's preferences have no income figure
- **THEN** the user has no income schedules and the projection reports `income_known = false`

### Requirement: Income editor

The webapp SHALL offer an income editor at Settings → Income, also reachable from the Upcoming payments income card. It SHALL show:

- the expected income for the next 12 months and its monthly average;
- the list of income schedules, each with its sentence description ("2.000,00 € every month, day 27 · Acme SL");
- the sentence-style form shared with the payment editor, with the patterns monthly, some months, once a year, every N months and once (no "no date"), plus amount, day, an estimated toggle, and a payer field with autocomplete from `GET /api/payees`;
- a "14 payments a year" shortcut on a monthly schedule that adds an extra-pay schedule for June and December with the same amount and payer.

Empty state SHALL invite adding the first income, never apologize.

#### Scenario: Adding fourteen pagas

- **WHEN** the user enters 2.000 € monthly, day 27, payer "Acme SL", and taps "14 payments a year"
- **THEN** two schedules are saved and the 12-month total reads 28.000,00 €

#### Scenario: Empty income

- **WHEN** the user has no income schedules
- **THEN** the editor invites "Add your income to see if your plan fits" with the form ready

### Requirement: Late income nudge on the dashboard

While the current month has at least one `late` income occurrence, the dashboard SHALL show one coach capsule above the "Este mes" panel. With a single late occurrence it SHALL name it: "Your Nómina (2.800,00 €) usually arrives on the 27th and isn't here yet". With several, it SHALL give their count and total. It SHALL offer:

- "Add it", which opens the add-transaction dialog as income, prefilled with the occurrence's amount and payer;
- "It's already here", which opens the income breakdown so the user can link an unplanned inflow;
- a dismiss control.

Dismissal SHALL hide the capsule for those late occurrences in the current month only. It is a per-browser convenience, and a newly late occurrence brings the capsule back. The capsule SHALL disappear as soon as no occurrence is late. The amounts and payer SHALL NOT be sent to analytics or logs.

#### Scenario: Salary late

- **WHEN** on 31 October "Nómina" (2.800,00 €, day 27) has no matching inflow
- **THEN** the dashboard shows the coach capsule naming it, with "Add it" and "It's already here"

#### Scenario: Not yet late

- **WHEN** on 29 October "Nómina" (day 27) has no matching inflow
- **THEN** no capsule is shown, because the occurrence is still `pending` within the 3-day grace

#### Scenario: Arrival clears the nudge

- **WHEN** the user taps "Add it" and saves the prefilled 2.800,00 € income
- **THEN** the occurrence becomes `received` and the capsule disappears
