## MODIFIED Requirements

### Requirement: Upcoming payments projection

The API SHALL expose `GET /plan/upcoming?from=YYYY-MM`, returning 12 months.

- **First month.** It SHALL report the month overview's real coverage.
- **Each later month** SHALL be simulated from the projected end of the previous month:
  - scheduled categories keep what's left after their pending payments;
  - savings keep their available;
  - flexible categories start at zero;
  - To Be Assigned carries **signed**: the first month's projected end SHALL start from its real To Be Assigned (negative when more was assigned than the money that arrived), minus its cash overspending (`overspent_cents`) and minus the uncovered part of its pending payments (Σ `short_cents`, which will become overspending when paid), plus its still-expected income (the amounts of its `pending` and `late` income occurrences, see income-schedules). A deficit SHALL never be clipped to zero; later months' uncovered payments keep reducing the carried balance as before.
- **Money of a later month** is that month's expected income (Σ of its income-schedule occurrences) plus the carried To Be Assigned. It is allocated in priority order: (1) payments due that month, (2) flexible categories' current assignments, (3) catch-up set-asides for later payments, (4) `no_date` goals. A level that doesn't fit is filled pro-rata **in whole cents**: each item gets the floor of its share and the remaining cents go one by one to the items with the largest remainders (ties by priority order), so the allocated cents never exceed the money available. Coverage and `short_cents` SHALL be computed on those integer amounts. Leftovers are carried unassigned.
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

#### Scenario: A current deficit is not forgotten

- **WHEN** October has a 100,00 € payment assigned with no money (To Be Assigned −100,00 €) and a 100,00 € salary is expected only from November, when another 100,00 € payment falls
- **THEN** November reports that payment with `covered = false` and `short_cents = 10000`

#### Scenario: One cent can't cover two

- **WHEN** a month has two 0,01 € payments due and 0,01 € to allocate
- **THEN** one payment reports `covered = true` and the other `covered = false` with `short_cents = 1`
