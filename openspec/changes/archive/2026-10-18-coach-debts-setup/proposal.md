## Why

`debt-paydown` gave Olmenta "What you owe": cards, installment loans and money owed to people, a paydown order (highest interest first), an optional monthly extra, a debt-free month and a cushion suggestion. Today all of it goes through a step-by-step plan editor. When it shipped, the plan was a follow-up where people **talk about their debts** with the coach.

Debts are where people need the most help and feel the most stress. They often don't know the installments left or the rate, and the editor's fields ask for exactly that. A conversation can go one debt at a time, accept "no lo sé", explain why one debt goes first, and answer "¿y si pongo 100 € más al mes?" with the real debt-free month before anything is saved.

The Home conversation already has the safety model for this: previews computed by the engine, confirm, undo. So debts join it instead of getting a separate interview. Several real debts are still waiting to be entered: Préstamo BBVA, the two iPhones, Ikea and Préstamo Manameli.

## What Changes

- **New: debts from the conversation.**
  - "Tengo la Visa con 634 €, puedo pagar 200 al mes", "el préstamo del coche son 290 € al mes, me quedan 34 cuotas desde noviembre", "le debo 670 € a mi hermano, sin fecha".
  - The coach proposes each debt with the editor's rules: a card by its account, with a monthly plan or a target month; a loan with installment, installments left and next month; a personal debt with amount, lender and an optional date.
  - The coach always asks the card's minimum and the rate, but "no lo sé" is fine; both stay optional, as in the editor.
  - The preview shows:
    - the debt and its plan in words;
    - its place in the order and its end month;
    - the debt-free month before → after;
    - this month's amount for its category and To be assigned before → after;
    - the "below the minimum" warning when it applies.
  - Confirm and Undo, as for every coach action.
- **New: changing a debt** ("la Visa: ahora puedo pagar 250", "me quedan 30 cuotas del Ikea", "el préstamo cobra 7 % al año"), **removing its plan**, and **converting a card account that is really a loan**, each with a preview and Undo.
- **New: the monthly extra, with its effect.** "¿Y si pongo 100 € más al mes?" previews the debt-free month and the first debt's end, before → after, and which debt gets the extra. When there's no cushion yet, the preview carries the cushion note with its reason ("so the next surprise doesn't end up on the card"). Nothing changes until Confirm, so the preview doubles as a what-if.
- **Explaining the plan.** The prompt explains the order (highest interest first, unknown rates after known ones, family last), what "~X €/month just for owing it" means, and why a cushion first. No jargon (no TAE, APR, snowball or avalanche), and no humor about debt.
- **From What you owe to the conversation.** The screen gets "Talk it through with your coach". It opens Home with the draft "Quiero ordenar mis deudas" ready to send. The plan editor stays.
- **The dev MCP server.** New tools `list_debts`, `add_debt`, `update_debt`, `delete_debt` and `set_debt_extra`.
- **Evals.** A card with a plan, a card with a target month, a loan, a personal debt without a date, "no sé el mínimo", a what-if extra, a change, the tone for debt stress, and no jargon.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `coach-conversation`: debts managed from the conversation: new tools and action kinds (`debt`, `debt_update`, `debt_delete`, `debt_extra`, `debt_convert`) with the same preview, confirm and undo lifecycle.
- `debts`:
  - debt writes are validated and applied by one shared operation (the API, the coach and the MCP server through the API);
  - "What you owe" gets the entry to the conversation.
- `dev-mcp-server`: the curated tool set adds the debt tools.

## Impact

- **Backend:**
  - `services/debt_ops.py`: validation from dicts plus the existing `create_debt`, `update_debt`, `delete_debt`, `convert_to_loan` and extra, with `DebtError` codes; `routers/debts.py` uses it;
  - coach tools and actions, with previews built on `build_debts_view` and the budget view;
  - the prompt, evals and tests.
- **MCP server:** the debt tools, the client methods, and `docs/dev-mcp-server.md`.
- **Webapp:**
  - the debt preview body in `ActionPreview`;
  - "Talk it through with your coach" on `/debts`, and Home reading a draft from the URL;
  - e2e.
- **Docs:** `docs/debt-guide.md` (talking about your debts) and the user guide's "Talking to your coach".
- **Unaffected:** the paydown order, the simulation, the cushion rule, the debt kinds and their math.
