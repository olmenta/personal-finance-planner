# Tasks — Bank statement import (BBVA & Sabadell)

## 1. Data model and migration

- [x] 1.1 `ImportBatch` model in `backend/app/models.py` (id, user_id, account_id, source, filename, status, row_count, skipped_duplicates, created_at); `transactions.import_batch_id` → real FK
- [x] 1.2 Alembic migration (`import_batches` table + FK) with working `downgrade()`; `uv run alembic upgrade head` green

## 2. Ingestion port and adapters

- [x] 2.1 `backend/app/ingestion/base.py`: `NormalizedTransaction` dataclass, `TransactionSource` protocol, `StatementFormatError(code)`, shared amount/date cell parsing (design D1)
- [x] 2.2 `BBVAXlsxAdapter` in `ingestion/bbva.py` (openpyxl): header-row detection by column names, `Fecha` date, `Concepto`/`Movimiento` description, `Disponible` balance into `external_ref`
- [x] 2.3 `SabadellXlsAdapter` in `ingestion/sabadell.py` (xlrd): same defensive posture for the Sabadell `.xls` layout (`F. Operativa`, `Concepto`, `Importe`, `Saldo`)
- [x] 2.4 Fixture workbooks generated in `backend/tests/` (anonymized BBVA `.xlsx` via openpyxl + Sabadell `.xls` via xlwt, incl. preamble rows, duplicates, both signs) + adapter tests: amounts/dates parse correctly, same-day identical rows with different balances both survive, unrecognizable/wrong-bank file raises `file_format_unrecognized`
- [x] 2.5 `CustomCsvAdapter` in `ingestion/custom_csv.py` (csv stdlib): required `date`/`amount`/`description`, optional `category` → `NormalizedTransaction.category_hint` + `balance` → dedupe ref; `,`/`;` delimiters, utf-8/latin-1 fallback, case-insensitive headers; tests incl. missing-column → `file_format_unrecognized`

## 3. AI category suggestions

- [x] 3.1 `uv add anthropic openpyxl xlrd` (+ `xlwt` dev); `anthropic_api_key` + `anthropic_model` (default `claude-opus-4-8`) in `config.py`; `.env.example` entry
- [x] 3.2 `backend/app/services/category_suggestions.py`: one structured-output Anthropic call per batch with category tree + rows (incl. `category_hint` when present), validate ids against the user's categories, fail-open to all-null on any exception (design D5)
- [x] 3.3 Tests with mocked Anthropic client: suggestion mapped, hallucinated id → null, exception → all-null import still succeeds

## 4. Import pipeline and API

- [x] 4.1 `backend/app/services/import_batch.py`: `create_batch` (parse → normalize → in-file + DB dedupe with unsalted hash → suggestions → staged rows + batch in one transaction), `confirm_batch(overrides)`, `discard_batch` (design D2–D4)
- [x] 4.2 Schemas: `ImportBatchView` (status, counts, staged `TransactionOut` rows), `ConfirmImportRequest{overrides}`
- [x] 4.3 `backend/app/routers/imports.py`: `POST /imports` (multipart, size/row limits → 413 `file_too_large`, format error → 422 `file_format_unrecognized`), `GET /imports/{id}`, `POST /imports/{id}/confirm` (409 `batch_not_staged` when not staged), `DELETE /imports/{id}`; register in `main.py`
- [x] 4.4 `GET /transactions`: add `status == "confirmed"` filter; adjust/extend existing tests
- [x] 4.5 API tests: upload stages rows without touching budget/summary, re-import is idempotent (all skipped), in-file duplicates collapse, confirm with override updates budget, discard deletes staged rows and allows re-upload, double confirm 409; `uv run pytest` green

## 5. BFF and client

- [x] 5.1 Route Handlers: `webapp/src/app/api/imports/route.ts` (multipart passthrough, design D7), `[id]/route.ts` (GET, DELETE), `[id]/confirm/route.ts` (POST)
- [x] 5.2 `webapp/src/lib/api.ts`: `ImportBatchView` type, `uploadImport(file, bank)` (FormData), `fetchImport`, `confirmImport(id, overrides)`, `discardImport`

## 6. Import UI

- [x] 6.1 `ImportBankTransactionsDialog` component: step 1 list of available sources ("BBVA - es", "Sabadell - es", "Custom CSV" with template download link + column explanation) + file input (`accept` per source); step 2 review table (date, description, amount tones, category Select prefilled with suggestion + "Suggested" badge, duplicates-skipped line); footer "Confirm import" / "Discard" (design D8)
- [x] 6.4 Template file `webapp/public/import-template.csv` (header + example rows documenting required/optional columns)
- [x] 6.2 Error states: `file_format_unrecognized` → actionable message with retry (pick another file/bank); `backend_unavailable` → retryable error
- [x] 6.3 "Import bank transactions" button on the transactions screen beside "Add transaction"; on confirm invalidate `["transactions"]` plus `["budget", m]` / `["summary", m]` for every month in the batch

## 7. Verification

- [x] 7.1 `volta run npm run build` green in `webapp/`; `uv run pytest` green in `backend/` (with `TEST_DATABASE_URL` → `neondb_test`)
- [x] 7.2 E2E with both processes: upload real export from `backend/bank-exports-examples/` → review shows suggestions → confirm → transactions list, budget bars, dashboard update; re-upload same file → all rows reported as duplicates; discard path leaves no rows behind
