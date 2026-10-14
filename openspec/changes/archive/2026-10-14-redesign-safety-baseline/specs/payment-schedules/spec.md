## ADDED Requirements

### Requirement: Supported planning horizon

Dated payments SHALL be limited to the planning horizon of the catch-up calculation (120 months from the current month). A `once` schedule whose `once_month`, or a personal debt whose `due_month`, falls beyond it SHALL be rejected with 422 `outside_planning_horizon`, so a zero monthly amount never implies that no funding is needed.

#### Scenario: Too far ahead

- **WHEN** in October 2026 a client creates a `once` payment for October 2037
- **THEN** the API returns 422 `outside_planning_horizon` and nothing is saved

#### Scenario: Inside the horizon

- **WHEN** in October 2026 a client creates a `once` payment for April 2028
- **THEN** it is saved and its catch-up amount spreads it over every month until then
