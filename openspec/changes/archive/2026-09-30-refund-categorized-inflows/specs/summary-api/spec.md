# summary-api Delta Specification

## MODIFIED Requirements

### Requirement: Month summary view

The API SHALL expose `GET /summary/{month}` returning, in integer cents: `balance_cents` (all-time sum of confirmed transaction amounts across the user's accounts), `income_cents` (sum of positive confirmed transactions **without a category** in the month — categorized inflows are refunds, not income), `expense_cents` (absolute net of categorized confirmed activity in the month: expenses minus categorized inflows), and `weeks` — one bucket per calendar week overlapping the month, each with `start` (ISO date of the bucket's first day, clamped to the month), `spent_cents`, and `income_cents` following the same categorization rule. Income SHALL be derived from the same shared aggregation the budget view uses, so the dashboard and the budget can never disagree. Staged transactions SHALL be excluded everywhere. Aggregation SHALL happen in the database, not by shipping the transaction list.

#### Scenario: Month totals

- **WHEN** June has confirmed income of 2.350,00 € and confirmed expenses totaling 1.938,00 €, plus a staged expense of 50,00 €
- **THEN** `GET /summary/2026-06` reports `income_cents = 235000` and `expense_cents = 193800`

#### Scenario: Refund nets expenses, not income

- **WHEN** June additionally has a confirmed +12,50 € inflow categorized to Supermercado
- **THEN** the summary reports `expense_cents = 192550` and `income_cents` unchanged at `235000`

#### Scenario: All-time balance

- **WHEN** the user's confirmed transactions across all months sum to +874,57 €
- **THEN** the summary reports `balance_cents = 87457` regardless of the month requested

#### Scenario: Weekly buckets cover the month

- **WHEN** a client requests `GET /summary/2026-06`
- **THEN** every June transaction date falls in exactly one returned week bucket, and bucket totals sum to the month's totals

#### Scenario: Empty month

- **WHEN** a month has no transactions
- **THEN** the summary returns zero totals and week buckets with zero amounts (not an error)
