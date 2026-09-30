## Why

Two budget rules still diverge from the YNAB method Olmenta commits to, and both break the product's core promise. **To Be Assigned is per-month** (`income − assigned` of that month only), so money left unassigned vanishes at month change. That also breaks the calendar-month decision: a salary arriving on the 27th can't be kept for next month. **Cash overspending carries as a negative rollover** inside the category, so a category that went over once starts every following month in the red and never recovers. Settled with the user on 2026-09-30/10-01: unassigned money carries over, and overspending gets covered in the month it happens. What isn't covered is deducted from next month's To Be Assigned, and the category starts clean.

## What Changes

- **To Be Assigned carries over between months.** It is derived as a running chain: the previous month's To Be Assigned, plus this month's unbudgeted money (uncategorized confirmed activity), minus this month's assignments, minus the previous month's uncovered cash overspending. The goal is still zero (every euro has a job), but a leftover is never lost. A negative (over-assigned) amount carries too. Money that existed before the budget's first month (confirmed activity dated earlier) seeds the chain, so the invariant *money in accounts = To Be Assigned + Σ available* holds from day one.
- **Cash overspending resets the category.** A category that ends a month negative starts the next month with zero rollover. The uncovered amount is deducted from next month's To Be Assigned instead. **BREAKING** for the rollover contract: negative carryover inside a category is removed. Credit overspending isn't handled here; `accounts-and-transfers` defines it (card debt).
- **The rollover chain crosses unopened months.** A month the user never opened counts as zero assignments with its real spending, instead of cutting the chain.
- **Move money between categories**: new `POST /budget/{month}/moves` (`from_category_id`, `to_category_id`, `amount_cents`) atomically lowers the source's assignment and raises the target's, bounded by the source's available. This is the primary way to cover overspending and to re-plan within a month. The source's assignment may go below zero when the money comes from its rollover (YNAB semantics).
- **The view exposes overspending and a cover suggestion**: per category `overspent_cents`, and a `cover_suggestion` (source + amount) chosen from the month's leftover To Be Assigned first, then the categories with the largest available. The view also reports the To Be Assigned breakdown (`carried_in_cents`, `overspent_deducted_cents`).
- **Webapp**:
  - The budget hero explains carry-ins and deductions.
  - Overspent rows get a one-tap "Cover from …" action and a general "Move money" action.
  - After saving a transaction that overspends a category, a non-blocking prompt offers the same cover (entry stays under 5 s).
- **Unchanged**: calendar months (Europe/Madrid) stay the budget period, and the summary API contract doesn't change.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `budget-api`:
  - Budget month view: cumulative To Be Assigned with breakdown, `overspent_cents`, `cover_suggestion`.
  - Rollover: no negative carryover; the chain continues across unopened months.
  - New move-money requirement.
- `budget-assignment`:
  - To-be-assigned hero: new formula and carry-in/deduction copy.
  - Overspent rows: cover action.
  - New move-money interaction.
- `webapp-server-state`:
  - Move-money mutation (optimistic, invalidation).
  - Post-save cover prompt in the transaction dialogs.
- `bff-proxy`: `POST /api/budget/{month}/moves` added to the proxied routes.

## Impact

- **Backend**:
  - `services/budget_view.py`: the To Be Assigned chain, the rollover rule, calendar walking across gaps, overspending and cover suggestion.
  - `routers/budget.py`: the moves endpoint.
  - `schemas.py`: new view fields and the move request/response.
  - No schema migration: assignments are already plain integers. The `amount_cents ≥ 0` check stays on PUT, and only moves may produce a negative assignment.
- **Webapp**: the budget screen hero and rows, a move-money sheet, the cover prompt in `AddTransactionDialog` / `EditTransactionDialog` / import confirm, the BFF route, and `lib/api.ts`.
- **Other changes**: `accounts-and-transfers` rewrites the same `budget-api` rollover requirement ("including negative carryover from cash overspending"). **This change lands first**, and that change's budget-api delta is rebased onto this wording at sync time: credit overspending is added back, and cash overspending resets per this change.
- **Performance**: the view walks months from the budget start to the requested month (already true for rollover). Acceptable at v1 volumes; the materialized monthly snapshot foreseen in project-definition §6.3 is the escape hatch.
