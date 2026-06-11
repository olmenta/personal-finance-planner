# webapp-server-state Delta Specification

## ADDED Requirements

### Requirement: Statement import flow

The transactions screen SHALL offer an "Import bank transactions" flow: pick the source from a list ("BBVA - es", "Sabadell - es", "Custom CSV" — the custom entry offers the downloadable template and explains its columns) and the matching file, upload via `POST /api/imports`, then review the staged rows — each with an editable category select prefilled with the AI suggestion and a visible skipped-duplicates count — and either confirm (with any category overrides) or discard. Confirming SHALL invalidate the transactions, budget, and summary queries for every month present in the batch. Upload and parse failures SHALL surface a retryable, actionable error (which bank/file to check), never a dead end.

#### Scenario: Import reflected after confirm

- **WHEN** the user confirms an imported batch containing June expenses
- **THEN** the transactions list, the June budget bars, and the dashboard summary all reflect the new rows without a page reload

#### Scenario: Unrecognized file

- **WHEN** the upload fails with `file_format_unrecognized`
- **THEN** the dialog explains the file didn't match the chosen bank's format and lets the user pick another file or bank

#### Scenario: Suggested categories are editable

- **WHEN** the review table shows a row with an AI-suggested category
- **THEN** the user can change it before confirming, and the override is what gets saved
