## 1. One payment write path

- [x] 1.1 `services/payment_ops.py`: `create_payment`, `update_payment` and `delete_payment`, extracted from `routers/schedules.py` (validation, debt and card-plan guards, horizon, partial-update merge and pruning, computed-assignment refresh), raising `PaymentError(status, code)` (D1).
- [x] 1.2 `routers/schedules.py` uses them with unchanged responses; the schedules, targets and debts tests stay green.
- [x] 1.3 `services/payment_text.py`: the payment in words, ported from the webapp's `describe`, with a fixture test covering each pattern, day, count and estimated.

## 2. Coach tools and actions

- [x] 2.1 `propose_payment` with typed arguments and the sentence → pattern table in its description; an unknown category points to `propose_category` with the payment as follow-up (D2). Add `payment` to the follow-up union of `coach-budget-setup`.
- [x] 2.2 `propose_payment_change` and `propose_payment_removal`, with payment resolution by name or by single-payment category (debt payments excluded and refused with `managed_by_debt`).
- [x] 2.3 Kinds `payment`, `payment_update` and `payment_delete` in `coach_actions`:
  - dry-run preview with the sentence before/after, normal and to-be-on-time amounts before/after, next due month, categories and To be assigned (D3);
  - commit through the payment ops with the recorded result;
  - undo rules (D4);
  - titles ("Add payment: Alquiler, 850,00 € every month").
- [x] 2.4 Tests:
  - rent from a sentence → preview, nothing saved, then confirm → assignment 850,00 €;
  - annual with 200,00 € carried → normal 50,00 €, to be on time 80,00 €, next due February 2027;
  - `every_n` estimated;
  - `once` beyond the horizon refused;
  - a debt's payment refused;
  - a card plan refused;
  - change and undo;
  - removal and undo;
  - undo refused after an edit from the editor;
  - payment for a new category through the category choice;
  - a stale preview after an editor change.

## 3. Prompt, fake model and evals

- [x] 3.1 `coach_v1.md` (or the next version if v1 shipped): the "Setting up payments" section and the budget-building order (D6).
- [x] 3.2 `app/llm/fakes.py`: "el alquiler son N al mes, el día D" → `propose_payment` monthly; "sube a N" → `propose_payment_change`.
- [x] 3.3 `evals/coach.py` cases:
  - one per pattern from a Spanish sentence (monthly with day, annual, some_months September–June, every_n with start, once, no_date);
  - "unos" → estimated;
  - a debt's payment → no action;
  - "el alquiler sube a 900" → `payment_update`.

  Running it is the user's step and required before shipping.

## 4. MCP server

- [x] 4.1 Client schedule methods. Tools `list_payments`, `add_payment`, `update_payment` and `delete_payment`, with typed arguments, payment resolution, readable error codes, and descriptions with the pattern table (D5).
- [x] 4.2 Tests:
  - add a monthly payment and read the new monthly amount;
  - update and delete;
  - a debt payment refused;
  - an unknown category points to `find_categories`;
  - a horizon refusal.
- [x] 4.3 `docs/dev-mcp-server.md`: the payment tools.

## 5. Webapp

- [x] 5.1 `lib/api.ts`: the payment preview fields. `ActionPreview` gets a payment body: the sentence (before → after for changes), monthly amount and to be on time before → after, this month's assignment, To be assigned, next due month, "Estimated", and a "See its payments" link to the category in Budget.

## 6. Docs

- [x] 6.1 Update the end-user guides. In `docs/user-guide.md` ("Talking to your coach" and "Categories with payments"):
  - setting up, changing and removing payments by talking;
  - what the preview shows;
  - debts still in What you owe.

  Check `docs/debt-guide.md`: installments can't be changed from the chat.
- [x] 6.2 Check that the deltas match the implementation: `coach-conversation`, `dev-mcp-server` and `payment-schedules` modified.

## 7. Verification

- [x] 7.1 `uv run pytest` green in `backend/`.
- [x] 7.2 Type check, lint and build green in `webapp/` (separate dist dir).
- [x] 7.3 e2e (`fake:e2e`):
  - "el alquiler son 850 al mes, el día 1" → preview → confirm → Budget shows Alquiler "From your payments" 850,00 €;
  - "el alquiler sube a 900" → confirm → undo.

  `volta run npm run e2e` green.
