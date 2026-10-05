# Uncategorized Spending & Category Combobox

## Why

Testing the accounts-and-transfers import flow surfaced three problems. First, an expense confirmed without a category disappears from the budget: it silently lowers To Be Assigned but no row shows it, so the user never learns it needs a category. The dashboard does count it, so the two screens disagree, and the summary spec doesn't even describe what the code does. Second, the import review only offers existing categories in a long, unsearchable dropdown, so a statement with a new kind of expense forces the user to leave the review to create a category. Third, typing a note or payee in the import review lags badly: every keystroke re-renders every row.

## What Changes

- **Uncategorized spending is visible in the budget.**
  - `GET /budget/{month}` reports the month's uncategorized outflows: `uncategorized_cents` and `uncategorized_count`. These are confirmed negative rows without a category, transfers and opening balances excluded, on any account.
  - The budget screen shows a highlighted "Sin categorizar" block above the groups, in warning style, with the total, the count, and a "Categorizar ahora" action. That action runs the existing AI categorization review right there.
  - Nothing else is blocked, and the budget math does not change: those euros have already left To Be Assigned, and categorizing them moves the spending into the chosen category.
- **The summary spec matches the dashboard.** `expense_cents` is everything that left the budget in the month: every confirmed outflow, categorized or not, minus categorized inflows (refunds). Transfers and opening balances are excluded. This is a spec correction; `summary.py` already behaves this way.
- **One category combobox everywhere.** A single searchable combobox replaces the category `Select` in the import review, Add/Edit transaction and the AI categorization review.
  - Typing filters categories by name across groups.
  - When nothing matches exactly, it offers "Crear «X»". That opens a small inline form asking for the group, preselected with the last group used. The form creates the category through `POST /categories`, selects it, and makes it immediately available in every other row and picker.
  - System groups ("Tarjetas de crédito") and archived categories are never offered.
- **Responsive import review.** Each review row becomes an isolated, memoized component with stable callbacks, so editing one row's note, payee, or category re-renders only that row.

## Capabilities

### New Capabilities

- `category-picker`: the shared category combobox: search across groups, excluded categories, inline creation with a group choice and last-used default, and immediate availability of a new category in every open picker.

### Modified Capabilities

- `budget-api`: the budget month view gains `uncategorized_cents` and `uncategorized_count`.
- `budget-assignment`: the assignment screen renders the "Sin categorizar" block with "Categorizar ahora".
- `summary-api`: `expense_cents` is defined as all outflows net of categorized refunds, matching the implementation.
- `category-suggestions`: apply honors an explicit `category_id: null` (clears the category, so an inflow returns to income).
- `webapp-server-state`: the statement import, AI categorization review and transaction dialogs use the category picker, and the import review stays responsive while typing.

## Impact

- **Backend:**
  - `services/budget_view.py` gets one grouped query for the uncategorized outflow total and count.
  - `schemas.py` adds the two `BudgetMonthView` fields.
  - Tests in `tests/test_budget*.py`.
  - No migration.
- **Webapp:**
  - New `components/CategoryCombobox.tsx`, built on shadcn `command` + `popover` (added via the shadcn CLI if they're missing).
  - It replaces the category `Select` in `ImportBankTransactionsDialog`, `AddTransactionDialog`, `EditTransactionDialog` and `SuggestCategoriesDialog`.
  - The import review row is extracted into a memoized component.
  - The budget page gets the "Sin categorizar" block and hosts the suggest flow.
  - `lib/api.ts` types are updated.
- **No API breaking changes:** the new fields are additive, and `POST /categories` is used as it already exists.
- **Out of scope:**
  - Blocking assignments or import confirmation while uncategorized rows exist (explicitly rejected).
  - Category creation from Settings is unchanged.
  - Payee combobox changes (the payee field stays free text with suggestions; only its re-render cost is fixed).
