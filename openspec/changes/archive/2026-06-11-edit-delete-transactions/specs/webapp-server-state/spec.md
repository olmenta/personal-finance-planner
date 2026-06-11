# webapp-server-state Delta Specification

## ADDED Requirements

### Requirement: Edit and delete from the transactions list

Each row on the transactions screen SHALL offer an actions menu with "Edit" and "Delete". Edit SHALL open a dialog prefilled with the row's direction, amount, payee, note, category, and date, and submit a partial update via `PATCH /api/transactions/{id}`. Delete SHALL ask exactly one confirmation (showing the row's description and amount, with a destructive-styled action) before calling `DELETE /api/transactions/{id}`. On success either action SHALL invalidate the transactions query plus the budget and summary queries for every affected month — for an edit that changes the date, both the old and the new month.

#### Scenario: Edit reflected everywhere

- **WHEN** the user edits a June expense's amount in the dialog and saves
- **THEN** the transactions list, June budget bars, and dashboard summary show the new amount without a page reload

#### Scenario: Date change invalidates both months

- **WHEN** the user moves a transaction from June to May in the edit dialog
- **THEN** budget and summary queries for both 2026-06 and 2026-05 are invalidated

#### Scenario: Delete needs one confirmation

- **WHEN** the user picks "Delete" from a row's actions menu
- **THEN** a confirmation dialog names the transaction, and only confirming removes it and refreshes the affected queries
