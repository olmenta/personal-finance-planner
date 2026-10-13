## 1. Data model

- [x] 1.1 Add `Debt` (`user_id`, `category_id` unique, `kind`, `rate_bp`, `rate_period`, `minimum_cents`, `owed_cents`, `due_month`, `created_at`) and `DebtSettings` (`user_id` pk, `extra_monthly_cents`) to `models.py`.
- [x] 1.2 Write the Alembic revision creating `debts` and `debt_settings` (no data step), after `c5d2e8f1a9b4`.

## 2. Debt engine (pure)

- [x] 2.1 Add `services/debts.py`:
  - `monthly_rate()` normalization (year ÷ 12);
  - the order key (group, −rate, owed);
  - `plan_for_target(owed, rate, months)`, using the annuity formula or `ceil(P / n)`;
  - the month-by-month simulation (required payments, extra and rolled pool to the first debt, interest when the rate is known, 120-month cap) returning each debt's `end_month` and the `debt_free_month`.
- [x] 2.2 Owed per kind:
  - card from `uncovered_debt_cents`;
  - loan from the remaining schedule occurrences, minus this month's when paid;
  - personal from `owed_cents` minus confirmed category spending since creation.
- [x] 2.3 Unit tests for the scenarios:
  - loan 290,17 € × 34 → 9.865,78 €, ends July 2029;
  - card 634,62 € at 1,5 % with 200 € → January, 9,52 € interest;
  - target January → 164,65 € with the rate and 158,66 € without;
  - order: highest rate first, unknown after known, personal last, tie by smallest;
  - rollover after a payoff;
  - a personal debt with no date and no extra never ends.

## 3. Debts API

- [x] 3.1 Add `routers/debts.py`:
  - `GET /debts` (ordered debts, totals, debt-free month, extra target, cushion);
  - `POST /debts` per kind (card → plan schedule on its payment category; loan → "Deudas" category plus its `monthly`/`count` schedule; personal → category, plus a `once` schedule when it has a due month, and an optional lender resolved as a payee);
  - `PATCH` and `DELETE /debts/{id}` (rewriting or removing the managed schedule, keeping the category);
  - `PUT /debts/extra`.

  Errors: 422 `invalid_debt`, 409 `debt_exists`, 404. Register it in `main.py`.
- [x] 3.2 Card plan: at most one schedule on a payment category (409 `card_plan_exists` from the schedules API). Make the debts API the only writer of debt schedules; the schedules API returns 409 `managed_by_debt` on them.
- [x] 3.3 `budget_view`: a payment category with a plan gets the plan's computed assignment (PUT returns 409 `assignment_from_payments`), with funded moves unchanged.
- [x] 3.4 Cushion: `suggested_cents = clamp(max(30000, required monthly), ≤ 100000)`, and `saved_cents` from the savings categories' available.
- [x] 3.5 Add API tests for every debts scenario: plan from a target, below minimum flagged, minimum skipped, `debt_exists`, delete keeps the category, personal debt paid down, due month creates a `once` schedule.

## 4. Month overview and conversion

- [x] 4.1 `services/overview.py`: card plan occurrences on payment categories are paid when the month's transfers into the card reach the plan amount, and payment categories with a plan appear in `to_pay`. Add `OverviewPending.late` for debt schedules in the current month that are more than 3 days past their day (a missing day counts as month end).
- [x] 4.2 Add `POST /accounts/{id}/convert-to-loan`: in one transaction, ensure "Deudas", create the category, the loan debt and its schedule, move the payment category's positive available into it, then archive the account and its payment category. Return 409 `not_convertible` for non-credit or archived accounts.
- [x] 4.3 Tests:
  - card plan paid by a transfer, and still pending without one;
  - `late` on day 9 but not day 8 for a day-5 installment;
  - the plan in `/plan/summary` `scheduled_cents`;
  - conversion moves the available, archives, and stops the uncovered card debt;
  - a bank account conversion returns 409.

## 5. Webapp

- [x] 5.1 BFF routes `api/debts`, `api/debts/[id]`, `api/debts/extra`, `api/accounts/[id]/convert-to-loan`. In `lib/api.ts`, add the debt types and functions, and `late` on `OverviewPending`.
- [x] 5.2 Add `lib/debts.ts`, a TS mirror of the D5 functions for the editor's live preview.
- [x] 5.3 Add the `/debts` page "What you owe":
  - the total and the debt-free month (or a plain explanation);
  - rows in order with owed, the required payment, the end, and the rate in plain words;
  - the first row's reason and interest sentence;
  - the extra with an edit control, and the cushion note with its reason;
  - paid-off rows with a celebration line and "remove the plan";
  - an empty state inviting a first debt;
  - the "Work on my debts" button in the header and on every row.

  Add it to the sidebar and to mobile navigation from the dashboard.
- [x] 5.4 `DebtEditor` sheet:
  - kind picker ("A card", "A loan with installments", "Money I owe someone");
  - card: pick the card, the plan "How much a month?" ↔ "When do you want to be done?" computed live, and "What's the least the bank lets you pay?" (skippable), with a "why it matters" note when below it;
  - loan: installment, installments left, next one, day;
  - personal: who, how much, "Do they need it back by a date?";
  - the rate: "x % a month", "x % a year" or "I don't know".
- [x] 5.5 Payment editor: debt-managed schedules show read-only "Managed from What you owe" with a link.
- [x] 5.6 Accounts screen: "This is a loan, not a card" on credit accounts, with a short form (installment, installments left, next one, day) that calls the conversion.
- [x] 5.7 Add `LateDebtNudge` on the dashboard, next to `LateIncomeNudge`: one capsule naming the late debt payment (or the count and total), a link to `/debts`, and per-browser dismissal keyed by month and the late schedule ids.

## 6. Docs

- [x] 6.1 Update `project-definition.md`:
  - §3: a debt principle (required versus optional, order by rate, plain language);
  - §4.2: replace "Paying down pre-existing debt" with "Chat about debts (coach interview from the Work on my debts button)";
  - §6.4: `Debt`, `DebtSettings`;
  - §10: a resolved entry.
- [x] 6.2 Check that the deltas match the implementation: `debts` added; `month-overview`, `payment-schedules`, `accounts-api` and `bff-proxy` modified.

## 7. Verification

- [x] 7.1 `uv run pytest` green in `backend/`.
- [x] 7.2 Type check, lint and build green in `webapp/` (build with `NEXT_DIST_DIR=.next-verify`).
- [x] 7.3 e2e `e2e/debts.spec.ts`, then `volta run npm run e2e` green. The spec covers:
  - add a card debt with a plan from a target month and see the order and debt-free month;
  - add a loan and a personal debt with a date;
  - convert a credit account into a loan;
  - see the late-installment nudge with the clock past day + 3;
  - "Work on my debts" opens the editor from the header and a row.
