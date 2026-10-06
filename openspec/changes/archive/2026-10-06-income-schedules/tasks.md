## 1. Data model and migration

- [x] 1.1 Extract `ScheduleRuleMixin` (pattern, months, month, every_n, start_month, count, once_month, day, estimated) in `models.py`. Make `PaymentSchedule` use it with no schema change, and add `IncomeSchedule` (`user_id`, `name`, `amount_cents`, `payee_id` FK to `payees` with `ON DELETE SET NULL`, rule columns, `created_at`, index on `user_id`).
- [x] 1.2 Write the Alembic revision:
  - create `income_schedules`;
  - add a data step: for each `user_preferences` row whose `income.expected_monthly_cents` is a positive integer, insert one `monthly` schedule named "Monthly income", with `day` from `income.income_day` when it is between 1 and 31;
  - downgrade drops the table.
- [x] 1.3 Add migration tests: a preference of 470000 on day 27 becomes one schedule; no figure creates nothing; zero or invalid values create nothing.

## 2. Shared rule engine

- [x] 2.1 Type `occurs()` and `payments_in()` in `services/schedules.py` against a `ScheduleRule` Protocol so both models pass. Payment behavior stays unchanged and the existing tests stay green.
- [x] 2.2 Add income input models to `schemas.py`: the monthly, some_months, annual, every_n and once models extended with `payer: str | None` (trimmed, empty clears it), a discriminated `IncomeScheduleIn` union without `no_date`, and `IncomeScheduleOut` with `payee_id`, `payer` (the payee's current name) and `yearly_cents` (next 12 months).

## 3. Income API

- [x] 3.1 Add `routers/income.py` with `GET/POST /income-schedules` and `PATCH/DELETE /income-schedules/{id}`: 422 `invalid_schedule` on validation errors, including `no_date`, and 404 `income_schedule_not_found` for unknown or foreign ids. Resolve `payer` to `payee_id` through the existing payee resolution in `services/payees.py`. `GET` is ordered by day (missing day last). Register it in `main.py`.
- [x] 3.2 Add `services/income.py::month_income(db, user, month)`:
  - occurrences of every schedule in the month;
  - income inflows (confirmed, uncategorized, positive, not transfer twins, not `opening_balance`);
  - the payer pass, matching on `payee_id`, with whole inflows and the 90 % chaining over same-payee occurrences in day order (missing day = month end);
  - the amount pass (±10 %, ±25 % estimated; closest amount, then day);
  - statuses `received`, `pending`, `late` (more than 3 days past, Europe/Madrid via `clock`) and `missed`;
  - `difference_cents` on the last occurrence of a chained inflow, plus the unplanned list.
- [x] 3.3 Add `GET /income/{month}` returning the month income contract (occurrences, unplanned, `expected_cents`, `received_cents`, `still_expected_cents`, `has_schedules`), with schemas in `schemas.py`.
- [x] 3.4 Add tests in `tests/test_income.py` for every income-schedules scenario: 14 pagas, `no_date` rejected, budget untouched, lower salary, salary plus extra pay in one inflow, late versus pending (pinned clock), amount match without payer, a second inflow from the same payer becoming unplanned, the mid-month contract numbers, no schedules, link-by-payee then automatic match next month, payer resolved to an existing payee case-insensitively, payer created before any income, and a schedule-referenced payee surviving an import discard.

- [x] 3.5 Import discard (`services/import_batch.py`): the orphan-payee cleanup also keeps payees referenced by an income schedule.

## 4. Projection and annual plan

- [x] 4.1 Change `services/projection.py`:
  - delete `expected_income` and `set_expected_income`;
  - add the helper `expected_in(schedules, month)`;
  - make later months' money `expected_in(m) + tba`;
  - add `still_expected_cents` from `month_income(M)` to the projected end of M;
  - add `UpcomingMonth.expected_income_cents`, and set the top-level `income_cents` to the Σ over the 12 months;
  - set `income_known` to "has income schedules".
- [x] 4.2 In `summary()`, compute `income_cents` as the Σ of occurrences in the window and `gap_monthly_cents` as `round(gap / 12)`.
- [x] 4.3 Remove `GET/PUT /plan/income` from `routers/plan.py` and the `ExpectedIncome` schema.
- [x] 4.4 Update `tests/test_targets.py`: replace the `/plan/income` setup with income schedules, keep the 60.978,07 € gap scenario numbers, and add scenarios for an extra pay funding its month, the salary still due carrying into next month, and 14 pagas counted in the summary.

## 5. Onboarding

- [x] 5.1 Add `prompts/onboarding_v3.md`: the income phase asks per source for name, payer, net amount, day and 12 or 14 payments, and acknowledges bonuses without extracting them. The extraction schema has `income.sources[]: {name, payer, amount_cents, day, payments_per_year}`. Make it the active version. (The `onboarding` eval suite was updated for the new schema; run by the user on 2026-10-06 with no regressions.)
- [x] 5.2 Update `services/onboarding.py`:
  - proposal income becomes a list of income schedules built deterministically from the sources (monthly, plus "Paga extra" `some_months [6,12]` for 14);
  - map legacy v1/v2 `{expected_monthly_cents, income_day}` to one monthly source;
  - finalize creates the reviewed income schedules in the same transaction;
  - preferences keep the sources as memory only.
- [x] 5.3 Update `tests/test_onboarding.py`: extraction of two sources with 14 pagas, bonus not extracted, the proposal holding two schedules for 14 pagas, finalize creating the edited schedules, atomic rollback including schedules, and legacy session mapping.

## 6. Webapp

- [x] 6.1 Replace the BFF route `src/app/api/plan/income/route.ts` with `api/income-schedules/route.ts` (GET, POST), `api/income-schedules/[id]/route.ts` (PATCH, DELETE) and `api/income/[month]/route.ts` (GET).
- [x] 6.2 `lib/api.ts`: add the income schedule and month income types and functions, add `expected_income_cents` to the upcoming types, drop `getExpectedIncome`/`putExpectedIncome`, and update the onboarding proposal income type. Add TanStack Query hooks with the keys `["income-schedules"]` and `["income", month]`, invalidating upcoming and summary on mutations.
- [x] 6.3 Extract the pattern picker and rule fields from `components/plan/ScheduleEditor.tsx` into `components/plan/ScheduleRuleFields.tsx`, with a prop to hide `no_date`; the sentence stays in `describe()` (`lib/schedules.ts`), widened to income schedules. `ScheduleEditor` behavior stays unchanged.
- [x] 6.4 Add `components/plan/IncomeEditor.tsx`:
  - the 12-month total and monthly average;
  - the schedule list with sentences ("2.000,00 € every month, day 27 · Acme SL");
  - the form (`ScheduleRuleFields` plus amount, day, estimated, a payer combobox from payees);
  - the "14 payments a year" shortcut;
  - an empty state that invites adding income;
  - delete.
  Mount it at Settings → Income and as a sheet from Upcoming payments.
- [x] 6.5 Upcoming payments screen: the income card shows the 12-month expected income with "Edit income", each month row shows `expected_income_cents`, and the inline prompt (amount and day) creates a monthly schedule.
- [x] 6.6 Rewrite `components/budget/IncomeBreakdown.tsx` to read `GET /api/income/{month}`:
  - expected occurrences with status chips (received ± difference, expected day N, not arrived yet in warning, didn't arrive);
  - unplanned income, each with a "This is…" picker that links it (transaction payee PATCH, or schedule `payer` PATCH with the inflow's payee name, per the spec rules);
  - "expected X · received Y";
  - the rest of the hero math unchanged.
- [x] 6.7 Dashboard late-income nudge in `app/(app)/page.tsx`:
  - read `["income", currentMonth]` and show one `CoachCapsule` above "Este mes" when any occurrence is `late` (named when one, count and total when several);
  - "Add it" opens the add-transaction dialog prefilled as income (amount and payer);
  - "It's already here" opens `IncomeBreakdown`;
  - dismissal goes to `localStorage` keyed by month and the sorted late schedule ids, with try/catch;
  - no amounts in telemetry.
- [x] 6.8 Onboarding review screen: add the income section (schedule sentences, editable amount and day, checkboxes) and send the accepted schedules in finalize.

## 7. Docs

- [x] 7.1 Update `project-definition.md`:
  - §3.1 principle 1 (expected income is planned and matched, never assigned);
  - principle 7 (income schedules, 14 pagas);
  - §3.3 ("Did my income arrive?" is part of the month questions);
  - §4.1 row 5;
  - §6.4 data model (`IncomeSchedule`);
  - a §10 resolved entry for income schedules.
- [x] 7.2 Check that the deltas match the implementation: `income-schedules` added; `payment-projection`, `budget-assignment`, `ai-onboarding`, `bff-proxy` and `payees` modified.

## 8. Verification

- [x] 8.1 `uv run pytest` green in `backend/`.
- [x] 8.2 Type check and lint green in `webapp/`. Run the build with `NEXT_DIST_DIR=.next-verify` if the dev server is running.
- [x] 8.3 e2e:
  - update `category-targets.spec.ts` (income set via the inline prompt now creates a schedule, and the projection numbers are unchanged);
  - update `categorization-review.spec.ts` where it relies on expected income;
  - update `e2e/support/app.ts` and the seed if they set `expected_monthly_cents`;
  - add `e2e/income.spec.ts`: add 14 pagas in Settings → Income, see the June row's expected income in Upcoming payments, record a lower salary, and see "received · X € less" in the budget breakdown; link an unplanned inflow with "This is…"; with the clock pinned past day + 3, see the dashboard capsule, use "Add it" and see the capsule disappear;
  - `volta run npm run e2e` green.
