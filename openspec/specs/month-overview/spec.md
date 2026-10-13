# month-overview Specification

## Purpose

The "Este mes" month overview contract (paid, to pay with coverage, left to spend, saved, unassigned, identity check), matching scheduled payments to transactions, and the home screen card.

## Requirements

### Requirement: Month overview contract

The API SHALL expose `GET /overview/{month}` returning, in integer cents: `paid` (the month's confirmed spending: paid scheduled occurrences listed individually with name, day and amount, flexible categories as spent totals), `to_pay` (scheduled occurrences still pending this month, each with `category_id`, `name`, `day`, `amount_cents`, `covered_cents`, `short_cents`), `left_to_spend` (Σ non-negative available of flexible categories, with the per-category list), `saved` (Σ of scheduled categories' available beyond this month's pending payments plus savings categories' available, per category), `overspent_cents` (Σ of negative availables), `to_be_assigned_cents`, and `accounts_cents` (the signed sum of confirmed transactions up to the month's end). The response SHALL satisfy `accounts_cents = Σ covered + left_to_spend + saved + to_be_assigned_cents − overspent_cents` exactly. "Today" SHALL be computed in Europe/Madrid; for past months every occurrence is due, for future months none is paid.

#### Scenario: Mid-month split

- **WHEN** on 14 October the rent (day 1) and the school fee (day 5) were paid and Manameli's 1.000,00 € (day 15) is pending with 1.000,00 € available in its category
- **THEN** `paid` lists the rent and the school fee, and `to_pay` lists Manameli with `covered_cents = 100000` and `short_cents = 0`

#### Scenario: Pending payment not fully covered

- **WHEN** a pending 1.000,00 € payment's category has only 498,00 € available
- **THEN** its `to_pay` entry reports `covered_cents = 49800` and `short_cents = 50200`

#### Scenario: The split adds up

- **WHEN** any month is requested
- **THEN** `accounts_cents` equals the sum of covered payments, left to spend, saved and To Be Assigned, minus overspent

### Requirement: Matching scheduled payments to transactions

A scheduled category's confirmed spending in the month SHALL be allocated to its occurrences in day order (a missing day counts as day 1). An occurrence SHALL count as paid when the allocation covers its amount, or, when it is `estimated`, as soon as any spending is allocated to it; the remainder of an occurrence not yet paid SHALL be pending.

#### Scenario: Exact bill marks the payment paid

- **WHEN** "Alquiler" has a 952,00 € monthly schedule on day 1 and a 952,00 € expense on 1 October
- **THEN** the October overview lists the rent under `paid` and not under `to_pay`

#### Scenario: Estimated bill with a different amount

- **WHEN** the estimated 100,00 € electricity schedule receives a 94,30 € bill
- **THEN** the occurrence counts as paid and the category shows 5,70 € left over

### Requirement: Home screen "Este mes" card

The dashboard SHALL render the overview as its primary panel: "Already paid this month" (total, expandable list), "Still to pay this month" (each pending payment with day, name, amount and a covered or "short X €" chip), and "Left to spend" (total and per-category remaining, overspent categories flagged), plus a side column with "Saved for the future" (grouped chips), "Unassigned", the accounts check line ("In your accounts: X = to pay + to spend + saved + unassigned"), and the next three months from the projection with a link to "Upcoming payments". Recent transactions SHALL remain below. Loading SHALL use skeletons without layout shift.

#### Scenario: Short payment is visible without digging

- **WHEN** a pending payment this month is short by 502,00 €
- **THEN** the card shows it under "Still to pay this month" with a warning chip "short 502,00 €"

#### Scenario: Quiet month

- **WHEN** the month has no schedules and no transactions
- **THEN** the card shows zero totals and invites setting up payments, with no error

### Requirement: Card plan occurrences paid by transfers

A card's payment category MAY hold a monthly plan schedule (see payment-schedules). Its occurrences SHALL appear in `to_pay` like any scheduled payment while unpaid. They SHALL count as paid when the month's transfers into the card reach the plan amount, instead of from category spending. Coverage SHALL use the payment category's available.

#### Scenario: Card plan paid by the monthly transfer

- **WHEN** "Pago Sabadell - Visa" has a 200,00 € plan on day 30 and a 450,00 € transfer into the card lands on 30 October
- **THEN** the October overview lists the card plan under `paid` and not under `to_pay`

#### Scenario: Card plan still pending

- **WHEN** no transfer into the card has landed by 14 October
- **THEN** `to_pay` lists the card plan with its covered and short amounts

### Requirement: Late required debt payments

A pending `to_pay` occurrence that belongs to a debt's required payment SHALL report `late = true` when the month is the current month and today (Europe/Madrid) is more than 3 days past its day. A missing day SHALL count as the last day of the month. Other pending occurrences SHALL report `late = false`.

#### Scenario: Installment three days late is not yet late

- **WHEN** a loan installment is due on day 5, unpaid, and today is 8 October
- **THEN** its `to_pay` entry reports `late = false`, and on 9 October `late = true`
