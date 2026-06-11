# bff-proxy Specification

## Purpose

Next.js Route Handlers acting as a backend-for-frontend: the browser talks only to `/api/*` on the webapp, which forwards to the FastAPI backend, keeping the backend URL server-side and passing through statuses and machine-readable errors unchanged.

## Requirements

### Requirement: Route Handlers proxy the backend API

The webapp SHALL expose Next.js Route Handlers under `/api/*` that forward requests to the FastAPI backend for every endpoint the UI consumes: `GET /api/categories`, `POST /api/categories`, `PATCH /api/categories/{id}`, `POST /api/categories/groups`, `PATCH /api/categories/groups/{id}`, `DELETE /api/categories/groups/{id}`, `GET /api/payees`, `GET /api/transactions` (with query string), `POST /api/transactions`, `PATCH /api/transactions/{id}`, `DELETE /api/transactions/{id}`, `GET /api/budget/{month}`, `PUT /api/budget/{month}/assignments/{categoryId}`, `POST /api/budget/{month}/confirm-suggestions`, `GET /api/summary/{month}`, `POST /api/imports` (multipart upload forwarded with its body and content type), `GET /api/imports/{id}`, `POST /api/imports/{id}/confirm`, and `DELETE /api/imports/{id}`. The browser SHALL NOT call the FastAPI backend directly.

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

#### Scenario: Payees proxied

- **WHEN** the browser requests `GET /api/payees`
- **THEN** the Route Handler fetches `GET {BACKEND_URL}/payees` and returns the backend's JSON body unchanged

#### Scenario: Transaction edit proxied

- **WHEN** the browser sends `PATCH /api/transactions/{id}` with a JSON body
- **THEN** the backend receives the same body at `PATCH {BACKEND_URL}/transactions/{id}` and the response passes through unchanged

#### Scenario: Transaction delete proxied

- **WHEN** the browser sends `DELETE /api/transactions/{id}`
- **THEN** the Route Handler forwards it and passes the backend's 204 (or error) through unchanged

#### Scenario: Category mutation proxied

- **WHEN** the browser sends `PATCH /api/categories/{id}` with a JSON body
- **THEN** the backend receives the same body at `PATCH {BACKEND_URL}/categories/{id}` and the response passes through unchanged

### Requirement: Backend base URL from server environment

The proxy SHALL resolve the backend base URL from the `BACKEND_URL` server-side environment variable (default `http://localhost:8000` for local dev). The variable SHALL NOT be exposed to the client bundle (no `NEXT_PUBLIC_` prefix).

#### Scenario: Local default

- **WHEN** `BACKEND_URL` is unset in local dev
- **THEN** the proxy targets `http://localhost:8000`

### Requirement: Status and error pass-through

The proxy SHALL pass through the backend's HTTP status code and machine-readable error body (`{"code": "<snake_case>"}`) without translation or wrapping. When the backend is unreachable, the proxy SHALL respond `502` with `{"code": "backend_unavailable"}`.

#### Scenario: Validation error surfaces unchanged

- **WHEN** the backend answers `422` with `{"code": "invalid_amount"}`
- **THEN** the browser receives `422` with the same body

#### Scenario: Backend down

- **WHEN** the FastAPI process is not running
- **THEN** the Route Handler responds `502` with `{"code": "backend_unavailable"}`

### Requirement: No caching of financial data

Proxy responses SHALL NOT be statically cached by Next.js: handlers SHALL opt out of route caching so every request reflects current backend state (client-side caching is the server-state layer's job).

#### Scenario: Fresh data after mutation

- **WHEN** an assignment is updated and the budget view is refetched
- **THEN** the response reflects the new assignment, not a cached body
