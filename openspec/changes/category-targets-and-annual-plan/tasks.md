# Tasks: category targets and annual plan

> Depends on `budget-rules`, which is implemented but not yet archived. Its manual check (6.3) and archive should happen before this change syncs. The `bff-proxy` delta is written on top of its wording.

## 1. Data layer

- [ ] 1.1 `models.py`: `Category.kind` (String, default `"flexible"`, not null); `PaymentSchedule` model per design D2; Alembic migration with downgrade
- [ ] 1.2 Schemas: `ScheduleIn` discriminated union per pattern (422 `invalid_schedule`), `ScheduleOut`; `kind` on category out/in

## 2. Schedules and amounts (backend)

- [ ] 2.1 `services/schedules.py`: `occurs(schedule, month)`, normal amount per pattern, category normal, catch-up amount (design D3), suggested amount rounded up to the cent
- [ ] 2.2 Routes: `GET/POST /categories/{id}/schedules`, `PATCH/DELETE /schedules/{id}` (404 for unknown or foreign ids)
- [ ] 2.3 Categories API: `kind` in the tree, and on POST and PATCH (422 on unknown values)
- [ ] 2.4 Drafting (design D4): `materialize_month` drafts scheduled categories and savings categories with goals at the suggested amount, including in the first month; the rest keep copying the previous month
- [ ] 2.5 Budget view: `kind`, `normal_cents`, `catch_up_cents` per category

## 3. Month overview (backend)

- [ ] 3.1 `services/overview.py`: today in Europe/Madrid (injectable), matching spending to occurrences in day order (estimated occurrences count as paid once any spending lands), buckets per design D5, `accounts_cents`
- [ ] 3.2 `GET /overview/{month}` route and response schema

## 4. Projection, summary, income (backend)

- [ ] 4.1 `services/projection.py`: port the prototype `simulate` (priority allocation, pro-rata within a level, carry) starting from the overview's projected end of month M (design D6); `income_known = false` path
- [ ] 4.2 `GET /plan/upcoming?from=`, `GET /plan/summary?from=` (design D7)
- [ ] 4.3 `GET/PUT /plan/income` through `PreferencesStore` (`income.expected_monthly_cents`)

## 5. Backend tests

- [ ] 5.1 Schedules: CRUD, the validation matrix per pattern, and occurrences (some months, every N, finite monthly, once, no date)
- [ ] 5.2 Amounts: colegio fixture (normal 582,92 €, catch-up 721,40 €), caught up falls back to normal, one-off 333,34 €, rounding up to the cent
- [ ] 5.3 Drafting: a scheduled category drafts its suggested amount (also in the first month), unscheduled ones copy, edits win
- [ ] 5.4 Overview: mid-month paid/pending split, covered and short amounts, estimated bill matching, past and future months, and the identity property (`accounts = covered + left + saved + TBA − overspent`) over generated data
- [ ] 5.5 Projection: payments at risk flagged, structural gap shows as unfunded set-asides, pro-rata within a level, the unknown-income path; a port of the prototype run on its fixture dataset (October flexible funded 554,78 € of 1.280 €)
- [ ] 5.6 Summary and income: window totals and gap (−4.578,07 € / −381,51 € fixture), PUT/GET round trip into preferences

## 6. BFF and API client

- [ ] 6.1 Route handlers for schedules, overview, plan upcoming, summary and income
- [ ] 6.2 `lib/api.ts`: types and client functions; `kind`, `normal_cents` and `catch_up_cents` on budget and category types

## 7. Webapp

- [ ] 7.1 Schedule editor dialog: kind selector, payment list with sentence descriptions, sentence-style form per pattern (month chips, day, estimated), live normal and catch-up cards, 12-month balance chart (shortfall in `--warning`); opened from the budget row ("Set up payments") and Settings → categories
- [ ] 7.2 Budget row: "Suggested from your payments" label for computed drafts; normal and catch-up hint in the expanded row
- [ ] 7.3 Dashboard: "Este mes" primary panel (already paid, still to pay with covered/short chips, left to spend), side column (saved grouped chips, unassigned, accounts check line, next 3 months), recent transactions below; skeletons without layout shift
- [ ] 7.4 "Upcoming payments" route + sidebar entry: summary cards, expandable month rows with the day-to-day and set-aside funding bars, inline "Add your monthly income" when unknown
- [ ] 7.5 Query invalidation: transaction writes, moves, assignment edits and schedule edits refresh overview, upcoming, summary and budget
- [ ] 7.6 Income breakdown sheet from the to-be-assigned hero: the month's incomes one by one (from `GET /api/transactions?month=`, uncategorized inflows only), expected versus received from `/api/plan/income`, carried in, deducted, assigned, and the total

## 8. Verification

- [ ] 8.1 `uv run pytest` green; `volta run npx tsc --noEmit` + `volta run npm run lint` green (build only without a dev server running)
- [ ] 8.2 Manual:
  - set up the user's real payments (colegio, rent, car insurance, water, Manameli, subscriptions) through the editor;
  - the dashboard matches the prototype's October split and the accounts check holds;
  - Upcoming payments shows the year's gap;
  - a new month drafts the computed amounts.
