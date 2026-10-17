## Why

In Olmenta's method, rent, utilities, insurance and school fees are **payments**: described once ("850 € every month, day 1"; "600 € in February"), they compute the category's monthly amount, catch up when you're behind, and feed the Future projection. That's the heart of building a budget from scratch. Today the payments can only be described in the schedule editor on the Budget screen. The coach has to send people there, and someone new to budgeting has to translate "el seguro del coche son 600 en febrero" into a pattern picker by themselves.

`coach-budget-setup` lets the coach create categories and set day-to-day amounts. This change completes the picture: the coach and the dev MCP server can set up, change and remove payments from a sentence, with the same preview → confirm → undo safety.

## What Changes

- **New: payments from the conversation.**
  - "El alquiler son 850 € al mes, el día 1", "el seguro del coche 600 en febrero", "el colegio 632 de septiembre a junio el día 5", "el agua unos 120 cada 3 meses desde noviembre", "la comunión en mayo de 2028, unos 2.000". The coach turns each into a payment proposal (pattern, amount, day, months, estimated).
  - The preview shows the payment in words, the category's monthly amount before → after (normal and "to be on time"), this month's assignment before → after, To be assigned before → after, and the next due month. Confirm creates it through the same rules as the editor; Undo removes it while it's unchanged.
- **New: changing or removing a payment** ("el alquiler sube a 900", "ya no pago el gimnasio"), with a preview of the new monthly amount and Undo.
- **Categories first.** A payment for a category that doesn't exist goes through the category choice from `coach-budget-setup` (similar ones first, the group dropdown), then continues to the payment preview.
- **Guarded like the editor.**
  - Payments of debts ("managed from What you owe") can't be changed from the chat: the coach points to What you owe.
  - A card's payment category keeps its single plan.
  - Dates beyond the planning horizon are refused with the editor's rule.
- **Building a budget, step by step.** The prompt guides a beginner through their fixed bills one at a time (housing, utilities, insurance, school, subscriptions) and then the day-to-day amounts. It never asks for everything at once.
- **The dev MCP server.** New tools `list_payments`, `add_payment`, `update_payment` and `delete_payment`, with the same validation and readable errors. Payments for debts are refused there too.
- **Evals.** Cases for each pattern from a sentence, "unos" → estimated, a debt payment refused, and changing an amount.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `coach-conversation`:
  - setting up, changing and removing payments from the conversation (new tools and action kinds);
  - the payment preview body;
  - undo rules;
  - the guards shared with the schedule editor.

  This depends on `coach-budget-setup`.
- `dev-mcp-server`: the curated tool set adds the payment tools. This builds on the `coach-budget-setup` delta of the same requirement, so it archives after it.
- `payment-schedules`: payment writes go through one shared operation (create, update, delete, with the computed-assignment refresh), used by the API, the coach and the MCP server, so the rules can't drift.

## Impact

- **Backend:**
  - `services/payment_ops.py`: create, update and delete extracted from `routers/schedules.py`, which keeps its behavior;
  - coach tools and actions (`propose_payment`, `propose_payment_change`, `propose_payment_removal`; kinds `payment`, `payment_update`, `payment_delete`);
  - a payment sentence helper for previews;
  - the prompt;
  - evals and tests.
- **MCP server:** the payment tools in `mcp_server/tools.py`, the client methods, and `docs/dev-mcp-server.md`.
- **Webapp:** the payment preview body in `ActionPreview`, with a link to the category's payments in Budget; e2e.
- **Docs:** the user guide's "Talking to your coach" (setting up payments from the chat).
- **Unaffected:** the schedule math, the projection, debts (still managed from What you owe), and income schedules.
