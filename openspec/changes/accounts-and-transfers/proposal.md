# Accounts & Transfers

## Why

v1 runs on one invisible seeded account: every transaction and import lands in "the user's first account". Real money lives across checking accounts, cash, and credit cards, and moves between them — and today a transfer imported from two banks would double-count as expense (bank A) plus income (bank B), corrupting the budget. YNAB's two-plane model (accounts = where money sits; categories = what it's for) requires first-class accounts and transfers that touch the account plane only.

## What Changes

- **Multiple accounts**: account CRUD with types `cash | bank | credit`, derived balances (sum of the account's confirmed transactions), and an opening-balance transaction at creation — YNAB-pure: an uncategorized inflow that funds To Be Assigned (negative for credit cards carrying debt, which lowers TBA honestly).
- **Account selection**: manual entry and edit dialogs gain an account picker (defaulting to the main account, preserving the <5s entry promise); statement upload binds the batch to a chosen account instead of "the first one".
- **Transfers**: a transfer is **two linked twin rows** (shared `transfer_pair_id`) — outflow in the source account, inflow in the destination — with **no category and no payee**, excluded from income, spent, and expense aggregates everywhere (they move money between pockets; the budget plane never sees them). Manual creation via a third "Transfer" mode in the dialogs (from/to/amount/date/note). Editing amount or date updates both twins; an unlink action splits a mistaken pair back into independent rows.
- **Transfers at import**: the review dropdown gains a "Transfers →" pseudo-group listing the user's other accounts; marking a row creates (or links) the twin on confirm. When the second bank's statement is later imported, a matcher **suggests** linking rows that mirror an existing twin (same amount, opposite sign, matching account, date within tolerance) — never silently.
- **Credit cards, option B**: a `credit` account with negative balance; purchases are categorized normally at swipe time (they're real spending); the monthly card payment is a transfer Bank → Card (not an expense — counting it would double-count every purchase). No YNAB auto-move machinery in v1 (additive later).
- **Visual**: transfer rows render with a both-ways icon, "Transfer → <account>" in place of payee, and neutral amount color — income green / expense red stay reserved for money entering/leaving the budget.
- **Onboarding**: the interview asks which bank accounts and credit cards the user has (they become proposed accounts in the review screen — new "Accounts" section with uncheck/rename/add) plus an optional, skippable question for the primary bank account's current balance; finalize creates the accepted accounts and writes the opening-balance transaction so a new user starts with a real To Be Assigned. Loans from the debt phase stay debt-paydown categories (YNAB models them as off-budget tracking accounts — out of v1 scope; the budget effect, a categorized monthly payment, is identical); credit cards become accounts instead of categories. Prompt config bumps to `onboarding_v2`.

## Capabilities

### New Capabilities

- `accounts-api`: account CRUD contract, types, derived balances, opening-balance semantics, main-account default.
- `transfers`: the twin-row transfer entity — creation, mirrored editing, unlinking, and exclusion from all budget-plane aggregates.

### Modified Capabilities

- `data-model`: `Account.type` gains `credit`; `Transaction.transfer_pair_id` (nullable, indexed); `opening_balance` transaction source.
- `transactions-api`: create/edit accept `account_id` (default: main account); transfer rows are read-only through the normal PATCH (edited via the transfer contract).
- `statement-import`: upload targets a chosen account; review can mark rows as transfers; twin matcher suggests links on the second bank's import.
- `budget-api`: income/spent exclude transfer rows.
- `summary-api`: income/expense/weekly buckets exclude transfer rows (all-time `balance_cents` is naturally unaffected — twins cancel out).
- `ai-onboarding`: optional opening-balance question in the interview; finalize writes the opening-balance transaction.

## Impact

- **Backend**: `models.py` (+`transfer_pair_id`, `credit` type), one Alembic migration, new `routers/accounts.py` + `services/transfers.py`, edits to `routers/transactions.py` / `routers/imports.py` (the three "first account" query sites), `budget_view.py` / `summary.py` (one exclusion added to the centralized income/spent functions).
- **Webapp**: accounts list screen + account picker, third "Transfer" segment in Add/Edit dialogs, transfer rendering in `TransactionRow`, "Transfers →" group in the import review dropdown, BFF routes `/api/accounts*`, `/api/transfers*`.
- **Depends on**: `refund-categorized-inflows` must land and sync first — it centralizes the income/spent semantics this change extends with the transfer exclusion (its budget-api/summary-api delta text builds on the refund wording).
- **Out of scope**: YNAB credit-card auto-move and payment category; automatic transfer detection from description text (AI hint later); multi-currency.
