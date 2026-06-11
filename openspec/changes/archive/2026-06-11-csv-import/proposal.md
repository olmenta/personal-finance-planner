# Proposal — Bank statement import (BBVA & Sabadell)

## Why

Manual entry is the only way to get transactions into Olmenta today, which makes the first budget month expensive to set up and the app useless for people with months of history in their bank. Statement import is v1 feature 4 (project-definition §4.1, there called "CSV import"): import BBVA Spain and Sabadell Spain statement exports through the parse → normalize → deduplicate → AI category suggestion → user confirmation pipeline, built behind the `TransactionSource` port so Open Banking (v3) plugs into the same pipeline (§6.3). Real exports (see `backend/bank-exports-examples/`, gitignored — PII) show neither bank exports CSV: BBVA produces `.xlsx`, Sabadell legacy `.xls` — the adapters parse those.

## What Changes

- **Ingestion port + adapters**: `TransactionSource` interface returning the normalized contract (`date`, signed `amount_cents`, `currency`, `description`, `external_ref`, `category_hint`, `raw_payload`); `BBVAXlsxAdapter` (openpyxl) and `SabadellXlsAdapter` (xlrd) with defensive parsing (header-row detection by column names, float or es-ES string amounts, DD/MM/YYYY or Excel-date cells, running balance as dedupe discriminator) covered by fixture-based tests with anonymized generated samples.
- **Custom CSV template**: a downloadable template (`webapp/public/import-template.csv`) the user fills manually from any other bank's export; `CustomCsvAdapter` parses it (required `date`, `amount`, `description`; optional `category` — free text used as an LLM hint, no need to match the category list — and `balance` for dedupe).
- **Import batch lifecycle**: new `ImportBatch` model + Alembic migration; `POST /imports` (Excel upload, bank choice) runs the pipeline and stages transactions (`status=staged`, `source=import_bbva|import_sabadell|import_custom`); `GET /imports/{id}` returns the batch with staged rows; `POST /imports/{id}/confirm` (with per-row category overrides) flips rows to `confirmed`; `DELETE /imports/{id}` discards the batch and its staged rows.
- **Deduplication**: rows are hashed `(account, date, amount, external_ref|description)` and checked in-file and against existing transactions (existing unique `dedupe_hash` per account); duplicates are skipped and reported, never imported twice.
- **AI category suggestion**: Anthropic API call (Python backend only) suggesting a category per staged row from the user's category tree; suggestion failure degrades to uncategorized rows, never blocks the import.
- **Import UI**: "Import bank transactions" entry on the transactions screen → upload (file + bank picked from a list of available banks) → review staged rows with editable category selects prefilled with AI suggestions and a skipped-duplicates count → confirm or discard; confirmed rows refresh transactions, budget, and summary queries.
- **Staged rows excluded from normal reads**: `GET /transactions` returns confirmed transactions only (staged rows are visible only through the import review); budget/summary aggregation already excludes staged.
- **Out of scope**: Cloud Tasks async workers and GCS raw-file storage (processing is synchronous in-request behind a service boundary; the raw file is never persisted), other banks' formats (v1.x), CSV variants, Open Banking adapters (v3), batch rollback after confirmation.

## Capabilities

### New Capabilities

- `statement-import`: import batch lifecycle — upload, parse/normalize/dedupe through the `TransactionSource` port, staged review, confirm/discard.
- `category-suggestions`: AI category suggestion for ingested transactions (Anthropic, backend-only), used by the import pipeline.

### Modified Capabilities

- `data-model`: `ImportBatch` entity; transactions gain real `source` values (`import_bbva`, `import_sabadell`, `import_custom`) and an enforced link to their import batch; first Alembic migration on an existing schema.
- `transactions-api`: the list requirement changes — `GET /transactions` returns confirmed transactions only.
- `bff-proxy`: proxied-routes requirement gains the `/api/imports*` routes (including multipart upload forwarding).
- `webapp-server-state`: new requirement — import flow (upload, review staged rows, confirm/discard) via the API with cache invalidation.

## Impact

- `backend/app/`: new `ingestion/` (port + adapters), `services/import_batch.py`, `services/category_suggestions.py`, `routers/imports.py`; `models.py` + Alembic migration; `uv add anthropic openpyxl xlrd` (+ `xlwt` dev-only for fixture generation); `ANTHROPIC_API_KEY` config.
- `backend/tests/`: adapter fixture tests (anonymized generated BBVA/Sabadell workbooks), pipeline/dedupe tests, API tests with mocked Anthropic client.
- `webapp/src/app/api/imports/*`: new Route Handlers (multipart passthrough).
- `webapp/src/lib/api.ts`: import types + fetch helpers.
- `webapp/src/app/(app)/transactions/`: "Import bank transactions" entry + review flow component.
