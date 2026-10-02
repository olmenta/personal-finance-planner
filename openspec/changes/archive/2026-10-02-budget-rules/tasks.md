# Tasks — Budget rules: carry-over and overspending

> Lands **before** `accounts-and-transfers` (design D9). Its budget-api rollover delta gets rebased onto this wording (task 6.2).

## 1. Forward-pass engine (backend)

- [x] 1.1 `budget_view`: find the budget start S (earliest materialized month) and the calendar range S..M; three grouped queries over the range: spent per (month, category) with the existing refund semantics, unbudgeted signed sum per month (confirmed, uncategorized), assignments per (month, category)
- [x] 1.2 `pre_start_net`: signed sum of confirmed transactions dated before S, seeding `carried_in` of S
- [x] 1.3 Forward pass per design D1: rollover = max(0, previous available); overspent(M−1) deducted from TBA(M); unopened months count as zero assignments and are never materialized by the read
- [x] 1.4 `BudgetMonthView` / `BudgetCategoryView` gain `carried_in_cents`, `overspent_deducted_cents`, `overspent_cents`, `cover_suggestion`; `to_be_assigned_cents` becomes the cumulative value; remove the recursive `rollover_by_category`
- [x] 1.5 Cover suggestion (design D7): greedy, largest overspending first, To Be Assigned first, then largest available; sources consumed across suggestions

## 2. Move money (backend)

- [x] 2.1 Schemas: `MoveRequest {from_category_id: str | null, to_category_id: str, amount_cents: int > 0}`; response is the month view
- [x] 2.2 `POST /budget/{month}/moves`: materialize month, validate (404 `category_not_found`, 422 `same_category`, 422 `insufficient_available`, 422 `insufficient_to_be_assigned`), apply both assignment edits in one transaction, mark `edited`; no amounts in logs

## 3. Backend tests

- [x] 3.1 Carry-over: leftover passes to next month; late-month salary left unassigned appears as next month's `carried_in`; negative TBA carries; pre-start history seeds TBA
- [x] 3.2 Overspending: uncovered cash overspending resets rollover to 0 and shows as `overspent_deducted_cents` next month; covered-in-month overspending leaves nothing to deduct
- [x] 3.3 Chain across an unopened month keeps rollover and does not create the month
- [x] 3.4 Identity property: for generated histories (incomes, categorized expenses, refunds, uncategorized outflows, moves, gaps), `TBA + Σ available` equals the signed sum of confirmed transactions up to month end, every month
- [x] 3.5 Moves: cover from a category, cover from TBA, insufficient available/TBA, same category, foreign category, negative assignment from rollover
- [x] 3.6 Cover suggestion: TBA first, largest available otherwise, two overspent categories never share the same euros
- [x] 3.7 Existing budget, summary and import tests still green (summary contract untouched)

## 4. BFF + API client

- [x] 4.1 Route handler `POST /api/budget/[month]/moves`
- [x] 4.2 `lib/api.ts`: new view fields and `moveMoney(month, body)`

## 5. Webapp

- [x] 5.1 Hero reads `to_be_assigned_cents` from the server (no client recompute) and shows the carry-in / deduction line when non-zero
- [x] 5.2 Overspent rows: one-tap cover action from `cover_suggestion`; every row: "Move money" action
- [x] 5.3 Move-money sheet: source picker with availables (+ "Sin asignar"), target, amount prefilled with overspending and capped by the source
- [x] 5.4 TanStack mutation for moves: optimistic update, replace with server view, rollback + retryable error on 422
- [x] 5.5 Cover prompt after saving in Add/Edit dialogs and after import confirm: non-blocking, only when a touched category ends overspent; "Elegir otra" opens the sheet
- [x] 5.6 Row breakdown notes a clean start when the previous month ended overspent

## 6. Verification and hand-off

- [x] 6.1 `uv run pytest` green; `volta run npx tsc --noEmit` + `volta run npm run lint` green in `webapp/` (build only when no dev server is running)
- [x] 6.2 Rebase `accounts-and-transfers` budget-api delta: rollover requirement adds back credit overspending on top of this change's reset rule; income/unbudgeted filters gain transfer and credit-opening exclusions
- [x] 6.3 Manual: leave money unassigned in September → it appears in October; overspend Supermercado with a debit expense → cover prompt → one tap covers it; overspend again without covering → October starts clean and To Be Assigned shows the deduction; open November skipping October → rollover intact
