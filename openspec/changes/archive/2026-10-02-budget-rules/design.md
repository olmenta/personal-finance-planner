## Context

[budget_view.py](../../../backend/app/services/budget_view.py) derives everything at read time:

- `to_be_assigned = income(M) − Σ assigned(M)`, month-local.
- `rollover(M)` recursively walks `available` back through *materialized* months, including negative carryover, and stops at the first month the user never opened.

Nothing is stored except `BudgetAssignment.assigned_cents`. The refund change (archived 2026-09-30) centralized `income_filters` / `spent_by_category`, and this change builds on them.

Product decisions this implements (conversation of 2026-09-30/10-01, recorded in the user's product-decision notes):

- To Be Assigned aims at zero but its leftover carries over.
- Overspending is covered in the month it happens; what isn't gets deducted from next month's To Be Assigned and the category starts clean (YNAB).
- Calendar months stay; late-month salaries work *because* To Be Assigned carries.
- Credit overspending is `accounts-and-transfers`' job.

## Goals / Non-Goals

**Goals:**

- One invariant, true in every month: **Σ confirmed activity up to the end of M = To Be Assigned(M) + Σ available(M)** (before `accounts-and-transfers`; that change refines it with transfers and card debt).
- No money disappears at month change, and no category is punished forever by one bad month.
- Covering overspending takes one tap, with a sensible source already chosen.

**Non-Goals:**

- Credit overspending and payment categories (`accounts-and-transfers`).
- Protecting categories that hold money for upcoming scheduled payments when suggesting a cover source. That needs payment schedules, which belong to the future targets/annual-plan change. Until then, suggestions rank by available only.
- Move history or audit ledger; coach suggestions for chronically overspent categories (annual-plan change).
- Configurable budget periods (calendar months confirmed again on 2026-10-01).

## Decisions

### D1: To Be Assigned is a derived chain, not a stored balance

```
TBA(S−1)  := pre_start_net                       (see D3)
TBA(M)    := TBA(M−1) + unbudgeted(M) − Σ assigned(M) − overspent(M−1)
available(c, M) := assigned(c, M) + rollover(c, M) − spent(c, M)
rollover(c, M)  := max(0, available(c, M−1))
overspent(M)    := Σ_c max(0, −available(c, M))
```

The view reports `carried_in_cents = TBA(M−1)` and `overspent_deducted_cents = overspent(M−1)` so the hero can explain the number.

*Alternative:* store a per-month To Be Assigned snapshot and update it on every write. Rejected. Every transaction edit, import and delete would have to patch all later months; derived values stay correct by construction, and the codebase already derives everything (`models.py` header).

### D2: One forward pass over calendar months, with no gaps

S is the earliest materialized `BudgetMonth`. The view walks every calendar month S..M:

- Materialized months use their assignments.
- Unopened months count as zero assignments. They are never materialized as a side effect, which would create draft assignments the user never saw.

The data comes from three grouped queries over the range: spent per (month, category), unbudgeted per month, and assignments per (month, category). The pass then runs in Python. This replaces the recursive `rollover_by_category`, which issued queries per month and cut the chain at gaps (money spent in an unopened month silently disappeared from rollover).

### D3: Money from before the budget's first month seeds To Be Assigned

`pre_start_net` is the signed sum of all confirmed transactions dated before S. Without it, importing June's statement and starting the budget in July leaves June's net balance in the accounts but in neither To Be Assigned nor any category, and the invariant breaks.

*Alternative:* ignore pre-start history. Rejected; the dashboard balance and the budget would disagree from day one. If the user later opens an earlier month, S moves back and everything re-derives consistently.

### D4: "Unbudgeted" is signed uncategorized activity; `income_cents` stays positive-only

`unbudgeted(M)` is the signed sum of confirmed rows without a category in M. Positive rows are income. A negative uncategorized row (possible when an import row is confirmed with its suggestion cleared) is money that left without a job, so it lowers To Be Assigned.

`income_cents` keeps its display meaning (positive uncategorized only), so the refund semantics and the summary API are untouched. After `accounts-and-transfers` lands, both exclude transfer rows and credit-account opening balances; that change owns those filters.

### D5: Overspending resets the category and is deducted next month

A negative end-of-month available becomes zero rollover, and its magnitude is `overspent(M)`, deducted from `TBA(M+1)`. The *current* month still shows the category negative with `overspent_cents` and a cover suggestion. That is the moment to act, and the deduction is only the fallback.

*Alternative:* deduct from the current month's To Be Assigned immediately. Rejected; it hides the overspending the user should see and decide on, and YNAB deliberately defers it to month end.

### D6: A move is two assignment edits in one transaction

`POST /budget/{month}/moves {from_category_id | null, to_category_id, amount_cents > 0}` works as follows:

- **Effect:** lowers `from`'s assignment and raises `to`'s, atomically. Both are marked `edited`.
- **`from = null`:** the money comes from To Be Assigned (bounded by `TBA(M) > 0`).
- **Bound:** the source's current available, so you can't move money that isn't there. The source's assignment may therefore go negative when the money comes from its rollover, which is YNAB's behaviour.
- **PUT:** keeps `amount_cents ≥ 0`, because a user typing a negative assignment is a mistake; only moves produce negatives.
- **Errors:**
  - 422 `same_category`;
  - 422 `insufficient_available` (with the available in the detail, no amounts in logs);
  - 404 `category_not_found`;
  - 422 `insufficient_to_be_assigned` when the source is To Be Assigned.
- **Response:** the recomputed month view.

*Alternative:* a `BudgetMove` ledger table. Rejected for v1; nothing needs move history yet, and assignments already express the result.

### D7: The server chooses the cover suggestion

For each overspent category, largest overspending first, the view picks one source greedily:

1. The month's positive To Be Assigned.
2. Otherwise, the non-overspent category with the largest available.

The suggested amount is `min(overspent, source_available)`. Sources are consumed as suggestions are assigned, so two suggestions never promise the same euros.

Server-side, so the budget screen, the entry-dialog prompt and (later) the coach agree. The targets change will add "skip categories reserved for an upcoming payment" here.

### D8: The cover prompt never blocks entry

After a transaction create/edit or an import confirm, the webapp refetches the month (as today). If a category that the write touched now has `overspent_cents > 0`, it shows a non-blocking prompt: "Supermercado se pasó 50,00 €. Cubrir desde Restaurantes". One tap posts the move, and "Elegir otra" opens the move sheet. The save itself completes first, so the <5 s entry promise holds.

### D9: Ordering with `accounts-and-transfers`

Both changes modify the `budget-api` rollover requirement. **This change lands first.** When `accounts-and-transfers` is implemented, its rollover delta is rebased:

- Credit overspending is added back and doesn't carry.
- Cash overspending resets per D5, which replaces its current "including negative carryover" text.
- The unbudgeted/income filters gain the transfer and credit-opening exclusions.

## Risks / Trade-offs

- [A carried negative To Be Assigned surprises users ("why do I start October at −120 €?")] → the hero always shows the breakdown ("−85 € del gasto de más de septiembre"), and the coach explains it the first time.
- [The month walk grows with budget age] → three grouped queries regardless of length; the Python pass is O(months × categories), trivial at v1 scale. If needed, use the snapshot from project-definition §6.3.
- [The greedy suggestion drains a category the user wanted to keep] → it is only a suggestion; "Elegir otra" is one tap away, and the targets change will exclude reserved categories.
- [Negative uncategorized outflows lower To Be Assigned unexpectedly] → they're rare (manual expenses require a category); the import review already nudges categorization.
- [Existing dev data changes numbers] → negative carryovers in the dev database become resets plus To Be Assigned deductions. There is no production data yet.

## Migration Plan

1. No schema migration: `assigned_cents` is already an unconstrained integer, and PUT keeps its own `≥ 0` validation.
2. Backend: forward-pass engine (D1–D5) → cover suggestion (D7) → moves endpoint (D6). The old recursive helpers are removed once the tests pass on the new pass.
3. Webapp: BFF route and API client → hero breakdown → overspent row actions and move sheet → post-save prompt.
4. Rollback: revert the code. Nothing persisted changes shape, so rolling back only affects any negative assignments that moves wrote. Those remain valid integers, and the old math reads them as-is.

## Open Questions

- None blocking. Hero copy details are settled at implementation in the existing voice (second person, verbs that say what happens).
