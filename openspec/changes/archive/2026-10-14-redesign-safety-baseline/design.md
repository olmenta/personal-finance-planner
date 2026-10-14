## Context

`ui-experiments/redesign.md` (version 2, October 14, 2026) reviewed the code at `eadb70f` plus the working tree. Its central decision is to **keep the financial engine** (budget chain, rollover, card funding, catch-up, income matching, projection, debts) and build the conversational Home on it, with narrow corrections and an action-safety layer. It reproduced ten behaviors with characterization tests (F01–F10) and found spec drift (OS01–OS06). Its delivery sequence starts with "baseline and focused safety fixes", which is this change.

**Code involved:**

- `services/projection.py`: `upcoming` initial state at the line `tba = float(max(0, overview.to_be_assigned_cents))`, and the float `_allocate`.
- `services/overview.py`: `build_overview` paid aggregation and `match_payments`.
- `services/coach.py` and `routers/coach.py`: accept recomputes and applies the current suggestion, and accepts any `from_category_id`. This is the active `coach-proposals` change, still uncommitted.
- `routers/budget.py`: the move endpoint holds the `same_category` and availability guards inline.
- `schemas.py`: `OnceSchedule.once_month` and the personal debt `due_month` have no range check, while catch-up stops at 120 months.

## Goals / Non-Goals

**Goals:**

- No hidden deficit in the forecast; no shortage rounded away.
- A coach action applies exactly what the user reviewed, once, with valid sources.
- Truthful "Already paid" and card settlement totals, keeping the money identity.
- Explicit horizon instead of a silent zero.
- Base specs that no longer contradict the code.
- Recorded policies for F07–F09.

**Non-Goals:**

- Any change to budget math, rollover, card funding moves, the catch-up formula, income matching, debts, or import deduplication.
- The new Home, navigation, chat, undo, locales and notifications. These are later changes (see the roadmap in the proposal).
- Daily liquidity modeling.

## Decisions

### D1. Projection initial state (F01)

The projected end of the selected month `M` is:

```text
tba_end(M) = TBA(M)                      # signed; negative = over-assigned
           − overspent_cents(M)          # cash overspending, deducted next month
           − Σ short_cents(to_pay of M)  # unpaid, uncovered: becomes overspending
           + still_expected_income(M)    # pending + late occurrences
```

There's no double count:

- **`TBA(M)`** already reflects money assigned to cover pending payments (`covered`).
- **`short_cents`** is only the part no category holds.
- **`overspent_cents`** is a past cash deficit that the budget chain would deduct from the next month's To Be Assigned anyway.

Later months keep the existing allocator and the existing deduction of simulated uncovered payments. Existing healthy fixtures, where To Be Assigned ≥ 0, nothing overspent and nothing short, are unchanged.

*Alternative considered:* subtracting every warning indicator, including negative category availables and card debt. Rejected because it double-counts. Credit overspending is debt with its own plan and doesn't reduce the cash projection.

### D2. Whole-cent pro-rata (F06)

`_allocate` works in integer cents:

1. Compute exact shares.
2. Give each item `floor(share)`.
3. Distribute the leftover cents one by one to the largest fractional remainders, with ties broken by the existing iteration order (priority, then category order).

Coverage uses these integers. `money` and the carried To Be Assigned stay integers through the loop. Float amounts from `catch_up` and `category_normal` are rounded up to whole cents when wanted, matching `amounts()`, so the allocator never invents money.

### D3. Coach acceptance bound to a revision (F02)

- **Revision:** `revision = sha256("{fingerprint}|{category_id}|{current}|{suggested}|{diff}|{sorted source ids}")[:16]`, computed in `services/coach.py` and returned on every raise and lower proposal.
- **Accept** requires `revision` in the body:
  - same revision → apply, and store `state = accepted` with `revision`;
  - different revision → 409 `proposal_changed` with the current proposal (`CoachProposalOut`);
  - already accepted with the same revision → 200, no-op.
- **Migration:** adds a nullable `revision` column to `coach_proposal_states`. The webapp sends the revision it rendered and, on 409, replaces the card with the returned proposal so the user sees the new amount before accepting again.

*Alternative considered:* a full action journal with idempotency keys. Deferred to `coach-conversation-actions`, where grouped commands and undo need it. The revision covers this change's single-category actions.

### D4. One move validator (F03)

`routers/budget.py`'s inline checks move into `services/budget_moves.py::validate_source(view, target_id, source_id, amount)`:

- `same_category` → 422;
- unknown or foreign source → 404;
- insufficient available → 422 `insufficient_available` for budget moves and 409 `not_enough_in_source` for the coach (the error codes stay per endpoint).

The coach adds its eligibility rule: a flexible, non-archived category, not a card payment, scheduled or savings category. Both callers mutate only after validation, inside the request transaction.

### D5. Paid versus settlements (F04, F05)

In `build_overview`:

- **Partial payment:** for an unpaid occurrence with `allocated > 0` that isn't estimated, add a paid item with `amount_cents = allocated` and `partial = true`. The pending remainder is unchanged.
- **Card payment categories:** their activity (transfers into the card) and their card plan occurrences go to a new `card_payments` section (`total_cents`, `items`) instead of `paid`.

Spending on the card was already counted in `paid` through each category at purchase time. The identity doesn't involve `paid`, so it's untouched. `ThisMonth` shows "Card payments" as its own line under "Already paid".

### D6. Planning horizon (F10)

The schema validators for `OnceSchedule.once_month` and the personal debt's `due_month` compare against `sched.month_index(current_month) + MAX_HORIZON - 1`. Beyond it they return 422 `outside_planning_horizon`; the routers map validator failures to that code. Existing stored schedules beyond the horizon, if any, aren't touched. The read side already ignores them, and the editor shows the limit.

### D7. Empty feed (OS05)

`CoachFeed` empty copy: "No suggestions right now." No solvency claim. Financial status comes from the summary, not from the absence of proposals.

### D8. Policies recorded for sign-off (F07–F09), implemented later

- **F07, unpaid past obligations.** Proposed policy: an unpaid dated occurrence from a past month stays listed as overdue in the current month's "to pay" until the user confirms it as paid elsewhere, rescheduled or canceled. Resolution is stored minimally, per schedule and month. It's implemented in `future-coaching`.
- **F08, partial income.** Proposed policy: when a matched inflow differs from the expected amount, the user chooses between "that's the final amount" (today's behavior, kept) and "the rest is still coming", which keeps the remainder as still-expected for that month without touching real To Be Assigned. It's implemented in `future-coaching`.
- **F09, ambiguous duplicates.** Proposed policy: an exact bank reference or running balance stays an automatic skip. Identical rows without either discriminator are staged as "possible duplicate" with a "keep both" decision, and re-import protection stays. It goes in a dedicated import change.

### D9. Test hygiene

`test_request_values_never_exported` asserts structured span attributes (request body fields absent) instead of `"4520" not in str(export)`. The characterization cases F01–F06 and F10 become desired-behavior tests, never golden copies of the old flaws.

## Risks / Trade-offs

- **[F01 makes some forecasts look worse overnight]** → That's the point: the shortage was real. Users with a negative To Be Assigned will now see later months short. The existing "short" copy explains it, and the upcoming Home change adds "Needs organizing".
- **[Integer allocation changes a few cents in realistic fixtures]** → Allowed only with a documented reason. Prototype fixtures are re-checked, and any diff is explained in the test.
- **[409 `proposal_changed` adds a step]** → It only happens when the numbers changed, which is exactly when the user should look again.
- **[Depends on the uncommitted coach-proposals change]** → It ships in the same PR, or after coach-proposals is merged and archived. Sync order: coach-proposals first, then this change.
- **[Existing out-of-horizon schedules]** → Unlikely, since nobody plans more than 10 years out. They're left as is, and only new writes are validated.

## Migration Plan

1. The Alembic revision adds a nullable `coach_proposal_states.revision`.
2. Deploy the backend and webapp together. Old webapp tabs that accept without a revision get a 422 and reload the proposal.
3. Rollback: drop the column and restore the previous accept behavior. No financial data changes.

## Open Questions

- Sign-off of the F07–F09 policies (D8) by the product owner before their changes start.
