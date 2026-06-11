# bff-proxy Delta Specification

## MODIFIED Requirements

### Requirement: Route Handlers proxy the backend API

The webapp SHALL expose Next.js Route Handlers under `/api/*` that forward requests to the FastAPI backend for every endpoint the UI consumes: `GET /api/categories`, `POST /api/categories`, `PATCH /api/categories/{id}`, `POST /api/categories/groups`, `PATCH /api/categories/groups/{id}`, `DELETE /api/categories/groups/{id}`, `GET /api/transactions` (with query string), `POST /api/transactions`, `GET /api/budget/{month}`, `PUT /api/budget/{month}/assignments/{categoryId}`, `POST /api/budget/{month}/confirm-suggestions`, `GET /api/summary/{month}`, `POST /api/imports` (multipart upload forwarded with its body and content type), `GET /api/imports/{id}`, `POST /api/imports/{id}/confirm`, and `DELETE /api/imports/{id}`. The browser SHALL NOT call the FastAPI backend directly.

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

#### Scenario: Category mutation proxied

- **WHEN** the browser sends `PATCH /api/categories/{id}` with a JSON body
- **THEN** the backend receives the same body at `PATCH {BACKEND_URL}/categories/{id}` and the response passes through unchanged

> Note: the in-flight `edit-delete-transactions` change also modifies this requirement (adds `PATCH`/`DELETE /api/transactions/{id}`). Whichever change syncs second must merge both endpoint lists.
