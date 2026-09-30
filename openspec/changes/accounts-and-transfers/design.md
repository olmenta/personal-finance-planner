# Design — Accounts & Transfers

## Context

`Account` exists ([models.py](../../../backend/app/models.py): `cash | bank`, single seeded row) and every transaction already carries `account_id` — but exactly three query sites pick "the user's first account" (`seed.py:31`, `routers/transactions.py:67`, `routers/imports.py:73`; grep beats codegraph here, the references are query strings). `ImportBatch.account_id` already exists. The two-plane YNAB model and all UX decisions were settled in explore (2026-06-12): twin-row transfers, no category on transfers, credit-card option B, opening balance to TBA, matcher suggests-never-applies.

`refund-categorized-inflows` (active change, must land first) centralizes income/spent semantics in `budget_view.income_cents` / `spent_by_category` with summary reusing them — this change adds one more exclusion there instead of re-deriving semantics.

## Goals / Non-Goals

**Goals:**

- Money across bank accounts, cash, and credit cards with honest derived balances.
- Transfers that never leak into the budget plane: no income inflation, no phantom expenses, no double-counted card payments.
- The two-bank import flow works: mark a transfer on bank A's statement; bank B's later import suggests the link instead of duplicating.

**Non-Goals:**

- YNAB credit-card auto-move (move budgeted money to a payment category on card spend) — option B explicitly defers it; additive later.
- Automatic transfer detection from description text ("TRASPASO…") — AI hint candidate, later.
- Tracking (off-budget) accounts, account closing/archiving flows beyond a simple archive flag, multi-currency.

## Decisions

### D1 — Transfers are two linked rows, not one row with a direction

Each side lives in its own account's register with its natural sign; `transfer_pair_id` (a shared UUID, nullable, indexed) links them. Per-account registers, balances, and dedupe need no synthesis. The alternative — one row with `transfer_account_id` — halves the rows but every account-scoped read must synthesize the missing side; rejected.

Twin invariants, enforced in `services/transfers.py` (single write path):

```
amount(out) = -amount(in)        same |amount|
category_id = NULL on both       payee_id = NULL on both
date equal on both               edit amount/date → both rows
delete one → delete both         unlink → clear pair id on both (rows become independent)
```

### D2 — Budget-plane exclusion is one filter in the centralized functions

`income_cents` (positive, uncategorized, **`transfer_pair_id IS NULL`**) and the expense/spent aggregations gain the same filter. Transfer rows have no category so `spent_by_category` is naturally immune; the explicit filter still lands everywhere for intent. All-time `balance_cents` keeps summing everything — twins cancel within the user total, and per-account balances need both sides.

### D3 — Opening balance is a normal uncategorized transaction, source `opening_balance`

YNAB-pure: creating an account with a starting balance writes one confirmed, uncategorized transaction dated that day. Positive → counts as income → To Be Assigned (it's real unbudgeted money). Credit card created with existing debt → negative opening balance → TBA drops (that money is already spent — honest zero-based accounting). No special-casing in aggregates; it's just an uncategorized row. Salted dedupe hash like manual entries.

### D4 — Main-account default keeps entry under 5 seconds

The oldest account is the user's main account (explicit `is_main` flag deferred — creation order suffices for v1). Manual entry pre-selects it; import upload requires an explicit choice only when the user has more than one account. The three "first account" query sites become "resolve requested account_id, default main, 404 on foreign account".

### D5 — Import-side transfers: mark at review, match on the second import

- Review dropdown gains a "Transfers →" group listing the user's *other* accounts. Marking a row stages it as transfer-pending; confirm creates the twin in the target account (confirmed, like the rest of the batch).
- When a later import stages rows into account B, the matcher scans B's existing confirmed transfer twins for `same amount, opposite-side origin, date within ±3 days` and attaches a **suggestion** to the staged row ("looks like the transfer from Banco A on Jun 10"). Accepting links the staged row to the existing twin (replacing the auto-created one) instead of confirming a duplicate; ignoring confirms it as a normal row. Never silent — false positives (two 50€ movements the same week) are a when-not-if.
- `dedupe_hash` stays bank-side only; cross-bank matching is the matcher's job, not the hash's.

### D6 — Credit cards are accounts with option-B semantics

`type = credit`; balance is naturally negative. Card purchases enter categorized in the card account (real spending, budget plane sees it once). The monthly payment is a Bank → Card transfer (budget plane sees it never). Without auto-move there is no enforced "money set aside for the card" — acceptable for the Spanish v1 reality (deferred-debit, pay-in-full cards); users who want it can budget a normal category by hand. The old "credit card" spending category from onboarding stays archivable through existing category CRUD; no data migration.

### D7 — UI surfaces

- **Dialogs**: `SegmentedControl` gains "Transfer" — fields collapse to From/To/Amount/Date/Note (no payee, no category). Editing a transfer opens this mode with both twins implied; editing an imported transfer behaves identically; "Unlink" lives here.
- **TransactionRow**: transfers render `arrow-left-right` icon, "Transfer → <account>", neutral amount color — `--income`/`--expense` stay reserved for money crossing the budget boundary (design-system rule: semantic color is money direction only).
- **Accounts screen**: list with name, type, derived balance; create/rename/archive. Lives under settings or its own nav entry — settle at implementation with the existing shell conventions.

### D8 — Onboarding asks accounts, cards, and (optionally) the opening balance

The interview gains two things, both pure prompt-config edits (per §6.6: prompt + extraction-schema change, bump to `onboarding_v2`, no engine change):

- **Accounts question** (income phase): which banks and credit cards the user has. Extraction fields `accounts.banks: string_list` and `accounts.credit_cards: string_list` — existing leaf types, the schema validator needs nothing new. The proposal gains an `accounts` list (`name`, `type bank | credit`); the review screen gains an Accounts section with the same uncheck/rename/add-new row component; finalize creates accepted accounts with case-insensitive reuse.
- **Opening balance question**, skippable ("How much is in your primary bank account right now? You can skip this."), extraction `accounts.main_balance_cents: int`. Finalize writes the `opening_balance` transaction into the primary (first) bank account when extracted; a skip writes nothing — the balance can be set later from the accounts screen. Why optional: it is the most privacy-sensitive moment of the interview and a refusal must not block activation — but answering means landing on a dashboard with a real To Be Assigned, the strongest start for the activation metric.

Debt-phase mapping (YNAB-faithful within v1 scope): **credit cards → `credit` accounts** (created at zero balance; existing card debt is set later — asking per-card debt would stretch the interview past the 2-minute target); **loans → debt-paydown categories**, because YNAB models loans as off-budget tracking accounts whose monthly payment is a categorized outflow — tracking accounts are a v1 Non-Goal and the budget-plane effect (categorized payment) is identical either way.

## Risks / Trade-offs

- [Matcher false positives annoy users] → suggestion-only, one tap to ignore; tolerance window stays small (±3 days) and requires exact amount.
- [Twin invariants drift if writes bypass the service] → all transfer mutations go through `services/transfers.py`; PATCH /transactions rejects rows with a `transfer_pair_id` (409 `is_transfer`) pointing clients to the transfer contract.
- [Existing single-account users] → seeded account becomes the main account; zero data movement. Onboarding's "first account" question stays deferred (memory: revisit with Auth0 signup).
- [TBA shock when adding a credit card with debt] → it's the honest YNAB-pure number; the UI copy at account creation should say so ("your To Be Assigned will drop by the card's debt").
- [Two active changes editing the same budget-api requirement] → hard ordering: refund change syncs first; this change's deltas are written on top of its final wording.

## Migration Plan

1. Migration: `transfer_pair_id` column + index; `credit` accepted in `Account.type` (string column — no DB enum change).
2. Backend: accounts CRUD → transfers service/routes → aggregate exclusions → import marking/matcher. Each step independently testable.
3. Webapp: account picker → transfer mode in dialogs → review pseudo-group → accounts screen.
4. Rollback: column is additive; UI features gate on data that simply won't exist.

## Open Questions

- None blocking. Accounts screen placement (settings vs nav) settled at implementation.
