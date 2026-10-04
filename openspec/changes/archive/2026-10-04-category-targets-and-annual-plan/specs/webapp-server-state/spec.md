# webapp-server-state Delta Specification

## MODIFIED Requirements

### Requirement: Dashboard served by the API

The dashboard (Overview) SHALL read its data via TanStack Query instead of mock data: the primary "Este mes" panel from `GET /api/overview/{month}` (see month-overview), the next three months from `GET /api/plan/upcoming?from={month}`, the weekly spend chart from `GET /api/summary/{month}` week buckets (labeled "Spent" and "Income"), and recent transactions from `GET /api/transactions?month=` joined client-side with categories. Loading SHALL render skeletons without layout shift on resolve; failures SHALL surface a retryable error state. Creating a transaction from the dashboard SHALL refresh the overview, upcoming, summary, budget, and transactions queries.

#### Scenario: New expense reflected on Overview

- **WHEN** the user adds a 12,49 € expense from the dashboard's "Add transaction" dialog
- **THEN** after invalidation "Already paid this month", "Left to spend", the weekly chart, and the recent-transactions list all reflect it

#### Scenario: Backend unreachable

- **WHEN** the overview query fails with `backend_unavailable`
- **THEN** the dashboard shows a retryable error state instead of mock values

#### Scenario: Quiet month

- **WHEN** the current month has no transactions
- **THEN** the dashboard renders zero amounts and an empty recent-transactions section inviting the first entry — no error, no mock data
