# Accounts & Transfers

## Why

v1 runs on one invisible seeded account: every transaction and import lands in "the user's first account". Real money lives across checking accounts, cash, and credit cards, and moves between them — and today a transfer imported from two banks would double-count as expense (bank A) plus income (bank B), corrupting the budget. YNAB's two-plane model (accounts = where money sits; categories = what it's for) requires first-class accounts and transfers that touch the account plane only.

## What Changes

- **Multiple accounts**: account CRUD with types `cash | bank | credit`, derived balances (sum of the account's confirmed transactions), and an opening-balance transaction at creation — YNAB-pure: on a cash/bank account an uncategorized inflow that funds To Be Assigned; on a credit card, pre-existing debt that does not touch To Be Assigned and shows as uncovered debt.
- **Account selection**: manual entry and edit dialogs gain an account picker (defaulting to the main account, preserving the <5s entry promise); statement upload binds the batch to a chosen account instead of "the first one".
- **Transfers**: a transfer is **two linked twin rows** (shared `transfer_pair_id`) — outflow in the source account, inflow in the destination — with **no category and no payee**, excluded from income, spent, and expense aggregates everywhere (they move money between pockets; the budget plane never sees them). Manual creation via a third "Transfer" mode in the dialogs (from/to/amount/date/note). Editing amount or date updates both twins; an unlink action splits a mistaken pair back into independent rows.
- **Transfers at import**: the review dropdown gains a "Transfers →" pseudo-group listing the user's other accounts; marking a row creates (or links) the twin on confirm. When the second bank's statement is later imported, a matcher **suggests** linking rows that mirror an existing twin (same amount, opposite sign, matching account, date within tolerance) — never silently.
- **Credit cards, YNAB model** (revised 2026-09-30, replacing option B): every credit account gets a system **payment category** ("Pago <card>") in a "Tarjetas de crédito" group. A categorized purchase on the card is spending in its category at purchase time **and** moves the budgeted amount to the payment category (derived at read time, To Be Assigned untouched), so the money to pay the card is always set aside. Paying the card is a Bank → Card transfer that consumes the payment category. Card spending beyond the category's available is **credit overspending**: it doesn't move, doesn't carry into next month, and stays visible as uncovered card debt. Refunds on the card move money back; interest and fees are ordinary categorized card outflows.
- **Card payment day**: optional `payment_day` asked at card creation; when unknown, the backend suggests one from the card payments seen in imported statements (never applied silently). Stored now for the coach's future "can the next charge be paid?" check.
- **Visual**: transfer rows render with a both-ways icon, "Transfer → <account>" in place of payee, and neutral amount color — income green / expense red stay reserved for money entering/leaving the budget. Credit balances read as an amount owed ("Debes 200,00 €"), not a red negative.
- **Onboarding**: the interview asks which bank accounts and credit cards the user has (they become proposed accounts in the review screen — new "Accounts" section with uncheck/rename/add) plus an optional, skippable question for the primary bank account's current balance; finalize creates the accepted accounts and writes the opening-balance transaction so a new user starts with a real To Be Assigned. Loans from the debt phase stay debt-paydown categories (YNAB models them as off-budget tracking accounts — out of v1 scope; the budget effect, a categorized monthly payment, is identical); credit cards become accounts (with their payment category) instead of categories. Prompt config bumps to `onboarding_v2`.

## Capabilities

### New Capabilities

- `accounts-api`: account CRUD contract, types, derived balances, opening-balance semantics, main-account default.
- `transfers`: the twin-row transfer entity — creation, mirrored editing, unlinking, and exclusion from all budget-plane aggregates.
- `credit-cards`: payment category per card, funded moves from budgeted card spending, credit overspending as debt, uncovered-debt visibility, payment day (asked or inferred).

### Modified Capabilities

- `data-model`: `Account.type` gains `credit`; `Account.payment_day`; `Category.payment_account_id`; `CategoryGroup.system`; `Transaction.transfer_pair_id` (nullable, indexed); `opening_balance` transaction source.
- `transactions-api`: create/edit accept `account_id` (default: main account); transfer rows are read-only through the normal PATCH (edited via the transfer contract).
- `statement-import`: upload targets a chosen account; review can mark rows as transfers; twin matcher suggests links on the second bank's import; confirmed card payments feed payment-day inference.
- `budget-api`: income/spent exclude transfer rows; "Tarjetas de crédito" group with payment categories and funded moves; `credit_overspent_cents`; rollover drops credit overspending; credit opening balances excluded from income.
- `summary-api`: income/expense/weekly buckets exclude transfer rows (all-time `balance_cents` is naturally unaffected — twins cancel out).
- `ai-onboarding`: optional opening-balance question in the interview; finalize writes the opening-balance transaction.

## Impact

- **Backend**: `models.py` (+`transfer_pair_id`, `credit` type, `payment_day`, `payment_account_id`, `CategoryGroup.system`), one Alembic migration, new `routers/accounts.py` + `services/transfers.py`, edits to `routers/transactions.py` / `routers/imports.py` (the three "first account" query sites), `budget_view.py` (transfer exclusion + credit-card funded moves, credit overspending, payment group) / `summary.py` (transfer exclusion), `routers/categories.py` (payment categories locked).
- **Webapp**: accounts list screen ("Debes …" for cards, payment day + suggestion chip) + account picker, third "Transfer" segment in Add/Edit dialogs, transfer rendering in `TransactionRow`, "Transfers →" group in the import review dropdown, "Tarjetas de crédito" group and credit-overspending style on the budget screen, BFF routes `/api/accounts*`, `/api/transfers*`.
- **Depends on**: `refund-categorized-inflows` (done, archived 2026-09-30) — it centralized the income/spent semantics this change extends.
- **Out of scope**: automatic transfer detection from description text (AI hint later); multi-currency; paying down pre-existing card debt (debt-management change); coach checks of upcoming charges (targets/projection change); replacing cash-overspending carryover and carrying unassigned TBA over (separate budget-rules change).
