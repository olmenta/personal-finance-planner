# webapp-server-state Specification

## Purpose

How the webapp reads and mutates server data through TanStack Query: budget month and transactions served by the API instead of mock data, optimistic assignment edits with rollback, cache invalidation after mutations, and loading/error presentation.

## Requirements

### Requirement: Budget month served by the API

The budget screen SHALL read its month view from `GET /api/budget/{month}` via TanStack Query instead of mock data. Derived figures (`to_be_assigned_cents`, `available_cents`) SHALL come from the server response, not be recomputed from client state. Presentation-only attributes (chip `tone`) SHALL be derived client-side from the category.

#### Scenario: Reload preserves state

- **WHEN** the user assigns 412,00 € to a category and reloads the page
- **THEN** the budget screen shows the persisted assignment from the API, not the mock defaults

### Requirement: Optimistic assignment with rollback

Editing a category assignment SHALL update the cached month view optimistically (assignment amount, recomputed to-be-assigned) before the `PUT /api/budget/{month}/assignments/{categoryId}` response arrives. On error, the cache SHALL roll back to the pre-mutation snapshot and the UI SHALL surface a retryable error state.

#### Scenario: Instant hero update

- **WHEN** the user commits an assignment edit
- **THEN** the to-be-assigned hero reflects the new total without waiting for the network round-trip

#### Scenario: Failed mutation rolls back

- **WHEN** the PUT request fails (e.g. backend down, 502)
- **THEN** the assignment and to-be-assigned hero return to their previous values and an error affordance is shown

### Requirement: Suggestion confirmation invalidates the month

`POST /api/budget/{month}/confirm-suggestions` SHALL be issued for draft categories on bulk confirm, after which the month query SHALL be invalidated and refetched so suggestion states come from the server.

#### Scenario: Confirm all drafts

- **WHEN** the user confirms suggestions from the coach capsule
- **THEN** drafted categories show `confirmed` state from the refetched server view and edited categories keep their amounts

### Requirement: Transactions list and creation via API

The transactions screen SHALL list from `GET /api/transactions?month=` joined client-side with `GET /api/categories` for icon and name. Creating a transaction SHALL post to `POST /api/transactions` and on success invalidate both the transactions list and the affected budget month (spent totals change).

#### Scenario: New expense updates budget

- **WHEN** the user registers a 12,49 € expense in Supermercado
- **THEN** the transaction appears in the list and the budget month's `spent_cents` for Supermercado reflects it after invalidation

### Requirement: Payee entry and rendering

The add-transaction dialog SHALL offer a payee field labeled "Payee" for expenses and "Payer" for incomes, suggesting matches from `GET /api/payees` (case-insensitive substring, free text allowed). Selecting a known payee SHALL prefill the category from the payee's `last_category_id` only when no category is chosen yet — never overriding an explicit choice. The transactions list SHALL render the payee as the row's primary line when present, with the note demoted to secondary text; rows without payee render as before. Transaction mutations SHALL invalidate the payees query alongside the existing invalidations.

#### Scenario: Known payee prefills the category

- **WHEN** the user types "Merc", picks the "Mercadona" suggestion, and has not chosen a category
- **THEN** the category select fills with Mercadona's last-used category, still editable

#### Scenario: Explicit category wins

- **WHEN** the user picks a category first and then selects a known payee
- **THEN** the chosen category stays

#### Scenario: Label follows direction

- **WHEN** the user switches the dialog from Expense to Income
- **THEN** the field label changes from "Payee" to "Payer" and behaves identically

#### Scenario: New payee appears in suggestions

- **WHEN** the user saves a transaction with a brand-new payee name
- **THEN** the next dialog open suggests it without a page reload

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

### Requirement: Category management on Settings

The Settings screen SHALL offer a "Categories" section rendering the grouped tree with actions to add a category (name, icon from the Olmenta icon map, group), add a group, rename, change icon, move a category to another group, archive/unarchive a category, and delete an empty group. Every mutation SHALL invalidate the categories query and the current budget month query. Selection UIs (transaction dialogs, import review) SHALL exclude archived categories, while the management section and historical views keep showing them flagged.

#### Scenario: New category usable immediately

- **WHEN** the user adds "Mascotas" from Settings and then opens "Add transaction"
- **THEN** the category select offers "Mascotas" without a page reload

#### Scenario: Archived category leaves the pickers

- **WHEN** the user archives "Ocio"
- **THEN** the transaction dialogs and import review no longer offer it, while Settings still lists it with an archived badge and an unarchive action

#### Scenario: Non-empty group delete surfaces the rule

- **WHEN** the user tries to delete a group that still has categories
- **THEN** the UI explains the group must be empty first and offers no destructive fallback

### Requirement: Loading and error presentation

Screens reading server state SHALL render a non-blocking loading presentation (skeleton or equivalent, no layout shift on resolve) and an error state with a retry action when a query fails. Empty states SHALL invite action, never apologize.

#### Scenario: Backend unreachable

- **WHEN** the budget month query fails with `backend_unavailable`
- **THEN** the screen shows an error state with a retry action instead of mock data

### Requirement: Dashboard served by the API

The dashboard (Overview) SHALL read its data via TanStack Query instead of mock data: balance card and income/expense stat cards from `GET /api/summary/{month}`, the weekly spend chart from the summary's week buckets (labeled "Spent" and "Income"), the budgets panel from `GET /api/budget/{month}` (top categories by spent, limit = assigned + rollover), and recent transactions from `GET /api/transactions?month=` joined client-side with categories. Loading SHALL render skeletons without layout shift on resolve; failures SHALL surface a retryable error state. Creating a transaction from the dashboard SHALL refresh the summary, budget, and transactions queries.

#### Scenario: New expense reflected on Overview

- **WHEN** the user adds a 12,49 € expense from the dashboard's "Add transaction" dialog
- **THEN** after invalidation the expenses stat, the weekly chart, the matching budget bar, and the recent-transactions list all reflect it

#### Scenario: Backend unreachable

- **WHEN** the summary query fails with `backend_unavailable`
- **THEN** the dashboard shows a retryable error state instead of mock values

#### Scenario: Quiet month

- **WHEN** the current month has no transactions
- **THEN** the dashboard renders zero amounts and an empty recent-transactions section inviting the first entry — no error, no mock data

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
