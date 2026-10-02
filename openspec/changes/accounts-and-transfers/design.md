# Design — Accounts & Transfers

## Context

`Account` exists ([models.py](../../../backend/app/models.py): `cash | bank`, single seeded row) and every transaction already carries `account_id` — but exactly three query sites pick "the user's first account" (`seed.py:31`, `routers/transactions.py:67`, `routers/imports.py:73`; grep beats codegraph here, the references are query strings). `ImportBatch.account_id` already exists. The two-plane YNAB model and all UX decisions were settled in explore (2026-06-12): twin-row transfers, no category on transfers, opening balance to TBA, matcher suggests-never-applies. The credit-card decision was revisited on 2026-09-30: option B (no auto-move) is replaced by the full YNAB model (D6), because a budget that doesn't set the card money aside hides whether the next charge can be paid.

`refund-categorized-inflows` (implemented and archived 2026-09-30) centralized income/spent semantics in `budget_view.income_cents` / `spent_by_category` with summary reusing them — this change adds the transfer exclusion and the credit-card funding there instead of re-deriving semantics.

## Goals / Non-Goals

**Goals:**

- Money across bank accounts, cash, and credit cards with honest derived balances.
- Transfers that never leak into the budget plane: no income inflation, no phantom expenses, no double-counted card payments.
- The two-bank import flow works: mark a transfer on bank A's statement; bank B's later import suggests the link instead of duplicating.
- Credit cards the YNAB way: budgeted card spending is set aside automatically for the card payment, overspending on credit shows up as new debt, and each card knows (or learns) its charge day.

**Non-Goals:**

- Automatic transfer detection from description text ("TRASPASO…") — AI hint candidate, later.
- Tracking (off-budget) accounts, account closing/archiving flows beyond a simple archive flag, multi-currency (a card billed in another currency is recorded in euros).
- Paying down pre-existing card debt (payoff plans, interest projections) — deferred to the debt-management change; this change only makes the uncovered debt visible.
- Coach checks of upcoming card charges against the payment category — this change stores `payment_day`; the check belongs to the future targets/projection change.
- Statement-cycle modelling (cut-off date, statement balance vs. current balance) — YNAB ignores it for budgeting and so do we.
- Card-statement file adapters — v1 imports card activity through the existing adapters/custom CSV; bank-issued card export formats come later.

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

YNAB-pure: creating an account with a starting balance writes one confirmed, uncategorized transaction dated that day. Positive on a cash/bank account → counts as income → To Be Assigned (it's real unbudgeted money). On a credit account the opening balance is **pre-existing debt**, as in YNAB: it does not touch To Be Assigned and is not a move into the payment category — it shows up as the card's uncovered debt, which the user pays down by assigning money to the payment category. (The first draft lowered TBA by the debt; rejected on 2026-09-30 — a new user would start with a negative TBA, and debt paydown is its own planned feature.) Salted dedupe hash like manual entries.

### D4 — Main-account default keeps entry under 5 seconds

The oldest account is the user's main account (explicit `is_main` flag deferred — creation order suffices for v1). Manual entry pre-selects it; import upload requires an explicit choice only when the user has more than one account. The three "first account" query sites become "resolve requested account_id, default main, 404 on foreign account".

### D5 — Import-side transfers: mark at review, match on the second import

- Review dropdown gains a "Transfers →" group listing the user's *other* accounts. Marking a row stages it as transfer-pending; confirm creates the twin in the target account (confirmed, like the rest of the batch).
- When a later import stages rows into account B, the matcher scans B's existing confirmed transfer twins for `same amount, opposite-side origin, date within ±3 days` and attaches a **suggestion** to the staged row ("looks like the transfer from Banco A on Jun 10"). Accepting links the staged row to the existing twin (replacing the auto-created one) instead of confirming a duplicate; ignoring confirms it as a normal row. Never silent — false positives (two 50€ movements the same week) are a when-not-if.
- `dedupe_hash` stays bank-side only; cross-bank matching is the matcher's job, not the hash's.

### D6 — Credit cards follow the YNAB model

`type = credit`; balance is naturally negative. The mechanics, per card K:

```
purchase −200 on K, category Supermercado (available 400)
  Supermercado  available 400 → 200     (spending counted at purchase)
  Pago K        available   0 → 200     (funded move, derived)
  TBA           unchanged
payment BBVA → K 200 (transfer)
  K balance    −200 → 0
  Pago K        available 200 → 0       (payment = payment category's "spent")
  Supermercado  unchanged
```

- **Payment category per card.** Created with the account (system group "Tarjetas de crédito", `Category.payment_account_id`), locked against delete/re-parent, follows the account's rename/archive. Assignable like any category: that's how old debt gets paid down.
- **Funded moves are derived, not stored.** Computed in `budget_view` per (category, card, month): `available_before_card = assigned + rollover − net non-card activity`; `funded = min(card_spending, max(0, available_before_card))`; card refunds move back in full. This is a month-level simplification of YNAB's chronological rule (YNAB funds each card transaction in date order); cash spending is applied first, so card spending is what ends up overspent. Deterministic, one grouped query split by account type, no stored ledger to keep in sync with edits/deletes/imports.
- **Credit overspending becomes debt.** The unfunded part is `credit_overspent_cents`; it is added back at rollover (the category starts the next month without it) and stays as uncovered card debt: `uncovered = max(0, −balance − payment_available)`. Cash overspending follows `budget-rules` (reset + deducted from next month's TBA); only the credit part is kept out of that deduction.
- **Payments.** Transfer inflows into K are the payment category's spending. Paying more than the payment category holds makes it negative — ordinary cash overspending, visible in red.
- **Interest and fees.** Nothing special: a card fee or interest charge is a categorized outflow on K (e.g. "Intereses y comisiones"). With no money in that category it is credit overspending, which is exactly the right signal (debt grew). Bank fees on a checking account are ordinary expenses. Category suggestions should recognize `INTERESES` / `COMISION` rows.
- **Onboarding's old "Tarjeta de crédito" spending category** stays archivable through existing category CRUD; v2 of the prompt no longer proposes it (cards become accounts with their own payment category).

### D7 — UI surfaces

- **Dialogs**: `SegmentedControl` gains "Transfer" — fields collapse to From/To/Amount/Date/Note (no payee, no category). Editing a transfer opens this mode with both twins implied; editing an imported transfer behaves identically; "Unlink" lives here.
- **TransactionRow**: transfers render `arrow-left-right` icon, "Transfer → <account>", neutral amount color — `--income`/`--expense` stay reserved for money crossing the budget boundary (design-system rule: semantic color is money direction only).
- **Accounts screen**: list with name, type, derived balance; create/rename/archive. Lives under settings or its own nav entry — settle at implementation with the existing shell conventions. Credit balances read as an amount owed ("Debes 200,00 €") in neutral color, never as a red negative; a card whose uncovered debt is > 0 shows it as a secondary line ("120,00 € sin cubrir"). The create form for credit accounts asks the optional payment day ("¿Qué día te cobran la tarjeta?", skippable) and shows an accept chip when a `suggested_payment_day` exists.
- **Budget screen**: the "Tarjetas de crédito" group renders like any group; payment rows are assignable, their spent column reads "Pagado" and the available is what's set aside for the next charge. Categories with credit overspending show the amount in a distinct (non-red) warning style — it's debt, not a cash hole.

### D8 — Onboarding asks accounts, cards, and (optionally) the opening balance

The interview gains two things, both pure prompt-config edits (per §6.6: prompt + extraction-schema change, bump to `onboarding_v2`, no engine change):

- **Accounts question** (income phase): which banks and credit cards the user has. Extraction fields `accounts.banks: string_list` and `accounts.credit_cards: string_list` — existing leaf types, the schema validator needs nothing new. The proposal gains an `accounts` list (`name`, `type bank | credit`); the review screen gains an Accounts section with the same uncheck/rename/add-new row component; finalize creates accepted accounts with case-insensitive reuse.
- **Opening balance question**, skippable ("How much is in your primary bank account right now? You can skip this."), extraction `accounts.main_balance_cents: int`. Finalize writes the `opening_balance` transaction into the primary (first) bank account when extracted; a skip writes nothing — the balance can be set later from the accounts screen. Why optional: it is the most privacy-sensitive moment of the interview and a refusal must not block activation — but answering means landing on a dashboard with a real To Be Assigned, the strongest start for the activation metric.

Debt-phase mapping (YNAB-faithful within v1 scope): **credit cards → `credit` accounts** (created at zero balance with their payment category; existing card debt is set later — asking per-card debt would stretch the interview past the 2-minute target); **loans → debt-paydown categories**, because YNAB models loans as off-budget tracking accounts whose monthly payment is a categorized outflow — tracking accounts are a v1 Non-Goal and the budget-plane effect (categorized payment) is identical either way.

### D9 — Payment day: asked, else inferred from statements

`Account.payment_day` (1–31, credit only) is optional at creation. When it is unset, `GET /accounts` computes `suggested_payment_day` from the card's confirmed transfer inflows: at least two payments whose day-of-month falls within ±2 days of each other → suggest the earliest day of that cluster. Suggest-never-apply, same rule as the twin matcher. Computed at read time (a handful of rows per card) — no background job. Onboarding doesn't ask for it: the interview stays under 2 minutes and most users won't know it offhand.

## Risks / Trade-offs

- [Matcher false positives annoy users] → suggestion-only, one tap to ignore; tolerance window stays small (±3 days) and requires exact amount.
- [Twin invariants drift if writes bypass the service] → all transfer mutations go through `services/transfers.py`; PATCH /transactions rejects rows with a `transfer_pair_id` (409 `is_transfer`) pointing clients to the transfer contract.
- [Existing single-account users] → seeded account becomes the main account; zero data movement. Onboarding's "first account" question stays deferred (memory: revisit with Auth0 signup).
- [Month-level funding differs from YNAB's chronological funding] → only when a category mixes cash and card spending and ends overspent; our rule (cash first) is deterministic and documented. Revisit if users report surprises.
- [Users don't understand money "moving" to the payment category] → the coach explains it the first time a card purchase lands ("apartamos 200 € para pagar la Visa"); the budget row makes the destination visible.
- [Derived moves cost on every budget read] → one extra grouped query split by account type; if needed, the materialized monthly snapshot already foreseen in project-definition §6.3 covers it.
- [Card exports with inverted signs] → rows imported into a credit account must follow the bank-account convention (purchases negative); adapter tests cover it when card formats are added.
- [Two active changes editing the same budget-api requirement] → hard ordering: refund change syncs first; this change's deltas are written on top of its final wording.

## Migration Plan

1. Migration: `transfer_pair_id` column + index; `credit` accepted in `Account.type` (string column — no DB enum change); `Account.payment_day`, `Category.payment_account_id` (unique FK), `CategoryGroup.system`.
2. Backend: accounts CRUD (+ payment category creation) → transfers service/routes → aggregate exclusions → credit-card funding in `budget_view` → payment-day inference → import marking/matcher. Each step independently testable.
3. Webapp: account picker → transfer mode in dialogs → review pseudo-group → accounts screen.
4. Rollback: column is additive; UI features gate on data that simply won't exist.

## Open Questions

- None blocking. Accounts screen placement (settings vs nav) settled at implementation.
