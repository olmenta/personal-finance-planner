## Context

Income schedules (spec: income-schedules) are the planning source for what the user expects to earn. They never touch the budget: To be assigned only counts money that arrives. They feed the month income view (expected versus received, matching by payer then by amount), the projection's coverage, Home's Future status and the late-income proposal. Writes live in `routers/income.py` (CRUD with the partial-update merge and payer resolution through `income.apply_schedule`). Linking an unplanned inflow happens in the webapp as two separate API calls (`IncomeBreakdown`).

`coach-payments-setup` set the pattern this change follows: a shared write path (`payment_ops`), coach action kinds with a dry-run preview, previews and undo reading the current state, and MCP tools over the API.

## Goals / Non-Goals

**Goals:**

- Any income the editor can describe, the coach can propose from a sentence, and the preview shows what it does to the plan (coverage), not to the budget.
- The link from an inflow to its schedule is one atomic backend operation, shared by the webapp and the coach.
- Building a budget from the chat starts with income.

**Non-Goals:**

- Recording money that arrived: that's `propose_transaction` with kind `income`, which already exists.
- Changing the matching rules or the late threshold.
- Probable income (bonuses that depend on targets): still not plannable, per the spec.
- Changing onboarding's income extraction.

## Decisions

### D1. `services/income_ops.py`

```text
create_income(db, user, body) -> IncomeSchedule
update_income(db, user, schedule_id, changes) -> IncomeSchedule
delete_income(db, user, schedule_id) -> None
link_income(db, user, transaction_id, schedule_id) -> None
fields_of(schedule) -> dict   # SCHEDULE_FIELDS + payer name
```

They're extracted from `routers/income.py` (validation through `IncomeScheduleIn`, the merge with pattern pruning, the empty payer that clears it, `apply_schedule`). Errors are raised as `IncomeError(status, code)`, and the router maps them to the same responses. `link_income` implements the spec's three-case rule in one transaction.

`POST /income/link` exposes the link and returns the month view; `IncomeBreakdown`'s "This is…" calls it instead of two writes. The existing income tests guard the CRUD behavior.

### D2. Coach tools and kinds

| Tool | Kind | Command |
|---|---|---|
| `propose_income` | `income` | `{body}` (the income fields plus payer) |
| `propose_income_change` | `income_update` | `{schedule_id, before, changes}` |
| `propose_income_removal` | `income_delete` | `{schedule_id, before}` |
| `propose_income_link` | `income_link` | `{transaction_id, schedule_id, month}` |

- **Typed arguments:** the editor's fields (pattern a Literal without `no_date`), with the sentence → pattern table in the descriptions. "14 pagas" means two incomes: the monthly one, and `some_months` for the extras (usually June and December; ask if unsure).
- **Naming an income:** by its name, or by its payer when that's unique (folded-name resolver).
- **Naming the inflow to link:** the `transaction:<id>` ref from `get_income` (its unplanned list gains refs) or `search_transactions`.

### D3. Preview

The money-action preview machinery reads the budget view, and here the budget doesn't move. Income kinds use their own preview (like `category`):

- **Dry run:** apply the op in a savepoint, read the after values, then roll back.
- **Values before and after:**
  - `month_expected_cents` (`month_income(month).expected_cents`);
  - `year_expected_cents` (Σ `yearly_cents` over the user's schedules);
  - `gap_cents` and `income_known` from `projection.summary(month)`.
- **Text:** `sentence_before` / `sentence_after` (the payment describer plus ", from <payer>"), and `to_be_assigned_unchanged: true`.
- **Link previews:** the occurrence's status and received amount before → after, and whether the inflow is still unplanned after.
- **Revision:** a hash of all of the above, so any change to income, inflows or the plan between the preview and the confirm makes it stale.

`projection.summary` is the heaviest read. It already runs on the Future screen, and a preview runs it twice (before and inside the savepoint). That's acceptable for a confirm-by-tap flow.

### D4. Commit and undo

The same lifecycle, with no month lock beyond the current month's (income doesn't change assignments; the lock just serializes coach actions).

- **Result:**
  - `income` and `income_update`: `{schedule_id, before (current), after}`;
  - `income_delete`: `{before}`;
  - `income_link`: `{transaction_id, schedule_id, txn_payee_before, txn_payee_after, schedule_payee_before, schedule_payee_after}`.
- **Undo:** checks the after state still holds, then applies the inverse through `income_ops`. For a link, it restores both payee ids directly. A payee created by the link stays: payees are cheap, and orphan cleanup already exists for imports.

### D5. MCP tools

- **`list_income`:** each income in words, with its yearly amount.
- **`add_income`**, **`update_income(income, …)`** and **`delete_income(income)`**: write directly, like the other MCP write tools.

Results state the income in words and the new yearly total. Linking stays out of the MCP server (the webapp and the coach cover it).

### D6. Prompt

An "Expected income" section:

- what it is (what you expect to earn, not money that arrived);
- the sentence → pattern table;
- 14 pagas as two incomes;
- "unos" means estimated;
- the payer when the user names who pays;
- when the user says money arrived, record it with `propose_transaction`, not as expected income.

"Building a budget" starts by asking about income (amount, day, pagas) if `get_income` shows none, then fixed bills, then day-to-day.

## Risks / Trade-offs

- **[14 pagas misread as one income of 2 × 1.800 € in two months]** → An eval case; the preview states both incomes in words; the prompt spells out the two-income shape.
- **[The model confuses "I got paid" with expected income]** → A prompt rule plus an eval case ("me ha llegado la nómina" → a transaction, not a schedule).
- **[Coverage preview cost]** → Two summary reads per preview; measured in tests, and acceptable for the frequency.
- **[Link undo leaves a created payee]** → Harmless; it can be reused, and cleanup is out of scope.

## Migration Plan

No schema change. Ship the backend (with the router refactor and `/income/link`) and the webapp together. Rollback: revert; income actions become inert.

## Open Questions

None.
