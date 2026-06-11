# Design — Bank statement import (BBVA & Sabadell Excel exports)

## Context

Transactions enter only via manual `POST /transactions`. The data model already anticipates import: `Transaction` carries `source`, `status` (`staged|confirmed`), `dedupe_hash` (unique per account), and a loose `import_batch_id` column; budget and summary aggregation already exclude staged rows. Missing: the `ImportBatch` table, the ingestion port/adapters (§6.3), the AI suggestion service, import endpoints, and UI. The backend runs locally against Neon with Alembic (one revision so far); there is no GCP infra, so the project-definition's Cloud Tasks/GCS pieces cannot be built yet.

**Reality check (real exports in `backend/bank-exports-examples/`, gitignored — they contain PII):** neither bank exports CSV. BBVA exports `.xlsx` (sheet "Informe BBVA": 4 preamble rows, header `F.Valor | Fecha | Concepto | Movimiento | Importe | Divisa | Disponible | Divisa | Observaciones`, leading empty column). Sabadell exports legacy `.xls` (sheet with 8 preamble rows incl. IBAN/holder, header `F. Operativa | Concepto | F. Valor | Importe | Saldo | Referencia 1 | Referencia 2`). Dates are `DD/MM/YYYY` strings (defensively: may be Excel date cells), amounts are signed floats (defensively: may be es-ES strings like `-1.234,56`). Spanish bank export layouts change without notice — adapters must be defensive and fixture-tested.

## Goals / Non-Goals

**Goals:**

- `TransactionSource` port + `BBVAXlsxAdapter`/`SabadellXlsAdapter` so future adapters (Open Banking, WhatsApp, OCR) reuse the same pipeline untouched.
- Full pipeline: parse → normalize → dedupe → AI category suggestion → staged review → confirm/discard.
- Real Anthropic suggestions that degrade gracefully (uncategorized, never a failed import).
- Review UI on the transactions screen meeting the "no apologizing, invite action" voice rules.

**Non-Goals:**

- Async workers (Cloud Tasks) and GCS raw-file retention — synchronous processing behind a service boundary; raw file bytes are parsed in-memory and discarded (GDPR-friendlier than the eventual retention window).
- Other banks, CSV variants of the exports, format auto-detection across banks (user picks the bank), batch rollback after confirm, re-import of a previously discarded batch.

## Decisions

### D1 — Port returns normalized rows; pipeline is adapter-agnostic

`backend/app/ingestion/base.py` defines `NormalizedTransaction` (frozen dataclass: `date`, signed `amount_cents`, `currency`, `description`, `external_ref: str | None`, `raw_payload: dict`) and the `TransactionSource` protocol: `parse(content: bytes) -> list[NormalizedTransaction]`, raising `StatementFormatError(code)` on unrecognizable input. Adapters live beside it (`bbva.py`, `sabadell.py`) and own all bank-specific mess:

- **BBVA `.xlsx`** via `openpyxl` (`read_only`, `data_only`, from `BytesIO`): scan for the header row (cells containing the known column set `F.Valor/Fecha/Concepto/Movimiento/Importe/...` — preamble length is not assumed), then map columns by header name, not position. Transaction date = `Fecha` (booking date); description = `Concepto`, with `Movimiento` appended (`"Concepto — Movimiento"`) when it adds detail beyond the concept; running balance = `Disponible`.
- **Sabadell `.xls`** via `xlrd` (2.x reads only legacy `.xls` — exactly right): same header-scan approach over `F. Operativa/Concepto/F. Valor/Importe/Saldo/...`. Transaction date = `F. Operativa`; description = `Concepto`; running balance = `Saldo`.
- **Shared defensive parsing** in `base.py` helpers: amounts may be floats (the normal case) or es-ES strings (`-1.234,56`) → signed cents via `Decimal`; dates may be `DD/MM/YYYY` strings or Excel datetime cells; currency defaults to `EUR`. A file that doesn't open with the expected engine or whose header row is never found raises `StatementFormatError("file_format_unrecognized")` — including the wrong-bank case (BBVA file with Sabadell selected opens but finds no Sabadell header).

Neither bank provides a per-row unique id, so `external_ref` carries `"{description}|bal:{balance_cents}"` — the running balance disambiguates legitimate same-day identical rows (two identical metro tickets have different balances) while staying stable across re-exports of overlapping ranges. `raw_payload` keeps the full original row keyed by header for audit/debug.

- **Custom CSV** (`CustomCsvAdapter`, `csv` stdlib): the escape hatch for any other bank. The user downloads a template (`/import-template.csv`, served from `webapp/public/`), fills it manually from their bank's export, and uploads it as the "Custom CSV" source. Required columns: `date` (DD/MM/YYYY or YYYY-MM-DD), `amount` (signed; dot or es-ES comma decimal), `description`. Optional columns: `category` — free text that does **not** need to match the user's category list; it is passed to the suggestion model as a hint (`NormalizedTransaction.category_hint`) and mapped by the LLM — and `balance` (running balance, improves dedupe exactly like the bank adapters). Delimiter `,` or `;`, utf-8 with latin-1 fallback, header matched case-insensitively. Without a balance column, same-day identical rows collapse in dedupe — documented in the template.

Alternatives rejected: pandas — heavyweight for two known layouts; converting to CSV first — loses cell types and adds a lossy step. `openpyxl` + `xlrd` with explicit header maps is more debuggable when formats drift.

### D2 — Synchronous pipeline behind a service function

`services/import_batch.py:create_batch(db, user, bank, filename, content) -> ImportBatch` runs the whole pipeline in-request. Upload limits (2 MB, max 2 000 rows) keep request time bounded; the real exports are tens of KB (`.xls` is the bloated one: ~40 KB for 57 rows). The service function is the future Cloud Tasks worker body — extracting it later changes the router, not the pipeline. Alternative rejected: building the queue now — no GCP infra exists, and a fake local queue adds failure modes without buying anything.

### D3 — Dedupe reuses the existing hash + constraint, strict for imports

Import rows hash `(account_id, date, amount_cents, external_ref or description)` with **no salt** (manual entries keep their per-row salt — two identical coffees are legitimate; two identical bank rows are the same row). Because `external_ref` includes the running balance (D1), legitimate same-day identical purchases survive while re-imports of overlapping date ranges dedupe exactly. In-file duplicates collapse first; then one query fetches existing hashes for the account and collisions are skipped, counted, and reported as `skipped_duplicates` on the batch. Re-importing the same file is therefore idempotent: 0 new rows. The DB unique constraint `uq_txn_account_dedupe` stays as the backstop.

### D4 — `ImportBatch` rows + staged transactions in one transaction

New model: `ImportBatch(id, user_id, account_id, source, filename, status[staged|confirmed|discarded], row_count, skipped_duplicates, created_at)` (project §6.4 plus the two counters the review UI needs). Staged transactions are written with `status="staged"`, `source="import_bbva"|"import_sabadell"` (channel-neutral: the same values survive a future format change; Open Banking gets its own `ob_*` sources), `import_batch_id` set, AI-suggested `category_id` (nullable). Alembic migration adds the table and a real FK on `transactions.import_batch_id`. Confirm = single `UPDATE` to `confirmed` (+ batch status); discard = delete staged rows + mark batch `discarded`. Confirming an already-confirmed batch is a 409 `batch_not_staged`.

### D5 — One Anthropic call per batch, structured output, fail-open

`services/category_suggestions.py:suggest(categories, rows) -> dict[row_index, category_id | None]` makes **one** structured-output call (`anthropic` SDK via `uv add anthropic`, model `claude-opus-4-8` — configurable as `anthropic_model` in `config.py`, key via `ANTHROPIC_API_KEY` in `.env`). Prompt: the user's category tree (id, name, group) + numbered rows (`date, description, amount`, plus the row's free-text `category_hint` when the custom CSV provided one — the hint doesn't need to match the tree, the model maps it), es locale; output a Pydantic schema mapping row index → category id or null, validated server-side against real category ids (hallucinated ids → null). Any exception (no key, rate limit, timeout) logs a warning and returns all-null — rows stage uncategorized and the user assigns in review; the import never fails because AI did. Per-batch rather than per-row keeps it to one round-trip and lets the model see merchant repetition. Transaction descriptions are sent to Anthropic — same data-processor posture as the planned onboarding interview (§6.2 AI row); no other PII leaves the system. Tests mock the client; no live calls in CI.

### D6 — API shape

| Endpoint | Behavior |
|---|---|
| `POST /imports` (multipart: `file` = the bank's Excel export, `bank=bbva\|sabadell`) | run pipeline, 201 → batch view with staged rows |
| `GET /imports/{id}` | batch view (status, counts, staged rows joined client-side with categories) |
| `POST /imports/{id}/confirm` | body `{overrides: {txn_id: category_id}}`; apply overrides, flip rows + batch to confirmed |
| `DELETE /imports/{id}` | delete staged rows, batch → `discarded`, 204 |

Unparseable file → 422 `{code: "file_format_unrecognized"}`; oversize → 413 `file_too_large`; wrong bank chosen surfaces as format error. `GET /transactions` gains `Transaction.status == "confirmed"` in its where-clause — staged rows are only visible through the batch view.

### D7 — BFF multipart passthrough

New Route Handlers `webapp/src/app/api/imports/...`. The existing `proxyFetch` JSON helper doesn't fit multipart; the upload handler forwards `request.formData()` to the backend with fetch (no Content-Type override — fetch sets the boundary) while reusing the backend-URL/error conventions (`backend_unavailable` 502). Other three routes are plain `proxyFetch`.

### D8 — Review UI as a dialog flow on the transactions screen

"Import bank transactions" secondary button beside "Add transaction" → `ImportBankTransactionsDialog`: step 1 a list of available sources ("BBVA - es", "Sabadell - es", "Custom CSV" — a list, not a segmented control, so v1.x banks append without redesign) + file input (`accept=".xlsx,.xls"` for banks, `.csv` for the custom source); the Custom CSV entry links to the downloadable template and explains the required/optional columns; step 2 review table (date, description, amount with income/expense tones, category `Select` prefilled with the suggestion, "Suggested" badge when AI-filled) + "N duplicates skipped" line; footer "Confirm import" / "Discard". TanStack mutation per step; on confirm invalidate `["transactions"]`, `["budget", month]`, `["summary", month]` for every month present in the batch (imports span months, unlike single adds). No new route — keeps entry where users already think about transactions.

## Risks / Trade-offs

- [Bank export layouts drift without notice] → adapters are defensive (header detection by name, explicit error codes) and fixture-tested with anonymized samples mirroring the real exports; a format change breaks one adapter file, and `StatementFormatError` shows the user an actionable message instead of garbage rows.
- [LLM suggests wrong categories] → suggestions are visibly editable defaults in review, validated against real category ids, and never auto-confirmed; the user always sees and approves every row.
- [Large file in-request could block the event loop] → hard limits (2 MB / 2 000 rows) + sync SQLAlchemy already runs in FastAPI's threadpool; Anthropic call is the slowest step and is one call per batch.
- [Anthropic outage degrades UX] → fail-open to uncategorized staging; import remains fully usable.
- [No raw-file retention means no re-processing after a parser fix] → acceptable in v1: the user still has the file and can re-upload; dedupe makes re-upload safe.

## Migration Plan

1. Alembic migration (`import_batches` + FK) — additive, deployable alone.
2. Backend: ingestion package, suggestion service, batch service, router, tests.
3. BFF routes + `api.ts` helpers (dead until used).
4. Transactions screen UI.
Rollback: revert webapp commit; backend endpoints additive; migration has a clean `downgrade()`.

## Open Questions

- None blocking. (Test fixtures are anonymized `.xlsx`/`.xls` files generated at test time with `openpyxl`/`xlwt`, mirroring the real exports in `backend/bank-exports-examples/` — which stay gitignored because they contain PII.)
