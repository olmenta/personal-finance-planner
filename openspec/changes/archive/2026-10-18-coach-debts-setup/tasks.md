## 1. One debt write path

- [x] 1.1 `services/debt_ops.py`: `create`, `update`, `delete`, `set_extra`, `convert` and `fields_of`, validating plain data (`invalid_debt` / `outside_planning_horizon`) and calling the existing `services/debts.py` rules, raising `DebtError` (D1).
- [x] 1.2 `routers/debts.py` and the accounts convert-to-loan route use them with unchanged responses; the debts and accounts tests stay green.
- [x] 1.3 Tests: `fields_of` recreates an equivalent debt for each kind (card plan, loan with installments left as of now, personal with owed as of now), and `set_extra` returns the previous value.

## 2. Coach tools and actions

- [x] 2.1 `propose_debt` (card by account name or type; plan by month or by target, never both; optional minimum and rate), `propose_debt_change`, `propose_debt_removal`, `propose_debt_extra` and `propose_debt_conversion`, with debt resolution by name, card account or lender (D2).
- [x] 2.2 Kinds `debt`, `debt_update`, `debt_delete`, `debt_extra` and `debt_convert` in `coach_actions`:
  - the dry-run preview: the plan in words before/after; position, end month and required before/after; the debt-free month before/after; the category's assignment and To be assigned; `below_minimum`; the extra's target; the cushion note (D3);
  - commit through `debt_ops` with the recorded result;
  - undo rules, with conversion not undoable (D4);
  - titles ("Add debt: Visa, 200,00 € a month").
- [x] 2.3 Tests:
  - a card with a plan at 1,5 % → order, January, debt-free month, and the payment category's 200,00 €; nothing saved until Confirm;
  - a card by target month → 158,66 € a month;
  - a loan from fields;
  - a personal debt without a date → no debt-free month;
  - a card without a minimum → `below_minimum` null;
  - a second debt on the same card refused (`debt_exists`);
  - the extra's what-if, with the cushion note and cancel leaving it unchanged;
  - change and undo;
  - removal and undo;
  - extra and undo;
  - conversion not undoable;
  - undo refused after an editor change;
  - a stale preview after a card expense.

## 3. Prompt, fake model and evals

- [x] 3.1 `coach_v1.md`: the "Debts" section (D7). In "What you can't do here", remove debts.
- [x] 3.2 `app/llm/fakes.py`: "la Visa debe N y puedo pagar M al mes" → `propose_debt` card with the plan; "¿y si pongo N más al mes?" → `propose_debt_extra`.
- [x] 3.3 `evals/coach.py` cases:
  - a card with a plan;
  - a card with a target month;
  - a loan with installments;
  - a personal debt without a date;
  - "no sé el mínimo" → no minimum;
  - a what-if extra → `debt_extra`;
  - a change;
  - debt stress tone (judge);
  - no jargon (judge).

  Running it is the user's step and required before shipping.

## 4. MCP server

- [x] 4.1 Client debt methods. Tools `list_debts`, `add_debt`, `update_debt`, `delete_debt` and `set_debt_extra`, with plain-word arguments, debt resolution, readable errors, and results with end months and the debt-free month (D6).
- [x] 4.2 Tests: add a loan and read the end month; a card by type with a plan; update and delete; the extra; `debt_exists`.
- [x] 4.3 `docs/dev-mcp-server.md`: the debt tools.

## 5. Webapp

- [x] 5.1 `lib/api.ts` debt preview fields. `ActionPreview` gets a debt body: the plan in words before → after, the order position and end month, the debt-free month before → after, the category this month and To be assigned, "Below the minimum the bank allows", the extra's target, and the cushion note with its reason. No Edit for debt kinds; no Undo for conversion.
- [x] 5.2 "Talk it through with your coach" on `/debts`, linking to `/?draft=…`. The Composer fills an empty field from `draft` and clears the param (D5).

## 6. Docs

- [x] 6.1 Update the end-user guides.
  - `docs/debt-guide.md`: a "Talking about your debts" section (adding each kind by talking, "no lo sé", the what-if extra, changes, undo, the conversion), and "Where to find it" mentions the coach.
  - `docs/user-guide.md` ("Talking to your coach"): debts are no longer outside the chat.
- [x] 6.2 Check that the deltas match the implementation: `coach-conversation`, `debts` and `dev-mcp-server` modified.

## 7. Verification

- [x] 7.1 `uv run pytest` green in `backend/`.
- [x] 7.2 Type check, lint and build green in `webapp/` (separate dist dir).
- [x] 7.3 e2e (`fake:e2e`):
  - "la Visa debe 634,62 y puedo pagar 200 al mes" → preview → confirm → What you owe lists it;
  - "¿y si pongo 100 más al mes?" → preview with the debt-free month → cancel → the extra unchanged;
  - "Talk it through with your coach" fills the composer.

  `volta run npm run e2e` green.
