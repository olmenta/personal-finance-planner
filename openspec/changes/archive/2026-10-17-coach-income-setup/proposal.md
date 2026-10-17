## Why

Olmenta plans with **expected income** (income schedules): the salary on the 28th, fourteen pagas with the extras in June and December, a side income that varies. Without it, Home says Future coverage is "unknown" and the coach can't tell whether the plan fits. Today the only ways in are the onboarding interview and Settings → Expected income. The coach, which now builds the rest of the budget from sentences (categories, amounts, payments), still has to send people to a form for the first and most important number.

Expected income has a second job: matching what arrives. When a salary lands without the payer that links it to its schedule, it shows as "unplanned income", and the occurrence looks late. The linking is a small, rule-based change ("ese ingreso es la nómina") that the coach can propose safely.

## What Changes

- **New: expected income from the conversation.**
  - "Cobro 2.100 € el día 28 de Acme", "cobro 1.800 en 14 pagas, con las extras en junio y diciembre", "me pagan unos 400 al mes de clases" (estimated), "en marzo cobro la renta, unos 600". The coach turns each into an income proposal: name, amount, pattern, day, payer, estimated.
  - The preview shows:
    - the income in words ("2.100,00 € every month, day 28, from Acme");
    - this month's expected income and the next 12 months' total, before → after;
    - the year's coverage, before → after ("short 1.234 € a year" → "covered");
    - the reminder that income counts in To be assigned only when it arrives.
  - Confirm saves it through the same rules as the editor; Undo removes it while it's unchanged.
- **New: changing or removing expected income** ("mi sueldo sube a 2.200", "ya no cobro la paga extra"), with previews and Undo.
- **New: linking an income that arrived to what was expected** ("ese ingreso de 2.080 es la nómina"). It uses the existing payer-equality rule (no link table): the preview shows the occurrence going from late or pending to received, and the inflow leaving "unplanned". Undo restores the payers while unchanged.
- **Building a budget starts with income.** The prompt asks about income first (amount, day, how many pagas), then fixed bills, then day-to-day amounts, so coverage is known from the start.
- **The dev MCP server.** New tools `list_income`, `add_income`, `update_income` and `delete_income`, with readable errors.
- **Evals.** Cases for a monthly salary with day and payer, fourteen pagas (two schedules), an approximate income, a change, a removal, and linking an unplanned inflow.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `coach-conversation`: expected income set up, changed and removed from the conversation, and linking an inflow to its schedule. This adds new tools and action kinds, with the same preview, confirm and undo lifecycle.
- `income-schedules`: writes go through one shared operation (create, update, delete, payer resolution, the partial-update merge), used by the API, the coach and, through the API, the MCP server. The linking rule becomes a backend operation that the webapp's "This is…" and the coach share.
- `dev-mcp-server`: the curated tool set adds the income tools.
- `bff-proxy`: proxies `POST /income/link`.

## Impact

- **Backend:**
  - `services/income_ops.py`: create, update and delete extracted from `routers/income.py`, plus the link operation;
  - coach tools and actions (`propose_income`, `propose_income_change`, `propose_income_removal`, `propose_income_link`; kinds `income`, `income_update`, `income_delete` and `income_link`);
  - previews using the plan summary and month income;
  - a link endpoint used by the webapp;
  - the prompt, evals and tests.
- **MCP server:** the income tools, the client methods, and `docs/dev-mcp-server.md`.
- **Webapp:**
  - the income and link preview bodies in `ActionPreview`;
  - the "This is…" link calls the new endpoint (same behavior);
  - e2e.
- **Docs:** the user guide (Income and "Talking to your coach").
- **Unaffected:** the matching rules, budget math (income schedules never change To be assigned), the projection, and the onboarding interview.
