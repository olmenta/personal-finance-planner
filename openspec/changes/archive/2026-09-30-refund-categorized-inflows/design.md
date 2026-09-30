# Design — Refunds: Categorized Inflows

## Context

Aggregation today: `spent_by_category` sums only negative confirmed rows; `income_cents` sums all positive confirmed rows; `summary.py` duplicates the income query inline (codegraph: `income_cents` has exactly one caller, `build_view` — the dashboard never goes through it). The transaction-create contract already allows income without category (uncategorized inflow → To Be Assigned) and income with category (accepted but mis-aggregated). Both entry UIs currently hide the category control for income — the import review hard-codes "Ready to assign" for positive rows.

## Goals / Non-Goals

**Goals:**

- A categorized inflow behaves as YNAB activity: restores the category's available, never touches income/TBA.
- Budget view and dashboard summary derive income from one function — they can never disagree.
- Refunds work through both real paths: bank import (primary — refunds arrive as positive rows) and manual entry.

**Non-Goals:**

- Transfers between accounts (the `accounts-and-transfers` change; it will add its own exclusion to the same functions).
- A "refund" flag or link to the original transaction (category presence is the discriminator; provenance tracking is not needed for correct math).
- The guided "Register refund" action on the original transaction row (backlog; option 2 — the dialog toggle — was chosen).

## Decisions

### D1 — Category presence is the discriminator; no new field

```
inflow ──┬── no category ──▶ income → To Be Assigned   (salary)
         └── category    ──▶ category activity          (refund)
```

No `is_refund` column, no transaction kind enum change. The data model already expresses the distinction; only the aggregation reads it wrong. This also keeps PATCH semantics trivial (adding/removing the category flips the meaning).

### D2 — Spent is the signed net per category

`spent_by_category` drops the `amount_cents < 0` filter and sums signed amounts, negated. A month with −138,00 € groceries and a +12,50 € refund reports spent 125,50 €. A refund-only month would report negative spent (over-restored) — allowed; `available = assigned + rollover − spent` handles it naturally and YNAB behaves the same.

### D3 — Summary reuses `income_cents` and nets expenses the same way

`summary.py` calls `income_cents` (no inline duplicate) and computes `expense_cents` as the absolute net of categorized activity. Weekly buckets follow the identical rule so the dashboard's week bars match the month totals. Centralizing now means `accounts-and-transfers` later changes ONE place to exclude transfers.

### D4 — Import review: positive rows get the dropdown, defaulting to "Ready to assign"

The hard-coded "Income is never categorized" branch is replaced by the same Select used for negative rows, with "Ready to assign" as the uncategorized default option. The confirm endpoint already accepts per-row category overrides for any row — no API change. The AI suggestion prompt gains one note: a positive row whose cleaned payee matches the user's categorization history may carry the matched category (refund); positive rows with no match stay null.

### D5 — Manual dialogs: collapsed refund toggle (option 2)

Income mode shows an off-by-default "It's a refund" switch; enabling it reveals the standard category select and the submit requires a category while it's on. Expense mode is untouched; plain income entry keeps zero added friction (core UX promise: <5s entry).

## Risks / Trade-offs

- [Users mark salary as refund by mistake] → toggle is collapsed and labeled concretely; the category select only appears after an explicit action.
- [Historical data shifts] → none in practice: both UIs prevented categorized inflows until now, and onboarding income lives in preferences, not transactions.
- [Negative net spent looks odd in UI] → BudgetBar already clamps rendering; the math stays honest.
- [AI suggests categories for genuine income rows] → prompt instructs null unless the payee matches spending history; review keeps the human in the loop either way.

## Migration Plan

1. Backend semantics + summary unification (one commit, regression-tested).
2. UI changes (review dropdown, dialog toggle) — independent, land after.
3. Rollback = revert; no data migration in either direction.

## Open Questions

- None blocking.
