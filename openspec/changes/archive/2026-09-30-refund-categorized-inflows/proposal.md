# Refunds: Categorized Inflows

## Why

A refund (e.g. a returned Mercadona purchase arriving as a positive row in a bank import) currently double-fails: it inflates monthly income / To Be Assigned, and the original category's spent stays unchanged — the money never "returns" to Supermercado. The YNAB rule is: an inflow **with** a category is activity in that category (a refund), not income; only uncategorized inflows fund To Be Assigned. The backend already allows `category_id` on income rows — what's wrong is the aggregation semantics and two UI gates that block assigning the category.

## What Changes

- **Income semantics**: `income_cents` (budget view and summary) counts only positive confirmed transactions **without** a category. A categorized inflow stops counting as income.
- **Spent semantics**: per-category spent becomes the **net** of signed confirmed activity (expenses minus categorized inflows), floored at zero per the view contract where applicable; a 12,50 € refund on Supermercado raises its available by 12,50 €.
- **One source of truth**: `summary.py` currently duplicates the income query inline instead of calling `income_cents` — unify so budget and dashboard can never disagree.
- **Import review**: positive rows get the same category dropdown as negative rows (today hard-coded to "Ready to assign"), defaulting to uncategorized; picking a category marks the row as a refund. AI suggestions may propose a category for inflows whose payee matches the user's history.
- **Manual entry (option 2)**: the income mode of the Add/Edit transaction dialogs gains a collapsed "It's a refund" toggle that reveals the category select; off by default so plain income entry stays friction-free.
- **PATCH gains a clear-category path**: an explicit `category_id: null` clears the row's category (un-marking a refund); an absent field stays "leave untouched". Needed so the edit dialog's toggle can be turned off.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `budget-api`: spent becomes net of categorized activity; income counts only uncategorized inflows (refund scenario added).
- `summary-api`: `income_cents` / `expense_cents` and weekly buckets follow the same categorized-inflow rule.
- `statement-import`: review allows categorizing positive rows (refunds); AI suggestions cover inflows.
- `transactions-api`: PATCH `category_id: null` clears the category (absent stays untouched).

## Impact

- **Backend**: `services/budget_view.py` (`income_cents`, `spent_by_category`), `services/summary.py` (reuse `income_cents`, net expense), `services/category_suggestions.py` (prompt note for inflows). No schema or API contract changes — `TransactionCreate`/`PATCH` already accept optional `category_id` on income.
- **Webapp**: `ImportBankTransactionsDialog.tsx` (dropdown on positive rows), `AddTransactionDialog.tsx` / `EditTransactionDialog.tsx` (refund toggle in income mode).
- **Data**: none. Existing rows keep their meaning (no categorized positive rows exist in practice — both UIs blocked creating them).
- **Future dependency**: `accounts-and-transfers` will add a third exclusion (transfers) to the same centralized income/spent functions — this change must land first.
