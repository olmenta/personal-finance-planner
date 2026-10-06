## MODIFIED Requirements

### Requirement: Income breakdown from the to-be-assigned hero

Tapping the to-be-assigned amount (or its income line) on the budget screen SHALL open a breakdown of where the month's money to assign comes from, read from `GET /api/income/{month}` and the budget view. It SHALL show, in order:

1. the month's expected income occurrences one by one: name, day and expected amount, with a status chip:
   - "received" in the income color, with "X € less" or "X € more" when the difference isn't zero;
   - "expected day N" when pending;
   - "not arrived yet" in the warning color when late;
   - "didn't arrive" when missed;
2. the unplanned income (unmatched inflows: payer or description, day, amount in the income color), each with a "This is…" action that links it to an expected occurrence (see income-schedules);
3. the line "expected X · received Y";
4. the amount carried in from the previous month;
5. the previous month's uncovered overspending deducted;
6. the month's total assignments;
7. the to-be-assigned figure.

Received income SHALL come from the month's confirmed uncategorized inflows (the same rule as `income_cents`), so only real money adds up to the hero. Expected occurrences SHALL never add to it. Refunds (categorized inflows) SHALL NOT appear as income.

#### Scenario: Salary listed with expected versus received

- **WHEN** October expects "Nómina" 2.800,00 € on day 27 and "Pensión" 900,00 € on day 1, and only the 900,00 € pension has arrived
- **THEN** the breakdown lists "Pensión · day 1 · received", "Nómina · day 27 · expected day 27", and the line "expected 3.700,00 € · received 900,00 €"

#### Scenario: Lower salary shows the difference

- **WHEN** "Nómina" expected 2.800,00 € and 2.750,00 € arrived
- **THEN** its row reads "received · 50,00 € less"

#### Scenario: Linking unplanned income

- **WHEN** an unplanned 1.180,00 € inflow is linked through "This is…" to "Alquiler piso"
- **THEN** it leaves the unplanned list and "Alquiler piso" shows as received

#### Scenario: Breakdown adds up to the hero

- **WHEN** the breakdown shows carried in 2.000,00 €, income 0, deducted 0 and assigned 1.909,20 €
- **THEN** its final line equals the hero's 90,80 € to assign

#### Scenario: No income yet this month

- **WHEN** the month has no confirmed uncategorized inflows
- **THEN** the breakdown says no income has arrived yet this month and lists the expected occurrences as still to come, or invites adding income when there are no income schedules
