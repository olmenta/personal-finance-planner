## ADDED Requirements

### Requirement: Card plan schedule on a payment category

A credit account's payment category SHALL accept at most one `monthly` payment schedule, its card plan, created and edited through the debts API. A second schedule on a payment category SHALL return 409 `card_plan_exists`. While the plan exists, the payment category's assignment SHALL be computed from the plan like any category with payments (`PUT` assignments returns 409 `assignment_from_payments`). Funded card moves SHALL keep flowing in on top of it. The plan SHALL count in the projection and the annual plan as a dated payment.

#### Scenario: Plan sets the card's assignment

- **WHEN** "Pago Sabadell - Visa" gets a 200,00 € monthly plan in an open month
- **THEN** its assignment becomes 200,00 €, and a 50,00 € budgeted card purchase still moves 50,00 € into it on top

#### Scenario: Plan counts in the annual plan

- **WHEN** a 200,00 € monthly card plan exists
- **THEN** `GET /plan/summary` includes 2.400,00 € of it in `scheduled_cents` for the 12-month window

### Requirement: Debt schedules are managed from debts

Schedules created by the debts API (card plans, loan installments, dated personal debts) SHALL be written only through it. `PATCH` and `DELETE /schedules/{id}` on them SHALL return 409 `managed_by_debt`. `GET` SHALL mark them with `debt_id`, so the payment editor shows them read-only with a link to "What you owe".

#### Scenario: Installment edited from the wrong place

- **WHEN** a client patches the schedule of a loan debt through `/schedules/{id}`
- **THEN** the API returns 409 `managed_by_debt` and the schedule is unchanged
