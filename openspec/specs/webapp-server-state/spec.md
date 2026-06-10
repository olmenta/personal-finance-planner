# webapp-server-state Specification

## Purpose

How the webapp reads and mutates server data through TanStack Query: budget month and transactions served by the API instead of mock data, optimistic assignment edits with rollback, cache invalidation after mutations, and loading/error presentation.

## Requirements

### Requirement: Budget month served by the API

The budget screen SHALL read its month view from `GET /api/budget/{month}` via TanStack Query instead of mock data. Derived figures (`to_be_assigned_cents`, `available_cents`) SHALL come from the server response, not be recomputed from client state. Presentation-only attributes (chip `tone`) SHALL be derived client-side from the category.

#### Scenario: Reload preserves state

- **WHEN** the user assigns 412,00 € to a category and reloads the page
- **THEN** the budget screen shows the persisted assignment from the API, not the mock defaults

### Requirement: Optimistic assignment with rollback

Editing a category assignment SHALL update the cached month view optimistically (assignment amount, recomputed to-be-assigned) before the `PUT /api/budget/{month}/assignments/{categoryId}` response arrives. On error, the cache SHALL roll back to the pre-mutation snapshot and the UI SHALL surface a retryable error state.

#### Scenario: Instant hero update

- **WHEN** the user commits an assignment edit
- **THEN** the to-be-assigned hero reflects the new total without waiting for the network round-trip

#### Scenario: Failed mutation rolls back

- **WHEN** the PUT request fails (e.g. backend down, 502)
- **THEN** the assignment and to-be-assigned hero return to their previous values and an error affordance is shown

### Requirement: Suggestion confirmation invalidates the month

`POST /api/budget/{month}/confirm-suggestions` SHALL be issued for draft categories on bulk confirm, after which the month query SHALL be invalidated and refetched so suggestion states come from the server.

#### Scenario: Confirm all drafts

- **WHEN** the user confirms suggestions from the coach capsule
- **THEN** drafted categories show `confirmed` state from the refetched server view and edited categories keep their amounts

### Requirement: Transactions list and creation via API

The transactions screen SHALL list from `GET /api/transactions?month=` joined client-side with `GET /api/categories` for icon and name. Creating a transaction SHALL post to `POST /api/transactions` and on success invalidate both the transactions list and the affected budget month (spent totals change).

#### Scenario: New expense updates budget

- **WHEN** the user registers a 12,49 € expense in Supermercado
- **THEN** the transaction appears in the list and the budget month's `spent_cents` for Supermercado reflects it after invalidation

### Requirement: Loading and error presentation

Screens reading server state SHALL render a non-blocking loading presentation (skeleton or equivalent, no layout shift on resolve) and an error state with a retry action when a query fails. Empty states SHALL invite action, never apologize.

#### Scenario: Backend unreachable

- **WHEN** the budget month query fails with `backend_unavailable`
- **THEN** the screen shows an error state with a retry action instead of mock data

### Requirement: Dashboard served by the API

The dashboard (Overview) SHALL read its data via TanStack Query instead of mock data: balance card and income/expense stat cards from `GET /api/summary/{month}`, the weekly spend chart from the summary's week buckets (labeled "Spent" and "Income"), the budgets panel from `GET /api/budget/{month}` (top categories by spent, limit = assigned + rollover), and recent transactions from `GET /api/transactions?month=` joined client-side with categories. Loading SHALL render skeletons without layout shift on resolve; failures SHALL surface a retryable error state. Creating a transaction from the dashboard SHALL refresh the summary, budget, and transactions queries.

#### Scenario: New expense reflected on Overview

- **WHEN** the user adds a 12,49 € expense from the dashboard's "Add transaction" dialog
- **THEN** after invalidation the expenses stat, the weekly chart, the matching budget bar, and the recent-transactions list all reflect it

#### Scenario: Backend unreachable

- **WHEN** the summary query fails with `backend_unavailable`
- **THEN** the dashboard shows a retryable error state instead of mock values

#### Scenario: Quiet month

- **WHEN** the current month has no transactions
- **THEN** the dashboard renders zero amounts and an empty recent-transactions section inviting the first entry — no error, no mock data
