# categories-api Delta Specification

## ADDED Requirements

### Requirement: Category kind and savings flag

`GET /categories` SHALL include each category's derived `kind` (`scheduled` | `savings` | `flexible`, see payment-schedules) and its `savings` flag. `POST /categories` and `PATCH /categories/{id}` SHALL accept an optional boolean `savings` (default false on create); a non-boolean value SHALL return 422. The kind itself SHALL NOT be writable.

#### Scenario: Mark a category as savings

- **WHEN** a client patches "Ahorro Tomy" with `savings = true`
- **THEN** the tree lists it with `savings = true` and `kind = "savings"`

#### Scenario: Invalid flag rejected

- **WHEN** a client patches a category with `savings = "maybe"`
- **THEN** the API returns 422
