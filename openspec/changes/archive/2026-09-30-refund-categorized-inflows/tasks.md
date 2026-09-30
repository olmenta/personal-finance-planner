# Tasks — Refunds: Categorized Inflows

## 1. Backend semantics

- [x] 1.1 `budget_view.income_cents`: count only positive confirmed transactions with `category_id IS NULL`
- [x] 1.2 `budget_view.spent_by_category`: drop the negative-only filter — negated net of signed confirmed activity per category
- [x] 1.3 `summary.py`: replace the inline income query with `income_cents`; `expense_cents` and weekly buckets follow the same categorized-net rule (refunds net expenses, never income)
- [x] 1.4 `category_suggestions._build_prompt`: note that positive rows may be refunds — suggest the matched category only when the cleaned payee appears in the user's history, else null

## 2. Backend tests

- [x] 2.1 Budget view: categorized refund lowers `spent_cents` and raises `available_cents`; excluded from `income_cents`; uncategorized inflow still counts as income
- [x] 2.2 Summary: refund nets `expense_cents`, leaves `income_cents` unchanged; week bucket totals still sum to month totals
- [x] 2.3 Import confirm: positive row with category override confirms as refund (budget reflects it); without category confirms as income

## 3. Webapp

- [x] 3.1 `ImportBankTransactionsDialog.tsx`: replace the hard-coded "Ready to assign" branch on positive rows with the category Select, defaulting to an explicit "Ready to assign" (uncategorized) option
- [x] 3.2 `AddTransactionDialog.tsx`: income mode gains a collapsed "It's a refund" switch revealing the category select; submit requires a category only while the switch is on; payload carries `category_id` then
- [x] 3.3 `EditTransactionDialog.tsx`: same toggle, pre-enabled when the income row already has a category
- [x] 3.4 Transactions list: income rows with a category render the category (refund), not the generic income icon

## 4. Verification

- [x] 4.1 `uv run pytest` green in `backend/` (144 passed)
- [x] 4.2 `volta run npm run build` + lint green in `webapp/`
- [x] 4.3 Manual: import a statement with a positive row, categorize it at review, confirm — category available rises, dashboard income unchanged
