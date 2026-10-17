## ADDED Requirements

### Requirement: One shared payment operation

Creating, updating and deleting a payment SHALL go through one backend operation used by the schedules API, the coach and the dev MCP server (through the API). It SHALL validate the fields, enforce the debt and card-plan guards and the planning horizon, write the payment, and refresh the computed assignments of the current and later materialized months. The API's responses and error codes SHALL stay as they are.

#### Scenario: Same rules from the chat and the editor

- **WHEN** the coach confirms a monthly payment of 40,00 € for "Luz" in an open October
- **THEN** October's assignment for "Luz" becomes 40,00 €, exactly as if it had been saved from the schedule editor

#### Scenario: Same refusal

- **WHEN** a `once` payment for October 2037 is proposed from the chat in October 2026
- **THEN** it's refused with `outside_planning_horizon`, as the API does
