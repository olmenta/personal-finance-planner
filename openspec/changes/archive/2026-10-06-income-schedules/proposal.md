## Why

The plan knows expected income only as one number, `income.expected_monthly_cents` in the preferences document. It has no source, date or rule. That breaks real Spanish households: 14 pagas (extra pays in June and December are fixed income, not bonuses), two salaries on different days, or a pension plus a rental. Nothing links the planned salary to the transaction that actually arrives, so the user never sees "expected 2.800 € on the 27th, 2.750 € arrived", or that this month's salary hasn't come in yet. The projection also ignores salary still due this month when it simulates the next one.

## What Changes

- **New: income schedules.** Expected income becomes a list of user-level schedules: name, amount, optional payer (a reference to the user's payee, resolved by name on write), rule, optional day and `estimated` flag. The rules reuse the payment-schedule patterns `monthly` (optionally finite), `some_months`, `annual`, `every_n` and `once`. There is no `no_date`, because undated income can't be planned. Probable money (bonuses that depend on targets) still has no place: it is never scheduled.
- **New: expected versus received.** Each expected occurrence in a month is matched, at read time, against the month's real income: confirmed uncategorized inflows, the same rule as `income_cents`. Matching uses the payer when the schedule has one, otherwise the amount. Each occurrence reports `received` (with any difference), `pending`, `late` or `missed`. An inflow that matches nothing is "unplanned income". A user links an unmatched inflow to an occurrence by giving it the schedule's payer, so no link table is needed.
- **Principle 1 unchanged.** Only real income transactions feed To Be Assigned. Income schedules never create transactions, never fund categories and never appear in the budget math. They feed the plan, which is the projection and the annual summary, plus the expected-versus-received view.
- **Projection and annual plan read schedules.** Each future month's money becomes the sum of its expected occurrences instead of a flat monthly figure. The current month's still-expected income (pending or late) is carried into the next month. The annual `income_cents` becomes the sum of occurrences in the 12-month window. `income_known` becomes "the user has at least one income schedule".
- **BREAKING:** `GET /plan/income` and `PUT /plan/income` are removed, along with the BFF route and the `expected_monthly_cents` preference as the source of truth. They are replaced by `GET/POST /income-schedules`, `PATCH/DELETE /income-schedules/{id}` and `GET /income/{month}` (the occurrences with their status).
- **Data migration.** An existing `expected_monthly_cents` (with `income_day`, if known) becomes one `monthly` income schedule. Users with no income stay without schedules.
- **Onboarding fills schedules.** The extraction schema captures income sources, each with amount, day and 12 or 14 pagas. The proposal lists income schedules and finalize creates them, together with their payers, under a bumped prompt version. Fourteen pagas become a monthly schedule plus a `some_months` [6, 12] extra-pay schedule.
- **Webapp.** A new income editor (Settings → Income) uses the same sentence-style form as payments. The Upcoming payments income card and inline prompt create schedules instead of typing one number, and each month row shows its expected income. The budget screen's income breakdown lists the month's expected occurrences with their status, plus unplanned income.
- **Late-income nudge.** While a salary is late (more than 3 days past its day), the dashboard shows a coach capsule with "Add it" and "It's already here".
- **Docs.** Update project-definition §3 (principles 1 and 7, §3.3), §4.1 row 5, §6.4 and the §10 decisions log.

## Capabilities

### New Capabilities

- `income-schedules`: income schedule CRUD, rules and occurrences, matching of real income to expected occurrences and its statuses, the `GET /income/{month}` contract, the migration from the single expected figure, and the income editor UI.

### Modified Capabilities

- `payment-projection`: the upcoming projection and the annual summary take income from income schedules (per-month occurrences, carrying the current month's still-expected income). `GET/PUT /plan/income` are removed. The Upcoming payments screen's income card and inline prompt work with schedules.
- `budget-assignment`: the income breakdown shows expected occurrences with received, pending, late or missed status, and unplanned income, instead of one expected total from `/plan/income`.
- `ai-onboarding`: income extraction and the setup proposal carry income sources (amount, day, extra pays), finalize creates income schedules and their payers, and preferences no longer hold `expected_monthly_cents` as the planning source.
- `payees`: payees are also born from income schedule writes (same resolution, still no public endpoint), and discarding an import keeps payees an income schedule references.
- `bff-proxy`: the `/api/plan/income` route is replaced by the `/api/income-schedules` and `/api/income/{month}` routes.

## Impact

- **Backend:** new `income_schedules` table and Alembic migration (schema plus preferences data migration). Pattern validation and `occurs()` in `services/schedules.py` are generalized so both schedule kinds share them. A new `services/income.py` handles occurrences and matching. `services/projection.py` changes (it drops `expected_income`/`set_expected_income`), and so do `routers/plan.py`, a new `routers/income.py`, `schemas.py`, `services/onboarding.py`, `services/import_batch.py` (orphan-payee cleanup) and a new `prompts/onboarding_v3.md`.
- **Webapp:** `lib/api.ts`, the `api/plan/income` route (removed), new `api/income-schedules` and `api/income/[month]` routes, `IncomeBreakdown.tsx`, the Upcoming payments screen, a new Settings → Income editor, and the onboarding review screen's income section.
- **Tests:** backend `test_targets.py` (plan income), `test_onboarding.py`, new income tests. E2E `category-targets.spec.ts` and `categorization-review.spec.ts` need updates, plus a new income spec.
- **Unaffected:** budget math, To Be Assigned, month overview identity, transactions, import parsing and the MCP server, which never read expected income.
