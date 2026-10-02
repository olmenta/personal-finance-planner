# categories-api Delta Specification

## ADDED Requirements

### Requirement: Category kind in the tree and on edit

`GET /categories` SHALL include each category's `kind`, and `PATCH /categories/{id}` SHALL accept `kind` (`flexible` | `scheduled` | `savings`); any other value SHALL return 422. `POST /categories` SHALL accept an optional `kind`, defaulting to `flexible`.

#### Scenario: Mark a category as scheduled

- **WHEN** a client patches "Colegio Tomi" with `kind = "scheduled"`
- **THEN** the tree lists it with `kind = "scheduled"`

#### Scenario: Invalid kind rejected

- **WHEN** a client patches a category with `kind = "monthly"`
- **THEN** the API returns 422
