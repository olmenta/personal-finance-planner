# Tasks — Accounts & Transfers

> Depends on `refund-categorized-inflows` being implemented and synced first (shared income/spent semantics).

## 1. Data layer

- [ ] 1.1 `Transaction.transfer_pair_id` (nullable `String(36)`, indexed) in `models.py`; `Account.type` docs/validation accept `credit`; Alembic migration with downgrade
- [ ] 1.2 `opening_balance` added to the transaction source values (schema comment + ingestion-safe)

## 2. Accounts backend

- [ ] 2.1 `routers/accounts.py`: `GET /accounts` (derived `balance_cents` via one grouped query), `POST /accounts` (name/type/institution/opening_balance_cents, 409 `account_exists`), `PATCH /accounts/{id}` (rename/institution/archived, 404 `account_not_found`); register in `main.py`
- [ ] 2.2 Opening-balance write: confirmed uncategorized salted transaction, `source = "opening_balance"`, negative allowed for credit
- [ ] 2.3 Main-account resolution helper (oldest active); replace the three "first account" sites (`routers/transactions.py`, `routers/imports.py`, keep `seed.py` semantics) with resolve-requested-or-main + 404 on foreign accounts
- [ ] 2.4 `POST /transactions` and `PATCH /transactions/{id}` accept `account_id` (move between registers on PATCH)

## 3. Transfers backend

- [ ] 3.1 `services/transfers.py`: create twin pair (invariants per design D1), mirrored edit (amount/date/note), delete both, unlink; all writes transactional
- [ ] 3.2 `routers/transfers.py`: `POST /transfers` (422 `same_account`), `PATCH /transfers/{pair_id}`, `DELETE /transfers/{pair_id}`, `POST /transfers/{pair_id}/unlink`; register in `main.py`
- [ ] 3.3 `PATCH /transactions/{id}` returns 409 `is_transfer` for paired rows
- [ ] 3.4 Aggregate exclusions: `transfer_pair_id IS NULL` filter in `income_cents` and the expense/spent aggregations (budget view + summary already share them after the refund change)

## 4. Import-side transfers

- [ ] 4.1 Confirm endpoint accepts per-row transfer marking (`transfer_to_account_id` override, mutually exclusive with category); creates the confirmed twin on confirm
- [ ] 4.2 Twin matcher at staging: equal amount, twin date ±3 days, same account — attach suggestion to the staged row (batch view exposes it); accept = adopt existing twin and drop the staged row, ignore = confirm normally
- [ ] 4.3 Upload accepts `account_id` (multipart field), defaulting to main

## 4b. Onboarding accounts & opening balance

- [ ] 4b.1 Prompt config: bump to `onboarding_v2` — accounts question (banks + credit cards; `accounts.banks` / `accounts.credit_cards` string_list fields), skippable primary-balance question (`accounts.main_balance_cents`), debt-phase mapping note (cards → accounts, loans → paydown categories)
- [ ] 4b.2 `SetupProposal` gains `accounts: [{name, type bank|credit}]`; prompt's proposal-building section instructs cards-as-accounts, loans-as-categories
- [ ] 4b.3 Finalize creates accepted accounts (case-insensitive reuse, cards at zero) and writes the `opening_balance` transaction into the primary bank account when extracted; skip writes nothing (eval fixtures updated for the new fields)
- [ ] 4b.4 Review screen: Accounts section (uncheck/rename in place/"Add account" with type picker) feeding the finalize payload

## 5. Backend tests

- [ ] 5.1 Accounts: CRUD, duplicate name 409, archive keeps balances, derived balance, opening balance → income/TBA (positive and credit-negative)
- [ ] 5.2 Transfers: twin invariants, mirrored edit, delete both, unlink re-enters budget plane, 409 `is_transfer` on PATCH, 422 `same_account`, budget/summary unchanged by transfers
- [ ] 5.3 Import: chosen account staging, transfer marking creates twin on confirm, matcher suggests (accept adopts / ignore confirms), no silent links

## 6. BFF + API client

- [ ] 6.1 Route handlers: `/api/accounts` (+`[id]`), `/api/transfers` (+`[pairId]`, `unlink`); bff-proxy delta note at sync time
- [ ] 6.2 `lib/api.ts`: account + transfer types and client functions; `account_id` on transaction create/update and import upload

## 7. Webapp

- [ ] 7.1 Account picker in Add/Edit transaction dialogs (default main, hidden when only one account exists) and in the import upload step
- [ ] 7.2 Third "Transfer" segment in Add/Edit dialogs: from/to/amount/date/note; edit mode loads the pair, offers Unlink; mirrored save
- [ ] 7.3 `TransactionRow` + transactions list: transfer rendering (`arrow-left-right`, "Transfer → <account>", neutral amount color, no category chip)
- [ ] 7.4 Import review: "Transfers →" group in the row dropdown (other active accounts); transfer-marked rows show no category; matcher suggestion chip with accept/ignore
- [ ] 7.5 Accounts screen: list with balances, create (type + opening balance with TBA-impact copy), rename, archive

## 8. Verification

- [ ] 8.1 `uv run pytest` green in `backend/`
- [ ] 8.2 `volta run npm run build` + lint green in `webapp/`
- [ ] 8.3 Manual: create second account + credit card with debt (TBA drops), manual transfer, card payment as transfer, import into chosen account, mark transfer at review, import counterpart statement and accept the match — budget totals never move
