## ADDED Requirements

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
