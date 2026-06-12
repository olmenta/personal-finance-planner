# bff-proxy Delta Specification

## MODIFIED Requirements

### Requirement: Route Handlers proxy the backend API

The webapp SHALL expose Next.js Route Handlers under `/api/*` that forward requests to the FastAPI backend for every endpoint the UI consumes: `GET /api/categories`, `POST /api/categories`, `PATCH /api/categories/{id}`, `POST /api/categories/groups`, `PATCH /api/categories/groups/{id}`, `DELETE /api/categories/groups/{id}`, `GET /api/payees`, `GET /api/transactions` (with query string), `POST /api/transactions`, `PATCH /api/transactions/{id}`, `DELETE /api/transactions/{id}`, `POST /api/transactions/suggest-categories`, `POST /api/transactions/apply-categories`, `GET /api/budget/{month}`, `PUT /api/budget/{month}/assignments/{categoryId}`, `POST /api/budget/{month}/confirm-suggestions`, `GET /api/summary/{month}`, `POST /api/imports` (multipart upload forwarded with its body and content type), `GET /api/imports/pending`, `GET /api/imports/{id}`, `POST /api/imports/{id}/confirm`, and `DELETE /api/imports/{id}`. The browser SHALL NOT call the FastAPI backend directly.

#### Scenario: Pending import proxied

- **WHEN** the browser requests `GET /api/imports/pending`
- **THEN** the Route Handler fetches `GET {BACKEND_URL}/imports/pending` and passes the batch view (or the 404 with `no_pending_import`) through unchanged

> Note: delta written against main as of 2026-06-12 (includes payees, transaction edit/delete, category management, and AI-review endpoints). If anything else lands first, merge endpoint lists at sync time.
