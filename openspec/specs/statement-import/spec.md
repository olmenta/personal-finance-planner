# statement-import Specification

## Purpose

Bank statement ingestion: a normalized `TransactionSource` port with BBVA, Sabadell, and custom-CSV adapters, an import batch API that stages parsed rows for review, deduplication against known rows, and the confirm/discard lifecycle that turns staged rows into confirmed transactions.

## Requirements

### Requirement: Normalized ingestion port

Transaction ingestion SHALL go through a `TransactionSource` port that returns rows in a normalized contract — `date`, signed `amount_cents` (expenses negative, income positive), `currency`, `description`, optional `external_ref`, and the `raw_payload` — so that new sources (Open Banking, WhatsApp, OCR) plug into the same pipeline without changes to domain logic. v1 SHALL provide `BBVAXlsxAdapter` (BBVA `.xlsx` exports) and `SabadellXlsAdapter` (Sabadell legacy `.xls` exports) with defensive parsing: header-row detection by column names (preamble length not assumed), amounts as floats or es-ES strings (`-1.234,56`), dates as `DD/MM/YYYY` strings or Excel date cells, and the row's running balance folded into `external_ref` so identical same-day rows stay distinguishable. Unrecognizable input — including a file from the other bank — SHALL raise a typed format error with a machine-readable code.

#### Scenario: BBVA export parsed

- **WHEN** a BBVA Spain `.xlsx` export containing a row dated `09/06/2026` with amount `-12.49` is parsed
- **THEN** the adapter yields a normalized row with `amount_cents = -1249` and `date = 2026-06-09`

#### Scenario: Unrecognizable file

- **WHEN** a file whose header rows match neither bank layout is submitted (including choosing the wrong bank for a valid file)
- **THEN** parsing fails with error code `file_format_unrecognized` and no transactions are created

### Requirement: Import batch upload stages transactions

The API SHALL expose `POST /imports` accepting a multipart statement file and a `bank` choice (`bbva` | `sabadell` | `custom`). It SHALL run parse → normalize → deduplicate → AI category suggestion synchronously and create an `ImportBatch` plus one transaction per surviving row with `status = "staged"`, `source = "import_bbva" | "import_sabadell" | "import_custom"`, the batch id, and the suggested `category_id` (nullable). Staged rows SHALL NOT affect budget, summary, or the transactions list. Files over the size/row limits SHALL be rejected with a machine-readable code, and the raw file SHALL NOT be persisted.

#### Scenario: Successful upload

- **WHEN** a valid Sabadell `.xls` export with 40 new rows is uploaded
- **THEN** the API returns 201 with a batch of 40 staged transactions, and `GET /budget/{month}` totals are unchanged until confirmation

#### Scenario: Oversize file rejected

- **WHEN** a file larger than the configured limit is uploaded
- **THEN** the API returns 413 with code `file_too_large` and no batch is created

### Requirement: Custom CSV template

For banks without a dedicated adapter, the webapp SHALL offer a downloadable CSV template the user fills manually from their bank's export and uploads as the `custom` source. The template SHALL require `date` (DD/MM/YYYY or YYYY-MM-DD), signed `amount` (dot or es-ES comma decimal), and `description` columns, and SHALL accept optional `category` (free text used as a suggestion hint — it does not need to match the user's category list) and `balance` (running balance, used as the dedupe discriminator) columns. The adapter SHALL accept `,` or `;` delimiters and utf-8 or latin-1 encoding, matching headers case-insensitively.

#### Scenario: Custom CSV parsed

- **WHEN** a filled template with a row `15/05/2026;-12,30;Mercadona;Supermercado` is uploaded as `custom`
- **THEN** a normalized row with `amount_cents = -1230`, `date = 2026-05-15`, and `category_hint = "Supermercado"` is staged

#### Scenario: Missing required column

- **WHEN** a CSV without an `amount` column is uploaded as `custom`
- **THEN** parsing fails with error code `file_format_unrecognized` and no transactions are created

### Requirement: Deduplication skips known rows

Each imported row SHALL be hashed over `(account, date, amount, external_ref or description)` without salt. Rows whose hash already exists for the account — in the same file or from any earlier import or entry — SHALL be skipped, counted, and reported on the batch as `skipped_duplicates`, never imported twice.

#### Scenario: Re-importing the same file

- **WHEN** the same statement file is uploaded twice and the first batch was confirmed
- **THEN** the second batch stages 0 transactions and reports every row in `skipped_duplicates`

#### Scenario: In-file duplicates collapse

- **WHEN** a statement file contains two rows identical including their running balance
- **THEN** exactly one staged transaction is created and one duplicate is reported

#### Scenario: Same-day identical purchases survive

- **WHEN** a statement contains two same-day rows with the same description and amount but different running balances
- **THEN** both rows are staged

### Requirement: Review, confirm, and discard

The API SHALL expose `GET /imports/{id}` returning the batch (status, `row_count`, `skipped_duplicates`, staged rows), `POST /imports/{id}/confirm` accepting per-row category overrides and flipping the batch's staged rows to `confirmed`, and `DELETE /imports/{id}` deleting the staged rows and marking the batch `discarded`. Per-row category selection SHALL be available for positive rows as well as negative ones: a positive row defaults to uncategorized ("Ready to assign" — it confirms as income) and MAY be assigned a category during review, which confirms it as a refund (category activity). AI category suggestions MAY propose a category for a positive row whose cleaned payee matches the user's categorization history, and SHALL leave unmatched positive rows unsuggested. Confirmed rows SHALL immediately count in budget, summary, and the transactions list. Confirming or discarding a batch that is not `staged` SHALL return 409 with a machine-readable code.

#### Scenario: Confirm with override

- **WHEN** the user confirms a batch overriding one row's category from the AI suggestion to "Ocio"
- **THEN** all rows become `confirmed`, the overridden row carries "Ocio", and the month's budget `spent_cents` reflects the batch

#### Scenario: Imported refund categorized at review

- **WHEN** a statement stages `ABONO MERCADONA +12,50` and the user assigns it the Supermercado category before confirming
- **THEN** the confirmed row carries Supermercado, the month's Supermercado `spent_cents` drops by 12,50 €, and `income_cents` does not include it

#### Scenario: Positive row left uncategorized is income

- **WHEN** a staged positive row is confirmed without a category
- **THEN** it counts in the month's `income_cents` (To Be Assigned)

#### Scenario: Discard a batch

- **WHEN** the user discards a staged batch
- **THEN** its staged transactions are deleted, the batch is `discarded`, and a later re-upload of the same file stages the rows again

#### Scenario: Double confirm rejected

- **WHEN** confirm is called on an already-confirmed batch
- **THEN** the API returns 409 with code `batch_not_staged`

### Requirement: Single pending import batch

The backend SHALL allow at most one `staged` import batch per user. `POST /imports` SHALL return 409 with code `import_pending` (carrying the pending batch id) while a staged batch exists, instead of staging a second one. Confirming or discarding the pending batch SHALL clear the invariant. This makes orphaned staged batches — invisible rows blocking re-imports through dedupe collisions — unrepresentable.

#### Scenario: Second upload blocked

- **WHEN** a user with a staged batch uploads another statement file
- **THEN** the API returns 409 with code `import_pending` and the existing batch id, and no new batch or rows are created

#### Scenario: Upload allowed after discard

- **WHEN** the user discards their pending batch and uploads again
- **THEN** the upload stages normally

### Requirement: Pending batch endpoint

The API SHALL expose `GET /imports/pending` returning the user's staged batch as a full batch view (same shape as `GET /imports/{id}`, staged rows included), or 404 with code `no_pending_import` when none exists. The endpoint is singular by design — the single-pending invariant means there is never a list.

#### Scenario: Pending batch fetched

- **WHEN** the user has a staged batch and requests `GET /imports/pending`
- **THEN** the response is the batch view with its staged rows, suggestions, and skip count

#### Scenario: No pending batch

- **WHEN** the user has no staged batch
- **THEN** the API returns 404 with code `no_pending_import`
