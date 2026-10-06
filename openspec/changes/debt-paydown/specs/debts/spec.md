## ADDED Requirements

### Requirement: Debt kinds and what is owed

A debt SHALL be a record linked one-to-one to a category, with a `kind`.

| kind | linked category | required payment | what is owed (`owed_cents`) |
|---|---|---|---|
| `card` | the credit account's payment category | its card plan (a monthly schedule) | the card's debt (−balance) minus the money set aside for new spending: the payment category's available beyond this month's unpaid plan |
| `loan` | a category with one finite `monthly` schedule (installment, `count`, `start_month`, day) | the installment | the installment × the installments not yet paid, counting from the current month |
| `personal` | a category with `owed_cents` entered by the user, optionally a `due_month` | when it has a due month: a `once` schedule of the amount owed in that month | `owed_cents` − the category's confirmed spending since the debt was created |

Every debt SHALL carry an optional interest rate (`rate_bp` in basis points with `rate_period` `month` or `year`, or none when unknown). A `card` debt SHALL also carry an optional `minimum_cents`. A debt whose `owed_cents` reaches zero SHALL report `paid_off = true`. Debts SHALL NOT create transactions or change To Be Assigned: their required payments flow through the existing payment schedules and budget.

#### Scenario: Loan balance from installments

- **WHEN** a loan debt has a 290,17 € monthly schedule with `count = 34` starting October 2026, and today is 14 October with October's installment unpaid
- **THEN** it reports `owed_cents = 986578` and ends in July 2029

#### Scenario: Card debt is what's not set aside

- **WHEN** "Sabadell - Visa" has a balance of −634,62 € and its payment category holds 0
- **THEN** the card debt reports `owed_cents = 63462`

#### Scenario: Setting the plan aside doesn't pay the debt

- **WHEN** the card owes 634,62 €, its 200,00 € plan is assigned this month and no transfer has been made yet
- **THEN** the card debt still reports `owed_cents = 63462`, and after a 200,00 € transfer into the card it reports 43462

#### Scenario: Personal debt goes down as it's paid

- **WHEN** a personal debt of 2.900,00 € to "Jose y Ruby" gets a 400,00 € payment categorized to it
- **THEN** it reports `owed_cents = 250000`

#### Scenario: Personal debt with a due month is required

- **WHEN** the user records 2.900,00 € owed with `due_month = 2027-03`
- **THEN** the category holds a `once` schedule of 2.900,00 € in March 2027, so the budget sets aside the catch-up amount each month until then

### Requirement: Debts API

The API SHALL expose:

- `GET /debts`: the debts in paydown order, each with `id`, `kind`, `category_id`, `name`, `owed_cents`, `rate_bp`, `rate_period`, `monthly_rate_bp` (normalized), `minimum_cents`, `required_monthly_cents`, `end_month`, `paid_off`, `position`, and `monthly_interest_cents` (only when a rate is known); plus `total_owed_cents`, `extra_monthly_cents`, `debt_free_month`, and `cushion` (`suggested_cents`, `saved_cents`).
- `POST /debts`, with these kinds:
  - `card`: `account_id`, a plan as `plan_monthly_cents` or `target_month`, optional `minimum_cents`, rate. From a `target_month`, the plan is the smallest monthly amount, rounded up to the cent, that pays the owed amount off by that month, with interest included when a rate is known.
  - `loan`: `name`, `installment_cents`, `installments_left`, `next_month`, optional `day`, rate. It creates the category in a "Deudas" group, reusing a case-insensitive match.
  - `personal`: `name`, `owed_cents`, optional `due_month`, optional `lender` resolved to a payee, rate.
- `PATCH /debts/{id}` and `DELETE /debts/{id}`. Delete removes the debt and its plan schedule but keeps the category and its history.
- `PUT /debts/extra {extra_monthly_cents ≥ 0}`.

Invalid input SHALL return 422 `invalid_debt`. A category or account already linked to a debt SHALL return 409 `debt_exists`. Unknown or foreign ids SHALL return 404.

#### Scenario: Card plan from a target month

- **WHEN** in October the user creates a card debt for a −634,62 € card with `target_month = January` and no rate
- **THEN** the plan schedule is 158,66 € per month (the owed amount over October–January, 4 payments, rounded up) and `end_month` is January

#### Scenario: Card plan below the minimum is flagged

- **WHEN** the card plan is 50,00 € and `minimum_cents` is 60,00 €
- **THEN** the debt reports `below_minimum = true` and the plan is saved anyway

#### Scenario: Minimum skipped

- **WHEN** the user creates a card debt without `minimum_cents`
- **THEN** the debt is created and `below_minimum` is null

### Requirement: Paydown order, extra and rollover

Debts SHALL be ordered by:

1. known rate, highest monthly-normalized rate first;
2. unknown rate;
3. personal debts without a rate, last (treated as interest-free).

Ties SHALL go to the smallest `owed_cents`. Paid-off debts leave the order.

The `extra_monthly_cents` (optional, default 0) SHALL be directed to the first debt in the order. When that debt is paid off, its required payment and the extra SHALL roll to the next debt. `GET /debts` SHALL report, for the current month, `extra_target_debt_id` and the amount to put there. Assigning it remains an explicit budget action.

#### Scenario: Highest rate first

- **WHEN** the user has a card at 1,5 % per month, a loan at 7 % per year and a personal debt with no rate
- **THEN** the order is card, loan, personal

#### Scenario: Unknown rate after known rates

- **WHEN** one loan has no rate and another has 9 % per year
- **THEN** the loan at 9 % comes first

#### Scenario: Paid-off debt rolls its money forward

- **WHEN** the card paid 200,00 € a month plus 100,00 € extra and is paid off in January
- **THEN** from February the simulation puts 300,00 € a month into the next debt in the order

### Requirement: Debt-free simulation

The backend SHALL simulate month by month from the current month, for at most 120 months:

- each debt receives its required payment;
- the first debt in the order also receives the extra plus everything rolled from paid-off debts;
- a debt with a known rate accrues `owed × monthly rate` before its payment;
- loans end at their last installment;
- personal debts with a due month are due that month;
- personal debts without a date only shrink through extra or rolled money.

Each debt SHALL report `end_month`, null when it doesn't end within the horizon. The response SHALL report `debt_free_month`, null when any debt doesn't end. Interest SHALL be computed only for debts with a known rate. `monthly_interest_cents` SHALL be `round(owed × monthly rate)`.

#### Scenario: Card with interest

- **WHEN** a card owes 634,62 € at 1,5 % per month with a 200,00 € plan and no extra
- **THEN** starting in October its `end_month` is January (4 payments, the last one smaller) and `monthly_interest_cents = 952`

#### Scenario: Personal debt without a date never ends without extra

- **WHEN** the only debt is a personal debt with no date and the extra is 0
- **THEN** its `end_month` and the `debt_free_month` are null

### Requirement: Emergency cushion suggestion

`GET /debts` SHALL report a `cushion`:

- `suggested_cents` is the larger of 300,00 € and one month of required debt payments, capped at 1.000,00 €;
- `saved_cents` is the available of the user's savings categories.

When `saved_cents < suggested_cents` and the extra is above 0, the screen SHALL show a coach note suggesting the cushion first, always with the reason ("so the next surprise doesn't end up on the card"). It SHALL never block setting the extra.

#### Scenario: No cushion yet

- **WHEN** the user has no savings categories with money and sets 100,00 € extra
- **THEN** the debts screen shows the cushion note with its reason and the extra is still saved

### Requirement: Converting a loan set up as a card

Converting a credit account into a loan (see accounts-api) SHALL create a `loan` debt from the installment, installments left, next month and day, in a category in the "Deudas" group named after the account. It SHALL move the old payment category's positive available into the new category as a budget move in the current month, and archive the account and its payment category. The account's transactions SHALL keep counting, as archiving already guarantees.

#### Scenario: Sabadell loan converted

- **WHEN** "Sabadell - Prestamo" (credit, −9.709,83 €) is converted with installment 290,17 €, 34 installments left from November and day 2
- **THEN** a loan debt "Sabadell - Prestamo" exists with that schedule, the account is archived, and it no longer reports uncovered card debt

### Requirement: What you owe screen

The webapp SHALL provide a "What you owe" screen at `/debts` (sidebar entry; reachable from the dashboard on mobile). It SHALL show:

- the total owed, and the debt-free month ("Debt-free in June 2028 if you keep this plan") or a plain explanation when there is none;
- the debts in order, each with its name, amount owed, its required payment and end, and its rate in plain words ("1,5 % a month", "no interest", "rate unknown");
- for the first debt, one sentence explaining why it goes first and, when a rate is known, "~X €/month just for owing it";
- the monthly extra with an edit control, and the cushion note when it applies;
- an always-visible "Work on my debts" button in the header and on every debt row, opening the plan editor;
- an empty state that invites adding a first debt, never apologizing.

The copy SHALL avoid finance jargon: no TAE, APR, amortization, snowball or avalanche.

#### Scenario: Reading the plan

- **WHEN** the user has a card, a loan and a personal debt
- **THEN** the screen shows the total, the debt-free month, the card first with its reason and interest sentence, and a "Work on my debts" button

#### Scenario: Paid off

- **WHEN** a debt's `owed_cents` reaches zero
- **THEN** it shows as paid off with a short celebration line and offers to remove its plan

### Requirement: Debt plan editor

The plan editor SHALL let the user add or edit a debt in a few steps:

1. pick the kind: "A card", "A loan with installments", "Money I owe someone";
2. enter the kind's fields in plain words:
   - card: pick the card, then "How much can you pay a month?" or "When do you want to be done?" with the other computed live, and "What's the least the bank lets you pay?" (skippable);
   - loan: installment, installments left, next one, day;
   - personal: who, how much, "Do they need it back by a date?";
3. answer "How much does it charge you?" with "x % a month", "x % a year" or "I don't know".

A plan below the minimum SHALL show why it matters before saving.

#### Scenario: Card plan both ways

- **WHEN** the user types 200 € a month for a 634,62 € card at 1,5 % per month
- **THEN** in October the editor shows "done in January", and choosing January instead shows 164,65 € a month (the least that finishes by then, interest included)

#### Scenario: Skipping the minimum

- **WHEN** the user skips the minimum question
- **THEN** the debt saves without it

### Requirement: Late debt payment nudge

While a required debt payment of the current month is `late` in the month overview, the dashboard SHALL show one coach capsule naming it ("Your Ikea installment was due on the 5th and hasn't gone out yet"), or the count and total when several are late. It SHALL link to "What you owe", with a dismiss control kept per browser for those payments in that month.

#### Scenario: Installment late

- **WHEN** on 14 October a loan installment due on day 5 is unpaid
- **THEN** the dashboard shows the nudge naming it

#### Scenario: Paid installment clears the nudge

- **WHEN** the installment's expense is recorded
- **THEN** the nudge disappears
