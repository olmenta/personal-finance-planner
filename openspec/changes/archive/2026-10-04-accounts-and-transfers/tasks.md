# Tasks — Accounts & Transfers

> `refund-categorized-inflows` is done and archived (2026-09-30) — the shared income/spent semantics are in place.
> Credit cards follow the YNAB model (design D6, revised 2026-09-30); section 3b replaces the former option B.

## 1. Data layer

- [x] 1.1 `Transaction.transfer_pair_id` (nullable `String(36)`, indexed) in `models.py`; `Account.type` docs/validation accept `credit`; `Account.payment_day` (nullable int 1–31); `Category.payment_account_id` (nullable unique FK); `CategoryGroup.system` (bool, default false); one Alembic migration with downgrade
- [x] 1.2 `opening_balance` added to the transaction source values (schema comment + ingestion-safe)

## 2. Accounts backend

- [x] 2.1 `routers/accounts.py`: `GET /accounts` (derived `balance_cents` via one grouped query), `POST /accounts` (name/type/institution/opening_balance_cents, 409 `account_exists`), `PATCH /accounts/{id}` (rename/institution/archived, 404 `account_not_found`); register in `main.py`
- [x] 2.2 Opening-balance write: confirmed uncategorized salted transaction, `source = "opening_balance"`; on credit accounts it is pre-existing debt (negative, excluded from income/TBA and from payment-category moves)
- [x] 2.5 Credit account creation creates its payment category ("Pago <name>") in the "Tarjetas de crédito" system group (created on first need), same transaction; rename/archive of the account propagates; `payment_day` accepted on POST/PATCH (credit only, 1–31)
- [x] 2.6 `routers/categories.py`: payment categories and system groups reject delete/re-parent with 409 `payment_category_locked`
- [x] 2.3 Main-account resolution helper (oldest active); replace the three "first account" sites (`routers/transactions.py`, `routers/imports.py`, keep `seed.py` semantics) with resolve-requested-or-main + 404 on foreign accounts
- [x] 2.4 `POST /transactions` and `PATCH /transactions/{id}` accept `account_id` (move between registers on PATCH)

## 3. Transfers backend

- [x] 3.1 `services/transfers.py`: create twin pair (invariants per design D1), mirrored edit (amount/date/note), delete both, unlink; all writes transactional
- [x] 3.2 `routers/transfers.py`: `POST /transfers` (422 `same_account`), `PATCH /transfers/{pair_id}`, `DELETE /transfers/{pair_id}`, `POST /transfers/{pair_id}/unlink`; register in `main.py`
- [x] 3.3 `PATCH /transactions/{id}` returns 409 `is_transfer` for paired rows
- [x] 3.4 Aggregate exclusions: `transfer_pair_id IS NULL` filter in `income_cents` and the expense/spent aggregations (budget view + summary already share them after the refund change)

## 3b. Credit cards (YNAB model)

- [x] 3b.1 `budget_view`: split category activity by account type in one grouped query; per (category, card) funded move = `min(card_spending, max(0, assigned + rollover − net non-card activity))`, card refunds move back in full; expose `credit_overspent_cents`
- [x] 3b.2 Payment categories in the view: `kind = "credit_payment"`, `payment_account_id`, spent = transfer inflows into the card, available = assigned + rollover + funded moves − payments; "Tarjetas de crédito" group rendered with the others
- [x] 3b.3 Rollover (on top of budget-rules' reset): split a negative end balance into credit overspending (stays as card debt) and cash overspending (deducted from next month's TBA); payment categories carry forward like any category
- [x] 3b.4 `income_cents` and budget-rules' unbudgeted sum: exclude transfer rows and credit-account opening balances (and keep TBA untouched by funded moves); extend the identity property test with cards and transfers
- [x] 3b.5 `GET /accounts` credit fields: `payment_available_cents`, `uncovered_debt_cents = max(0, −balance − payment_available)`, `payment_day`, `suggested_payment_day` (≥2 transfer inflows within ±2 days of the same day-of-month → earliest day; null otherwise)
- [x] 3b.6 Category suggestion prompt: recognize card interest/fee rows (`INTERESES`, `COMISION`) and propose an "Intereses y comisiones" category when the user has one

## 4. Import-side transfers

- [x] 4.1 Confirm endpoint accepts per-row transfer marking (`transfer_to_account_id` override, mutually exclusive with category); creates the confirmed twin on confirm
- [x] 4.2 Twin matcher at staging: equal amount, twin date ±3 days, same account — attach suggestion to the staged row (batch view exposes it); accept = adopt existing twin and drop the staged row, ignore = confirm normally
- [x] 4.3 Upload accepts `account_id` (multipart field), defaulting to main

## 4b. Onboarding accounts & opening balance

- [x] 4b.1 Prompt config: bump to `onboarding_v2` — accounts question (banks + credit cards; `accounts.banks` / `accounts.credit_cards` string_list fields), skippable primary-balance question (`accounts.main_balance_cents`), debt-phase mapping note (cards → accounts, loans → paydown categories)
- [x] 4b.2 `SetupProposal` gains `accounts: [{name, type bank|credit}]`; prompt's proposal-building section instructs cards-as-accounts, loans-as-categories
- [x] 4b.3 Finalize creates accepted accounts (case-insensitive reuse, cards at zero) and writes the `opening_balance` transaction into the primary bank account when extracted; skip writes nothing (eval fixtures updated for the new fields)
- [x] 4b.4 Review screen: Accounts section (uncheck/rename in place/"Add account" with type picker) feeding the finalize payload

## 5. Backend tests

- [x] 5.1 Accounts: CRUD, duplicate name 409, archive keeps balances, derived balance, opening balance → income/TBA (positive and credit-negative)
- [x] 5.2 Transfers: twin invariants, mirrored edit, delete both, unlink re-enters budget plane, 409 `is_transfer` on PATCH, 422 `same_account`, budget/summary unchanged by transfers
- [x] 5.3 Import: chosen account staging, transfer marking creates twin on confirm, matcher suggests (accept adopts / ignore confirms), no silent links
- [x] 5.4 Credit cards: payment category created/renamed/archived with the card and locked (409); budgeted purchase moves to payment category with TBA unchanged; payment consumes it; card refund moves back; credit overspending reported, not moved, reset at rollover and visible as uncovered debt; covering it in-month funds the card; mixed cash+card category applies cash first; opening debt leaves TBA unchanged; `suggested_payment_day` from two payments, null with one

## 6. BFF + API client

- [x] 6.1 Route handlers: `/api/accounts` (+`[id]`), `/api/transfers` (+`[pairId]`, `unlink`); bff-proxy delta note at sync time
- [x] 6.2 `lib/api.ts`: account + transfer types and client functions; `account_id` on transaction create/update and import upload

## 7. Webapp

- [x] 7.1 Account picker in Add/Edit transaction dialogs (default main, hidden when only one account exists) and in the import upload step
- [x] 7.2 Third "Transfer" segment in Add/Edit dialogs: from/to/amount/date/note; edit mode loads the pair, offers Unlink; mirrored save
- [x] 7.3 `TransactionRow` + transactions list: transfer rendering (`arrow-left-right`, "Transfer → <account>", neutral amount color, no category chip)
- [x] 7.4 Import review: "Transfers →" group in the row dropdown (other active accounts); transfer-marked rows show no category; matcher suggestion chip with accept/ignore
- [x] 7.5 Accounts screen: list with balances (credit as "Debes …" in neutral color, uncovered debt as secondary line), create (type + opening balance; credit adds the optional "¿Qué día te cobran la tarjeta?"), accept chip for `suggested_payment_day`, rename, archive
- [x] 7.6 Budget screen: "Tarjetas de crédito" group (assignable payment rows, spent labelled "Pagado"); credit-overspent amounts in a distinct non-red warning style; first card purchase gets a one-time coach explanation of the move

## 8. Verification

- [x] 8.1 `uv run pytest` green in `backend/`
- [x] 8.2 `volta run npm run build` + lint green in `webapp/`
- [x] 8.3 Manual: create second account + credit card with debt (TBA unchanged, debt shown uncovered), card purchase moves money to "Pago <card>", card payment as transfer empties it, overspend on the card and see it as debt next month, manual transfer — budget totals never move for transfers
  - Deferred (2026-10-04): manual check of the import side — import into chosen account, mark transfer at review, import counterpart statement and accept the match. Covered by `tests/test_import_transfers.py`; walk it through in the app in a later session.
