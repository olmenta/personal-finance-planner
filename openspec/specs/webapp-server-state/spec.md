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

### Requirement: AI categorization review flow

The transactions screen SHALL offer a "Suggest categories" action when confirmed uncategorized transactions exist. Triggering it SHALL request proposals and open a review dialog listing each proposed row (date, description, amount, editable category select and editable payee input prefilled with the proposals, confidence badge) with per-row checkboxes defaulting to checked and low-confidence rows sorted first. Applying SHALL post only the checked rows (with any overrides) to the apply endpoint and invalidate the transactions query plus the budget and summary queries for every affected month. An empty proposal list (nothing uncategorized, or AI unavailable) SHALL render an actionable empty state, never a dead end, and the AI SHALL never write a category without the user applying it.

#### Scenario: Bulk categorization applied

- **WHEN** the user runs "Suggest categories" over 40 uncategorized rows and applies 30 of them
- **THEN** those 30 transactions show their categories in the list and the affected months' budget bars and dashboard refresh without a page reload

#### Scenario: Low confidence surfaces first

- **WHEN** proposals include `low` and `high` confidence rows
- **THEN** the review dialog lists the low-confidence rows first with a distinct badge

#### Scenario: AI unavailable

- **WHEN** the suggestion request returns no proposals
- **THEN** the dialog explains nothing could be suggested right now and points to manual categorization instead of showing an error wall

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

The transactions screen SHALL offer an "Import bank transactions" flow: pick the source from a list ("BBVA - es", "Sabadell - es", "Custom CSV" — the custom entry offers the downloadable template and explains its columns) and the matching file, upload via `POST /api/imports`, then review the staged rows — each with an editable category select prefilled with the AI suggestion and a visible skipped-duplicates count — and either confirm (with any category overrides) or discard. While a pending (staged) batch exists, the transactions screen SHALL show a persistent banner naming the file and row count with a "Resume review" action that reopens the review step, the import dialog SHALL open directly into that review instead of offering a new upload, and a 409 `import_pending` from upload SHALL navigate to the pending review rather than render an error. The skipped-duplicates copy SHALL state that skipped rows are already-imported transactions, and an all-skipped upload SHALL render an explanatory empty state, not a failure. Upload, confirm, and discard SHALL invalidate the pending-import query; confirming SHALL additionally invalidate the transactions, budget, and summary queries for every month present in the batch. Upload and parse failures SHALL surface a retryable, actionable error (which bank/file to check), never a dead end.

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

### Requirement: Move money mutation

Moving money SHALL go through `POST /api/budget/{month}/moves` via a TanStack Query mutation that optimistically updates the cached month view (source and target assignments and availables; To Be Assigned when the source is "Sin asignar") and replaces the cache with the server's returned view on success. On error the cache SHALL roll back and the UI SHALL surface the machine-readable code as a translated, retryable message.

#### Scenario: Optimistic cover

- **WHEN** the user taps "Cubrir desde Restaurantes" on an overspent Supermercado row
- **THEN** both rows reflect the move immediately, and the server's view replaces the cache when the response arrives

#### Scenario: Rejected move rolls back

- **WHEN** the server answers 422 `insufficient_available` because another device spent the money meanwhile
- **THEN** the rows return to their previous values and an error message invites retrying

### Requirement: Cover prompt after saving a transaction

After a transaction is created or edited from the Add/Edit dialogs, or an import batch is confirmed, the webapp SHALL refetch the affected month (as today) and, when a category touched by that write now has `overspent_cents > 0`, show a non-blocking prompt with the category's `cover_suggestion` ("Supermercado se pasó 50,00 €. Cubrir desde Restaurantes") offering one-tap cover and "Elegir otra" (opens the move-money sheet). The save itself SHALL complete and close its dialog before the prompt appears; dismissing the prompt SHALL leave the overspending visible on the budget screen.

#### Scenario: Overspending expense

- **WHEN** the user adds a 60,00 € Supermercado expense that leaves the category 50,00 € over
- **THEN** the dialog closes as usual and a prompt offers to cover the 50,00 € from the suggested source

#### Scenario: No prompt without overspending

- **WHEN** a saved expense stays within the category's available
- **THEN** no cover prompt appears
