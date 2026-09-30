# bff-proxy Delta Specification

## MODIFIED Requirements

### Requirement: Route Handlers proxy the backend API

The webapp SHALL expose Next.js Route Handlers under `/api/*` that forward requests to the FastAPI backend for every endpoint the UI consumes: `GET /api/categories`, `POST /api/categories`, `PATCH /api/categories/{id}`, `POST /api/categories/groups`, `PATCH /api/categories/groups/{id}`, `DELETE /api/categories/groups/{id}`, `GET /api/payees`, `GET /api/transactions` (with query string), `POST /api/transactions`, `PATCH /api/transactions/{id}`, `DELETE /api/transactions/{id}`, `POST /api/transactions/suggest-categories`, `POST /api/transactions/apply-categories`, `GET /api/budget/{month}`, `PUT /api/budget/{month}/assignments/{categoryId}`, `POST /api/budget/{month}/confirm-suggestions`, `GET /api/summary/{month}`, `POST /api/imports` (multipart upload forwarded with its body and content type), `GET /api/imports/pending`, `GET /api/imports/{id}`, `POST /api/imports/{id}/confirm`, `DELETE /api/imports/{id}`, `POST /api/onboarding/start`, `GET /api/onboarding/session`, `GET /api/onboarding/status`, `POST /api/onboarding/messages`, `POST /api/onboarding/{id}/finalize`, and `POST /api/onboarding/template`. The browser SHALL NOT call the FastAPI backend directly.

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

#### Scenario: Pending import proxied

- **WHEN** the browser requests `GET /api/imports/pending`
- **THEN** the Route Handler fetches `GET {BACKEND_URL}/imports/pending` and passes the batch view (or the 404 with `no_pending_import`) through unchanged

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

#### Scenario: Suggestion run proxied

- **WHEN** the browser sends `POST /api/transactions/suggest-categories`
- **THEN** the backend receives it at `POST {BACKEND_URL}/transactions/suggest-categories` and the proposal list passes through unchanged

#### Scenario: Onboarding turn proxied

- **WHEN** the browser sends `POST /api/onboarding/messages` with the user's reply
- **THEN** the backend receives it at `POST {BACKEND_URL}/onboarding/messages` and the structured turn (or the 503 with `onboarding_unavailable`) passes through unchanged
