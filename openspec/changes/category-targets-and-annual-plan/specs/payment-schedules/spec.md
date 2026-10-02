# payment-schedules Delta Specification

## ADDED Requirements

### Requirement: Category kinds

Every category SHALL have a `kind` of `flexible` (day-to-day spending), `scheduled` (payments with a calendar) or `savings` (money set aside without a due date), defaulting to `flexible`. The kind SHALL NOT change available, rollover or To Be Assigned math; it SHALL decide the draft rule, the home-screen bucket, and the projection priority.

#### Scenario: Existing categories default to flexible

- **WHEN** the migration runs on a database with categories
- **THEN** every existing category has `kind = "flexible"` and its budget numbers are unchanged

#### Scenario: Kind changes presentation only

- **WHEN** a category with 120,00 € available changes from `flexible` to `savings`
- **THEN** its available is still 120,00 € and it moves from "left to spend" to "saved for the future" on the home screen

### Requirement: Payment schedules CRUD

The API SHALL expose `GET /categories/{id}/schedules`, `POST /categories/{id}/schedules`, `PATCH /schedules/{id}` and `DELETE /schedules/{id}`. A schedule SHALL carry `name`, `amount_cents > 0`, a `pattern` and the pattern's fields, an optional `day` (1–31), and `estimated` (default false):

| pattern | required fields | meaning |
|---|---|---|
| `monthly` | — (optional `count` with `start_month`) | every month, or `count` payments from `start_month` |
| `some_months` | `months` (non-empty list of 1–12) | in those calendar months every year |
| `annual` | `month` (1–12) | once a year in that month |
| `every_n` | `every_n` (2–12), `start_month` | every N months from `start_month` |
| `once` | `once_month` | a single payment in that month |
| `no_date` | — | an annual goal of `amount_cents`, no occurrences |

Missing or contradictory fields for the pattern SHALL return 422 `invalid_schedule`; an unknown or foreign category or schedule SHALL return 404. A category MAY hold several schedules.

#### Scenario: School fees September to June

- **WHEN** the user adds `{name: "Cuota del colegio", amount_cents: 63200, pattern: "some_months", months: [9,10,11,12,1,2,3,4,5,6], day: 5}` to "Colegio Tomi"
- **THEN** the API returns 201 and the schedule occurs in each of those months and never in July or August

#### Scenario: Quarterly water bill

- **WHEN** a schedule `{amount_cents: 12000, pattern: "every_n", every_n: 3, start_month: "2026-11", estimated: true}` exists
- **THEN** it occurs in November 2026, February, May and August 2027

#### Scenario: Finite monthly payments

- **WHEN** a schedule `{amount_cents: 2329, pattern: "monthly", count: 4, start_month: "2026-10"}` exists
- **THEN** it occurs October 2026 to January 2027 and never after

#### Scenario: Invalid pattern fields rejected

- **WHEN** a client posts `{pattern: "annual", amount_cents: 50000}` without `month`
- **THEN** the API returns 422 with code `invalid_schedule`

### Requirement: Normal and catch-up monthly amounts

For each category with schedules and each month M, the backend SHALL compute the **normal amount** (per schedule: `monthly` = amount while active; `some_months` = amount × months ÷ 12; `annual` = amount ÷ 12; `every_n` = amount ÷ N; `no_date` = amount ÷ 12; `once` = 0) summed over the category, and the **catch-up amount**: the maximum over months j from M to M+11 of `(Σ payments from M to j − saved) ÷ (j − M + 1)`, floored at zero, where `saved` is the category's rollover at the start of M. The **suggested amount** SHALL be the larger of the two, rounded up to the cent.

#### Scenario: Colegio with nothing saved

- **WHEN** "Colegio Tomi" has the September–June fee of 632,00 €, books 228,00 € in September, AMPA 60,00 € in October and 387,00 € in February, and nothing saved at the start of October 2026
- **THEN** October's normal amount is 582,92 € and its catch-up amount is 721,40 €, so the suggestion is 721,40 €

#### Scenario: Caught up falls back to normal

- **WHEN** a category with a single 500,00 € annual payment in March has 250,00 € saved at the start of October
- **THEN** its catch-up amount is 41,67 € (250 € over 6 months) and its suggestion equals the normal amount of 41,67 €

#### Scenario: One-off payment

- **WHEN** a category's only schedule is 1.000,00 € `once` in December and nothing is saved in October
- **THEN** its normal amount is 0 and its catch-up amount is 333,34 €

### Requirement: Schedule editor

The webapp SHALL offer a schedule editor for a category, opened from its budget row ("Set up payments") and from Settings → categories, showing: a kind selector (Day-to-day / Scheduled / Savings); the category's payments, each with its sentence description ("632,00 € from September to June, day 5") and per-payment normal amount; a sentence-style form for the selected payment (pattern picker, amount, month chips for `some_months`, month for `annual`, interval and start for `every_n`, month for `once`, count for finite `monthly`, day, estimated toggle); the category's normal and catch-up amounts updating as the form changes; and a 12-month bar chart of the category's projected balance under the normal amount and under the suggested amount, with shortfall bars in the warning color.

#### Scenario: Describing a payment once

- **WHEN** the user picks "Some months", taps Sep through Jun, enters 632 and day 5
- **THEN** the sentence reads "632,00 € from September to June, day 5" and the normal amount shows 526,67 € for that payment

#### Scenario: Behind shows the catch-up

- **WHEN** the category's catch-up amount exceeds its normal amount
- **THEN** the catch-up card is highlighted with "You're behind — set this aside this month" and the chart shows where the normal amount would fall short
