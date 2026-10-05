# webapp-server-state Delta Specification

## MODIFIED Requirements

### Requirement: Transactions list and creation via API

The transactions screen SHALL list from `GET /api/transactions?month=` joined client-side with `GET /api/categories` for icon and name. The Add and Edit transaction dialogs SHALL choose the category with the category picker (see category-picker). Creating a transaction SHALL post to `POST /api/transactions` and on success invalidate both the transactions list and the affected budget month (spent totals change).

#### Scenario: New expense updates budget

- **WHEN** the user registers a 12,49 € expense in Supermercado
- **THEN** the transaction appears in the list and the budget month's `spent_cents` for Supermercado reflects it after invalidation

#### Scenario: Category found by typing

- **WHEN** the user opens the category picker in Add transaction and types "super"
- **THEN** the list narrows to matching categories such as "Supermercado" and selecting one fills the field

### Requirement: AI categorization review flow

The transactions screen SHALL offer a "Suggest categories" action when confirmed uncategorized transactions exist. Triggering it SHALL request proposals and open a review dialog listing each proposed row (date, description, amount, editable category picker (see category-picker) and editable payee input prefilled with the proposals, confidence badge) with per-row checkboxes defaulting to checked and low-confidence rows sorted first. Applying SHALL post only the checked rows (with any overrides) to the apply endpoint and invalidate the transactions query plus the budget and summary queries for every affected month. An empty proposal list (nothing uncategorized, or AI unavailable) SHALL render an actionable empty state, never a dead end, and the AI SHALL never write a category without the user applying it.

#### Scenario: Bulk categorization applied

- **WHEN** the user runs "Suggest categories" over 40 uncategorized rows and applies 30 of them
- **THEN** those 30 transactions show their categories in the list and the affected months' budget bars and dashboard refresh without a page reload

#### Scenario: Low confidence surfaces first

- **WHEN** proposals include `low` and `high` confidence rows
- **THEN** the review dialog lists the low-confidence rows first with a distinct badge

#### Scenario: AI unavailable

- **WHEN** the suggestion request returns no proposals
- **THEN** the dialog explains nothing could be suggested right now and points to manual categorization instead of showing an error wall

### Requirement: Statement import flow

The transactions screen SHALL offer an "Import bank transactions" flow: pick the source from a list ("BBVA - es", "Sabadell - es", "Custom CSV" — the custom entry offers the downloadable template and explains its columns) and the matching file, upload via `POST /api/imports`, then review the staged rows — each with an editable category picker (see category-picker) prefilled with the AI suggestion and a visible skipped-duplicates count — and either confirm (with any category overrides) or discard. While a pending (staged) batch exists, the transactions screen SHALL show a persistent banner naming the file and row count with a "Resume review" action that reopens the review step, the import dialog SHALL open directly into that review instead of offering a new upload, and a 409 `import_pending` from upload SHALL navigate to the pending review rather than render an error. The skipped-duplicates copy SHALL state that skipped rows are already-imported transactions, and an all-skipped upload SHALL render an explanatory empty state, not a failure. Upload, confirm, and discard SHALL invalidate the pending-import query; confirming SHALL additionally invalidate the transactions, budget, and summary queries for every month present in the batch. Upload and parse failures SHALL surface a retryable, actionable error (which bank/file to check), never a dead end.

#### Scenario: Import reflected after confirm

- **WHEN** the user confirms an imported batch containing June expenses
- **THEN** the transactions list, the June budget bars, and the dashboard summary all reflect the new rows without a page reload

#### Scenario: Unrecognized file

- **WHEN** the upload fails with `file_format_unrecognized`
- **THEN** the dialog explains the file didn't match the chosen bank's format and lets the user pick another file or bank

#### Scenario: Suggested categories are editable

- **WHEN** the review table shows a row with an AI-suggested category
- **THEN** the user can change it before confirming, and the override is what gets saved

#### Scenario: Closed review is resumable

- **WHEN** the user uploads a statement, closes the review dialog without confirming, and returns to the transactions screen later
- **THEN** a banner names the pending file and row count, and "Resume review" reopens the review with the staged rows intact

#### Scenario: Dialog reopens into the pending review

- **WHEN** a pending batch exists and the user opens "Import bank transactions"
- **THEN** the dialog shows the pending review (with discard available) instead of the source picker

#### Scenario: All rows already imported

- **WHEN** an upload stages 0 rows because every row collides with confirmed transactions
- **THEN** the review explains the rows are already imported and points to the transactions list, instead of presenting a dead-end zero count

#### Scenario: Typing stays responsive in a long review

- **WHEN** a review lists 150 staged rows and the user types a note or a payee in one of them
- **THEN** every keystroke appears immediately, because editing one row re-renders only that row

#### Scenario: New category from the review

- **WHEN** a statement has a row for a kind of expense the user has no category for
- **THEN** the user creates the category from that row's picker without leaving the review, and the following rows can pick it
