## Context

Payments (payment schedules) are what make a category's monthly amount computed: the schedule math (`services/schedules.py`) gives normal, catch-up and suggested amounts, `refresh_computed_assignments` keeps open months in line, and the projection reads them. The only writer today is `routers/schedules.py`, used by the schedule editor and the debts API's own schedules.

`coach-conversation-actions` gave the coach the action lifecycle. `coach-budget-setup` (implemented before this change) adds category creation with a follow-up and multi-category budgets. This change adds payments on top of both.

## Goals / Non-Goals

**Goals:**

- Any payment the editor can describe, the coach can propose from a sentence, with a preview that shows what it does to the budget.
- One write path for payments, so the chat, the editor and the MCP server can't drift.
- Undo with the same guarantees as other actions.

**Non-Goals:**

- Income schedules from the chat ("cobro 2.100 el día 28"). They're a separate capability (income-schedules) with their own matching rules; candidate for a later change.
- Debts and their installments: still managed from What you owe.
- The 12-month balance chart of the editor inside the chat. The preview links to the category's payments in Budget instead.

## Decisions

### D1. `services/payment_ops.py`

```text
create_payment(db, user, category_id, body) -> PaymentSchedule
update_payment(db, user, schedule_id, changes) -> PaymentSchedule
delete_payment(db, user, schedule_id) -> None
```

They're extracted from `routers/schedules.py`: validate through `ScheduleIn`, the `managed_by_debt` and `card_plan_exists` guards, the horizon, the merge of a partial update, the pattern-field pruning, then `refresh_computed_assignments`. Errors are raised as `PaymentError(status, code)`, and the router maps them to the same `HTTPException`s. The existing schedules and debt tests guard the behavior.

The MCP server keeps calling the REST API, so it inherits the same path.

### D2. Coach tools and action kinds

| Tool | Kind | Command |
|---|---|---|
| `propose_payment` | `payment` | `{category_id, category_name, body}`, where `body` is the `ScheduleIn` fields |
| `propose_payment_change` | `payment_update` | `{schedule_id, category_id, before: fields, changes}` |
| `propose_payment_removal` | `payment_delete` | `{schedule_id, category_id, before: fields}` |

- **Typed arguments:** the tool's arguments are the editor's fields, typed (`pattern` as a Literal, months as 1–12 ints, months as `YYYY-MM`), so the model fills them from the sentence. The tool descriptions carry the sentence → pattern table ("every month" → monthly; "in February" → annual month 2; "September to June" → some_months [9,10,11,12,1,2,3,4,5,6]; "every 3 months from November" → every_n 3, start_month; "in May 2028" → once; "a year, no date" → no_date; "unos / about / aprox." → estimated).
- **Naming a payment:** a payment is named by its name, or by its category when the category has exactly one. Resolution uses the folded-name resolver over the user's non-debt payments, and an ambiguous name lists the candidates.
- **New categories:** `propose_payment` with an unknown category returns an error telling the model to use `propose_category` with `for` = the payment. `coach-budget-setup`'s follow-up mechanism then proposes the payment after the choice. Its `for` union gains the `payment` command.

### D3. Preview by dry run

The preview reuses `coach_actions.preview`: apply the payment op inside a savepoint, read the budget view and the category's schedule amounts, then roll back. Fields:

- `payment`: `{sentence_before?, sentence_after, next_due_month, estimated}`;
- `categories`: as for other kinds (assigned and available before/after);
- `amounts`: `{normal_before, normal_after, catch_up_before, catch_up_after}` from `schedules.amounts`;
- To be assigned before/after;
- `accounts_unchanged: true`.

The sentence comes from a backend port of the webapp's `describe(schedule)` in `services/payment_text.py`. It's English placeholder copy like the other titles, and the webapp renders it as-is. Changing the copy means changing both describers, and a test pins the same outputs for a fixture set.

### D4. Commit and undo

- **Commit:** calls the payment op in the commit savepoint (month lock, revision check as today). It records `result = {schedule_id, after: fields}`; for a removal, `{before: fields}`.
- **Undo:**
  - `payment`: allowed while the schedule exists with `after` fields; it deletes it.
  - `payment_update`: allowed while it holds `after`; it updates back to `before`.
  - `payment_delete`: allowed while the category exists, isn't archived, and has no payment with identical fields; it recreates the payment and records the new id.

  All go through the payment ops, so assignments refresh.
- **The month lock** covers the current month. Later months refreshed by `refresh_computed_assignments` aren't locked; that's acceptable because the stale check runs on the current month's preview, and later months are recomputed anyway.

### D5. MCP tools

- **`list_payments(category?)`:** each payment in words, with its monthly amount.
- **`add_payment(category, name, amount, pattern, …)`:** writes directly, like the other MCP write tools. When the category doesn't exist, it says to use `find_categories` / `create_category` first.
- **`update_payment(payment, …changes)`** and **`delete_payment(payment)`:** the payment is named by name or category.

The client gets the schedule endpoints. Results translate `invalid_schedule`, `outside_planning_horizon`, `managed_by_debt` and `card_plan_exists` into one-line messages.

### D6. Prompt

A "Setting up payments" section:

- what counts as a payment (a cost with a date) versus day-to-day spending;
- the sentence → pattern table;
- confirm the day only if the user gave one (it orders payments, it's optional);
- estimated for approximate amounts;
- for building a budget: go through fixed bills one at a time, in this order: housing, utilities, insurance, school/children, subscriptions, debts (which point to What you owe). Then the day-to-day amounts with `propose_budget`.

## Risks / Trade-offs

- **[The model picks the wrong pattern, e.g. "September to June" as annual]** → The preview states the payment in words before anything is saved; the evals have one case per pattern; a correction is a new message ("no, el día 5"), which proposes again (payment previews have no Edit).
- **[Two describers, Python and TypeScript, drift]** → A shared fixture test on the backend; the webapp keeps using its own for the editor.
- **[Undo after later months were refreshed]** → Undo runs the same op, which refreshes them back.

## Migration Plan

No schema change: new kinds fit in `coach_actions`. The router refactor keeps behavior, so ship it with this change. Deploy after `coach-budget-setup`. Rollback: revert; stored payment actions become inert.

## Open Questions

- Income schedules from the chat as the next change (`coach-income-setup`)?
