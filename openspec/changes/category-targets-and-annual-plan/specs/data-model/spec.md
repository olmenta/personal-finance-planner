# data-model Delta Specification

## ADDED Requirements

### Requirement: Category kind and payment schedules persisted

Categories SHALL carry a non-null `kind` (`flexible` | `scheduled` | `savings`, default `flexible`). A `payment_schedules` table SHALL persist schedules (`id`, `user_id`, `category_id` FK, `name`, `amount_cents`, `pattern`, `months`, `month`, `every_n`, `start_month`, `count`, `once_month`, `day`, `estimated`), indexed by `(user_id, category_id)`, applied through an Alembic migration with a working downgrade. Schedules SHALL hold no derived amounts — normal and catch-up amounts are computed on read.

#### Scenario: Migration adds kind and schedules

- **WHEN** `uv run alembic upgrade head` runs on a database at the previous revision
- **THEN** `categories.kind` exists with default `flexible` and the `payment_schedules` table exists

#### Scenario: Downgrade removes them

- **WHEN** the migration is downgraded
- **THEN** `categories.kind` and `payment_schedules` are gone and the rest of the schema is unchanged
