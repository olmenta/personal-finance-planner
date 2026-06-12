# bff-proxy Delta Specification

## MODIFIED Requirements

### Requirement: Route Handlers proxy the backend API

The webapp SHALL expose Next.js Route Handlers under `/api/*` that forward requests to the FastAPI backend for every endpoint the UI consumes: `GET /api/categories`, `POST /api/categories`, `PATCH /api/categories/{id}`, `POST /api/categories/groups`, `PATCH /api/categories/groups/{id}`, `DELETE /api/categories/groups/{id}`, `GET /api/payees`, `GET /api/transactions` (with query string), `POST /api/transactions`, `PATCH /api/transactions/{id}`, `DELETE /api/transactions/{id}`, `POST /api/transactions/suggest-categories`, `POST /api/transactions/apply-categories`, `GET /api/budget/{month}`, `PUT /api/budget/{month}/assignments/{categoryId}`, `POST /api/budget/{month}/confirm-suggestions`, `GET /api/summary/{month}`, `POST /api/imports` (multipart upload forwarded with its body and content type), `GET /api/imports/{id}`, `POST /api/imports/{id}/confirm`, and `DELETE /api/imports/{id}`. The browser SHALL NOT call the FastAPI backend directly.

#### Scenario: Budget view proxied

- **WHEN** the browser requests `GET /api/budget/2026-06`
- **THEN** the Route Handler fetches `GET {BACKEND_URL}/budget/2026-06` and returns the backend's JSON body unchanged

#### Scenario: Query string forwarded

- **WHEN** the browser requests `GET /api/transactions?month=2026-06`
- **THEN** the backend receives the same `month` query parameter

#### Scenario: Summary proxied

- **WHEN** the browser requests `GET /api/summary/2026-06`
- **THEN** the Route Handler fetches `GET {BACKEND_URL}/summary/2026-06` and returns the backend's JSON body unchanged

#### Scenario: Statement upload forwarded

- **WHEN** the browser posts a multipart form with a bank statement file to `/api/imports`
- **THEN** the backend receives the same file and `bank` field, and the response body and status pass through unchanged

#### Scenario: Suggestion run proxied

- **WHEN** the browser sends `POST /api/transactions/suggest-categories`
- **THEN** the backend receives it at `POST {BACKEND_URL}/transactions/suggest-categories` and the proposal list passes through unchanged

> Note: `edit-delete-transactions` and `manage-categories` (both in flight) also modify this requirement. Whichever change syncs last must merge all endpoint lists.
