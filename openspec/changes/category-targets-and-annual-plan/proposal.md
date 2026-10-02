## Why

Olmenta budgets every expense monthly, but real life isn't monthly. School fees are paid September–June, car insurance once a year, water every quarter. Today the user has to do the math (annual cost ÷ 12) and has no way to know whether a payment months away will be covered. Reviewing the user's real budget showed exactly this failure: a spreadsheet that looked +739 €/month healthy hid a −4.578 €/year gap, because non-monthly costs never appeared in the monthly view.

The product decisions (2026-09-30/10-01) and the approved prototype (`ui-experiments/este-mes-y-pagos.local.html`) define the answer:
- The budget is always annual cost ÷ 12, computed by the app.
- Payments follow their own schedule.
- The app shows what to solve now and whether every future payment will be met.

## What Changes

- **Category kinds**: `flexible` (day-to-day), `scheduled` (payments with a calendar) and `savings` (filled when there's money left). The kind is set in category management and drives where money appears on the home screen.
- **Payment schedules per category**: one or more payments, each with a pattern:
  - monthly (optionally a finite number of payments);
  - some months (e.g. Sep–Jun);
  - once a year;
  - every N months from a start month;
  - once on a date;
  - no date (an annual goal).

  Each payment has an amount, an optional day, and an "estimated" flag for variable bills.
- **Monthly amounts computed by the app**:
  - the **normal amount** (annual cost ÷ 12, or the remaining amount ÷ months left for one-offs);
  - the **catch-up amount** (the minimum to set aside per month, given what's already saved, so no payment in the next 12 months goes uncovered).

  The month's draft assignment for a scheduled category becomes the larger of the two, instead of copying last month.
- **Month overview API + home card "Este mes"**, as in the prototype:
  - already paid this month;
  - still to pay (scheduled payments due later this month, each covered or short);
  - left to spend (flexible categories);
  - saved for the future;
  - unassigned;
  - a line proving the split adds up to the money in the accounts.

  Scheduled payments are matched to real transactions by category and month.
- **Upcoming payments API + "Próximos pagos" screen**:
  - a 12-month timeline of scheduled payments with coverage status;
  - how much of the day-to-day budget is funded;
  - how much of what should be set aside can actually be set aside.

  It uses a projection that allocates the **expected fixed income** in the prototype's priority order: payments due that month, then day-to-day, then setting aside for later payments, then undated goals.
- **Annual plan summary**: expected fixed income for 12 months versus planned costs (scheduled payments + day-to-day + goals), with the yearly and monthly gap. Probable money (bonuses) is never part of it. Expected fixed income comes from the preferences document (`income.expected_monthly_cents`, set by onboarding) and becomes editable.
- **Schedule editor**, following the prototype's "Configurar pagos":
  - a category's payment list;
  - a sentence-style form per payment with a pattern picker and month chips;
  - live normal and catch-up amounts;
  - a 12-month balance chart for the category.
- **Income breakdown**: tapping the budget's to-be-assigned figure lists the month's incomes one by one, expected versus received, plus the carry-in and deductions that make up the number.
- **Dashboard**: the "Este mes" card becomes the home screen's primary panel, replacing the balance-card-first layout. Recent transactions stay below it.

## Capabilities

### New Capabilities

- `payment-schedules`: category kinds, schedule patterns and their CRUD, the normal and catch-up monthly amounts, and the schedule editor UI.
- `month-overview`: the "Este mes" contract (paid, to pay with coverage, left to spend, saved, unassigned, identity check), matching payments to transactions, and the home card.
- `payment-projection`: the 12-month upcoming-payments timeline and priority-allocation coverage, the annual plan summary and editable expected fixed income, and the "Próximos pagos" screen.

### Modified Capabilities

- `data-model`: `Category.kind`; new `PaymentSchedule` entity.
- `categories-api`: `PATCH /categories/{id}` accepts `kind`; the tree exposes it.
- `budget-api`: drafts for scheduled categories use the computed monthly amount. The view exposes `kind`, `normal_cents` and `catch_up_cents` per category.
- `budget-suggestions`: drafted amounts come from schedules for scheduled categories, and from the previous month for the rest.
- `webapp-server-state`: the dashboard is served by the month overview.
- `budget-assignment`: tapping the to-be-assigned figure opens an income breakdown (each income of the month, expected versus received, carried in, deducted, assigned).
- `bff-proxy`: new routes for schedules, overview, upcoming payments and expected income.

## Impact

- **Backend**:
  - model: a `PaymentSchedule` model and one Alembic migration (`categories.kind`, `payment_schedules`);
  - new services: `services/schedules.py` (occurrences, amounts), `services/projection.py` (the allocation engine, ported from the prototype), `services/overview.py`;
  - routers: new schedules, overview and plan routers; `categories` accepts `kind`; `budget_view` uses the computed amounts when drafting.
- **Webapp**: the dashboard home card, the "Próximos pagos" route, the schedule editor (reached from the budget row and from Settings → categories), BFF routes, and `lib/api.ts`.
- **Depends on** `budget-rules`: carry-over To Be Assigned and the overspending reset feed the overview's identity and the projection's starting point. It must be implemented first; it's implemented and awaiting its manual check.
- **Other changes**:
  - `accounts-and-transfers` later adds card charges as scheduled payments and per-account balances to the overview; this change is written so those slot in.
  - Onboarding extraction of schedules ("632 al mes de septiembre a junio") and coach proposals (repeated overspending, monthly plan adjustments) are follow-up changes.
- **Out of scope**: multiple budgets per user, multi-currency, debt payoff plans.
