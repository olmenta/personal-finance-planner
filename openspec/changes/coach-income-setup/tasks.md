## 1. One income write path

- [x] 1.1 `services/income_ops.py`: `create_income`, `update_income`, `delete_income`, `link_income` and `fields_of`, extracted from `routers/income.py` (validation, merge with pattern pruning, empty payer clears it, payer resolution) and the webapp's linking rule, raising `IncomeError(status, code)` (D1).
- [x] 1.2 `routers/income.py` uses them with unchanged responses. Add `POST /income/link {transaction_id, schedule_id}`, which returns the month income view (404 `transaction_not_found` / `income_schedule_not_found`). The income tests stay green.
- [x] 1.3 Tests: link with the schedule's payer, with the transaction's payer, with neither (a payee from the schedule's name), the occurrence received afterwards, and the 404s.

## 2. Coach tools and actions

- [x] 2.1 `propose_income`, `propose_income_change` and `propose_income_removal`: typed arguments with the sentence → pattern table and the 14-pagas shape in the descriptions; income resolved by name or unique payer (D2).
- [x] 2.2 `propose_income_link(transaction, income)`: the `transaction:<id>` ref from `get_income` (unplanned items get refs) or `search_transactions`; the occurrence must be in the inflow's month.
- [x] 2.3 Kinds `income`, `income_update`, `income_delete` and `income_link` in `coach_actions`:
  - their own dry-run preview: the sentence before/after with payer, month and year expected before/after, coverage gap and `income_known` before/after, To be assigned unchanged, and the link occurrence status (D3);
  - commit through `income_ops` with the recorded current-state result;
  - undo rules (D4);
  - titles ("Add income: Nómina, 2.100,00 € every month, day 28, from Acme").
- [x] 2.4 Tests:
  - a salary from a sentence → preview with coverage from unknown to known, To be assigned unchanged, nothing saved; confirm saves it;
  - fourteen pagas as two proposals;
  - estimated;
  - `no_date` refused;
  - change and undo;
  - removal and undo;
  - undo refused after an editor edit;
  - a stale preview after an editor edit;
  - link a late salary → received, and undo restores the payers.

## 3. Prompt, fake model and evals

- [x] 3.1 `coach_v1.md`: the "Expected income" section, and "Building a budget" starting with income (D6).
- [x] 3.2 `app/llm/fakes.py`: "cobro N el día D" → `propose_income` monthly with day; "mi sueldo sube a N" → `propose_income_change`.
- [x] 3.3 `evals/coach.py` cases:
  - salary with day and payer;
  - 14 pagas → two incomes;
  - "unos 400 al mes" → estimated;
  - "mi sueldo sube a 2.200" → `income_update`;
  - "ya no cobro la paga extra" → `income_delete`;
  - "ese ingreso de 2.080 es la nómina" → `income_link`;
  - "me ha llegado la nómina, 2.100" → a transaction, no income schedule.

  Running it is the user's step and required before shipping.

## 4. MCP server

- [x] 4.1 Client income methods. Tools `list_income`, `add_income`, `update_income` and `delete_income`, with typed arguments, resolution by name or payer, readable errors, and the pattern guide (D5).
- [x] 4.2 Tests: add a salary and read the yearly total; update and delete; `no_date` refused; an unknown income lists candidates.
- [x] 4.3 `docs/dev-mcp-server.md`: the income tools.

## 5. Webapp

- [x] 5.1 BFF route `api/income/link`. `lib/api.ts`: `linkIncome` and the income preview fields. `IncomeBreakdown`'s "This is…" uses `linkIncome`.
- [x] 5.2 `ActionPreview`: the income body (sentence before → after, this month's expected, the year's expected, coverage "short X € a year" / "covered" / "unknown", "To be assigned changes when the money arrives") and the link body (occurrence status before → after); no Edit for income kinds.

## 6. Docs

- [x] 6.1 Update the end-user guides. In `docs/user-guide.md` ("Income" and "Talking to your coach"):
  - expected income by talking (14 pagas, estimated, payer);
  - changing and removing it;
  - linking "this income is my salary";
  - building a budget starting with income.

  Check `docs/debt-guide.md` for income wording.
- [x] 6.2 Check that the deltas match the implementation: `coach-conversation`, `income-schedules`, `dev-mcp-server` and `bff-proxy` modified.

## 7. Verification

- [x] 7.1 `uv run pytest` green in `backend/`.
- [x] 7.2 Type check, lint and build green in `webapp/` (separate dist dir).
- [x] 7.3 e2e (`fake:e2e`):
  - "cobro 2100 el día 28" → preview → confirm → Home's Future is no longer "Coverage unknown";
  - "mi sueldo sube a 2200" → confirm → undo;
  - update `income.spec.ts` if "This is…" changes behavior (it shouldn't).

  `volta run npm run e2e` green.
