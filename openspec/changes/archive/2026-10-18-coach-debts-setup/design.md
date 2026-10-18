## Context

`debt-paydown` built debts as plans over payment schedules:

- a card plan is a schedule on the card's payment category;
- a loan is a schedule with a count in a "Deudas" category;
- a personal debt with a date is a `once` schedule.

`services/debts.py` holds the rules: `create_debt`, `update_debt`, `delete_debt`, `convert_to_loan` and `settings().extra_monthly_cents`, plus the simulation (`build_debts_view`: order, end months, debt-free month, cushion). `routers/debts.py` validates the Pydantic bodies (`DebtIn`, `DebtUpdate`, `DebtExtraIn`, `ConvertToLoanIn`) and maps `DebtError`.

The coach changes so far (budget, payments, income) set the pattern: a shared operation, action kinds with dry-run previews, previews and undo reading the current state, MCP tools over the API, a prompt section and eval cases.

## Goals / Non-Goals

**Goals:**

- Everything the plan editor can do, the coach can propose from conversation, one debt at a time, with "I don't know" accepted for the optional facts.
- The extra's effect is visible before saving (a what-if that is just an unconfirmed preview).
- Calm, jargon-free explanations of the order and the cushion.

**Non-Goals:**

- New debt kinds, a different order, or new simulation rules.
- Recording debt payments: those are transactions or transfers, as today.
- Changing the plan editor; it stays as the visual path.
- Undoing a conversion (it archives an account and moves money).

## Decisions

### D1. `services/debt_ops.py`

```text
create(db, user, body: dict) -> Debt            # validates DebtIn
update(db, user, debt_id, changes: dict) -> Debt # validates DebtUpdate
delete(db, user, debt_id) -> None
set_extra(db, user, cents) -> int               # returns the previous extra
convert(db, user, account_id, body: dict) -> Debt
fields_of(db, debt) -> dict                     # recreatable fields (for undo)
```

Validation moves from the router into these functions (`_code(exc)` → `invalid_debt` / `outside_planning_horizon`), raising `DebtError(status, code)`. The router keeps its responses. `accounts.py`'s convert-to-loan route calls `debt_ops.convert`. `fields_of` returns what `POST /debts` needs to recreate the debt:

- card: `account_id`, the current plan amount (not the target month, since a target recomputes), minimum and rate;
- loan: name, installment, the installments left as of now, next month, day and rate;
- personal: name, the owed amount as of now, lender, due month and rate.

### D2. Coach tools and kinds

| Tool | Kind | Command |
|---|---|---|
| `propose_debt` | `debt` | `{body}` (DebtIn in cents) |
| `propose_debt_change` | `debt_update` | `{debt_id, changes}` |
| `propose_debt_removal` | `debt_delete` | `{debt_id}` |
| `propose_debt_extra` | `debt_extra` | `{extra_cents}` |
| `propose_debt_conversion` | `debt_convert` | `{account_id, body}` |

- **Tool arguments are plain words:** euros, `rate_percent` with `per`, months as YYYY-MM.
- **Name resolution:** a card account resolves through `resolve_account` (credit type), and a debt by its name, its card account's name or its lender.
- **Interview rules:** the tool descriptions state them (ask the minimum and the rate, accept "no lo sé"; card plan by month or by date, never both).

### D3. Preview

A debt preview combines the debts view and the budget view, read before and inside the savepoint:

- `debts`: `total_owed`, `debt_free_month`, `extra_monthly`, `extra_target` (name), and for the touched debt `name`, `kind`, `position`, `end_month`, `required_monthly`, `below_minimum`, `monthly_interest`;
- `plan_text`: the debt's plan in words, before → after (e.g. "200,00 € a month · done in January 2027"; "290,17 € × 34 from November 2026, day 2"; "670,00 €, no date");
- `categories`: the debt's category assigned and available before → after, plus To be assigned (when a schedule changes);
- `cushion`: `{suggested, saved, applies}` for `debt_extra` when `saved < suggested` and the extra is above zero;
- the revision covers all of it.

A card's owed amount depends on its account balance and the payment category's available, so any spending on the card between the preview and the confirm makes the preview stale, as intended.

### D4. Commit and undo

- **Commit:** calls `debt_ops` in the commit savepoint. The result records `debt_id` plus `before` and `after` from `fields_of` (and `extra_before` for `debt_extra`).
- **Undo checks:**
  - `debt` and `debt_update`: the debt still exists and its plan fields equal `after`;
  - `debt_delete`: no debt exists for that category or account;
  - `debt_extra`: the extra still equals the new value.
- **Undo applies the inverse:**
  - `debt` → delete;
  - `debt_update` → update with the `before` plan fields;
  - `debt_delete` → create from `before`;
  - `debt_extra` → set the previous value.
- `debt_convert` reports `can_undo: false`.

### D5. From "What you owe" to Home

"Talk it through with your coach" links to `/?draft=Quiero%20ordenar%20mis%20deudas`. The Composer reads `draft` from the URL on mount and fills the field without sending, if the field is empty, then removes the param from the URL. A stored draft wins, so nothing is overwritten.

### D6. MCP tools

`list_debts` gives the order, owed, required, end months, the debt-free month, the extra and the cushion. `add_debt`, `update_debt`, `delete_debt` and `set_debt_extra` write directly, like the other MCP write tools, with readable `invalid_debt`, `debt_exists` and `outside_planning_horizon`.

### D7. Prompt

A "Debts" section:

- one debt at a time;
- for cards, ask "how much a month, or by when?" (never both), then the minimum and the rate, accepting "no lo sé";
- loans: installment, installments left, next one;
- personal: who, how much, a date if any;
- the order in plain words (highest interest first; unknown rates after known ones; family without interest last);
- the extra goes to the first debt and rolls forward;
- the cushion first when there are no savings, always with its reason, never blocking;
- no jargon, no humor, no judgment;
- recording a payment is a transaction or a transfer, not a change to the debt.

## Risks / Trade-offs

- **[The model invents a rate or a minimum]** → The prompt and the tool descriptions forbid it; an eval case covers "no sé el mínimo" → no minimum.
- **[Card owed changes with every card expense → frequent stale previews]** → Expected and safe; the fresh preview appears with "Needs updating".
- **[Undo of a card debt created with a target month recreates a monthly plan]** → Undo deletes a created debt rather than recreating it; only `debt_delete` recreates, and that uses the plan amount it had, which is what the user saw.
- **[Debt stress in conversation]** → A tone rule and an eval judge case.

## Migration Plan

No schema change. Ship the backend (with the router and accounts refactor) and the webapp together. Rollback: revert; debt actions become inert.

## Open Questions

None.
