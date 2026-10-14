## MODIFIED Requirements

### Requirement: Derived budget values are computed, not stored

Category available balance (`assigned + rollover − spent`) and the month's to-be-assigned (the cumulative chain defined in budget-api: the previous month's To Be Assigned plus the month's signed uncategorized cash and bank activity, minus its assignments, minus the previous month's cash overspending) SHALL be derived at read time from transactions and assignments, never persisted as columns.

#### Scenario: Available reflects a new transaction immediately

- **WHEN** a category has 120,00 € assigned, 32,00 € rollover and a new 138,00 € expense is recorded
- **THEN** the next budget read reports 14,00 € available for that category with no extra write

### Requirement: Category kind and payment schedules persisted

Categories SHALL carry a non-null stored `kind` flag (`flexible` | `savings`, default `flexible`) that records only the user's savings choice; the kind the API exposes is derived (`scheduled` when the category holds payments, `credit_payment` for a card's payment category, otherwise the stored flag) and is never persisted. A `payment_schedules` table SHALL persist schedules (`id`, `user_id`, `category_id` FK, `name`, `amount_cents`, `pattern`, `months`, `month`, `every_n`, `start_month`, `count`, `once_month`, `day`, `estimated`), indexed by `(user_id, category_id)`, applied through an Alembic migration with a working downgrade. Schedules SHALL hold no derived amounts — normal and catch-up amounts are computed on read.

#### Scenario: Migration adds kind and schedules

- **WHEN** `uv run alembic upgrade head` runs on a database at the previous revision
- **THEN** `categories.kind` exists with default `flexible` and the `payment_schedules` table exists

#### Scenario: Downgrade removes them

- **WHEN** the migration is downgraded
- **THEN** `categories.kind` and `payment_schedules` are gone and the rest of the schema is unchanged
