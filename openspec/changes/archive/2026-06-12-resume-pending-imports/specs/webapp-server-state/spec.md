# webapp-server-state Delta Specification

## MODIFIED Requirements

### Requirement: Statement import flow

The transactions screen SHALL offer an "Import bank transactions" flow: pick the source from a list ("BBVA - es", "Sabadell - es", "Custom CSV" — the custom entry offers the downloadable template and explains its columns) and the matching file, upload via `POST /api/imports`, then review the staged rows — each with an editable category select prefilled with the AI suggestion and a visible skipped-duplicates count — and either confirm (with any category overrides) or discard. While a pending (staged) batch exists, the transactions screen SHALL show a persistent banner naming the file and row count with a "Resume review" action that reopens the review step, the import dialog SHALL open directly into that review instead of offering a new upload, and a 409 `import_pending` from upload SHALL navigate to the pending review rather than render an error. The skipped-duplicates copy SHALL state that skipped rows are already-imported transactions, and an all-skipped upload SHALL render an explanatory empty state, not a failure. Upload, confirm, and discard SHALL invalidate the pending-import query; confirming SHALL additionally invalidate the transactions, budget, and summary queries for every month present in the batch. Upload and parse failures SHALL surface a retryable, actionable error (which bank/file to check), never a dead end.

#### Scenario: Import reflected after confirm

- **WHEN** the user confirms an imported batch containing June expenses
- **THEN** the transactions list, the June budget bars, and the dashboard summary all reflect the new rows without a page reload

#### Scenario: Closed review is resumable

- **WHEN** the user uploads a statement, closes the review dialog without confirming, and returns to the transactions screen later
- **THEN** a banner names the pending file and row count, and "Resume review" reopens the review with the staged rows intact

#### Scenario: Dialog reopens into the pending review

- **WHEN** a pending batch exists and the user opens "Import bank transactions"
- **THEN** the dialog shows the pending review (with discard available) instead of the source picker

#### Scenario: All rows already imported

- **WHEN** an upload stages 0 rows because every row collides with confirmed transactions
- **THEN** the review explains the rows are already imported and points to the transactions list, instead of presenting a dead-end zero count
