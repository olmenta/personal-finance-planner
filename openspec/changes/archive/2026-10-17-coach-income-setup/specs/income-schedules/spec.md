## ADDED Requirements

### Requirement: One shared income operation

Creating, updating and deleting an income schedule, and linking an inflow to a schedule, SHALL go through one backend operation used by the income API, the coach and the dev MCP server (through the API). It SHALL apply the schedule validation, the partial-update merge (switching pattern drops the other pattern's fields; an empty payer clears it) and payer resolution. The API's responses and error codes SHALL stay as they are.

`POST /income/link {transaction_id, schedule_id}` SHALL apply the linking rule atomically:

- the schedule's payee is given to the transaction;
- or, when the schedule has none, the transaction's payee is given to the schedule;
- or, when neither has one, the schedule's name becomes a payee resolved for both.

It returns the month's income view. The transaction must be a confirmed, uncategorized inflow of the user (404 `transaction_not_found` otherwise), and the schedule the user's (404).

#### Scenario: Linked in one step

- **WHEN** the client posts a link for an unplanned inflow without payer and a schedule with payer "Acme"
- **THEN** the inflow gets the payee Acme, and the returned month view shows the occurrence as received

#### Scenario: Neither has a payer

- **WHEN** the schedule "Clases" and the inflow both lack a payer
- **THEN** a payee "Clases" is resolved, both get it, and later inflows from it match automatically
