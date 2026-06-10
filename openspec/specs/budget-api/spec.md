# budget-api Specification

## Purpose

HTTP API surface for the zero-based budget: the per-month budget view contract the webapp renders, category assignment upserts, draft suggestions seeded from the previous month, and rollover of unspent balances.

## Requirements

### Requirement: Budget month view

The API SHALL expose `GET /budget/{month}` returning the `BudgetMonthView` contract the webapp renders: `month`, `income_cents`, `to_be_assigned_cents` (derived), and groups → categories with `assigned_cents`, `spent_cents`, `rollover_cents`, `available_cents` (derived), `suggestion_cents` and `suggestion_state`, plus quick-fill history fields `last_month_assigned_cents`, `avg_3m_cents` (mean of up to the three previous months' confirmed spending, rounded to whole euros in cents), and `last_month_spent_cents` — each `null` when the relevant history does not exist. Requesting a month with no record SHALL create it lazily with draft suggestions.

#### Scenario: View matches webapp contract

- **WHEN** a client requests `GET /budget/2026-06`
- **THEN** the response contains income, derived to-be-assigned, and per-category assigned/spent/rollover/available in integer cents

#### Scenario: Spent aggregates confirmed transactions only

- **WHEN** a category has confirmed transactions totaling 138,00 € and a staged transaction of 50,00 € in the month
- **THEN** the view reports `spent_cents = 13800` for that category

#### Scenario: Quick-fill fields from history

- **WHEN** a category was assigned 120,00 € in May with 119,00 € spent, and June is requested
- **THEN** June's view reports `last_month_assigned_cents = 12000` and `last_month_spent_cents = 11900` for that category

#### Scenario: First month has no quick-fill

- **WHEN** the first-ever month is requested
- **THEN** every category's `last_month_assigned_cents`, `avg_3m_cents`, and `last_month_spent_cents` are `null`

### Requirement: Assign to a category

The API SHALL expose `PUT /budget/{month}/assignments/{category_id}` accepting `amount_cents ≥ 0`, upserting the assignment and setting its suggestion state to `edited`. The response SHALL include the recalculated `to_be_assigned_cents`.

#### Scenario: Assignment updates to-be-assigned

- **WHEN** income is 2.350,00 €, total assigned is 1.938,00 €, and a client raises one category by 412,00 €
- **THEN** the response reports `to_be_assigned_cents = 0`

### Requirement: Draft suggestions from the previous month

When a budget month is created, each category's assignment SHALL be drafted from the previous month's assignment (state `draft`); if no previous month exists, assignments SHALL start at zero with no draft. `POST /budget/{month}/confirm-suggestions` SHALL mark the given categories' drafts as `confirmed` without changing amounts, and SHALL NOT overwrite `edited` assignments.

#### Scenario: New month pre-fills from history

- **WHEN** June is first requested and May has assignments
- **THEN** June's assignments equal May's with `suggestion_state = "draft"`

#### Scenario: First month starts empty

- **WHEN** the first-ever month is requested
- **THEN** all assignments are zero and no category is in `draft` state

#### Scenario: Confirm preserves edits

- **WHEN** a client confirms suggestions after editing one category manually
- **THEN** drafted categories become `confirmed` and the edited category keeps its amount and `edited` state

### Requirement: Rollover carries unspent balances forward

A category's `rollover_cents` for month M SHALL equal its available balance at the end of month M−1 (`assigned + rollover − spent`, floored at the chain's actual value, including negative carryover), and zero when no previous month exists.

#### Scenario: Positive carryover

- **WHEN** a category ends May with 32,00 € available
- **THEN** June's view reports `rollover_cents = 3200` for that category
