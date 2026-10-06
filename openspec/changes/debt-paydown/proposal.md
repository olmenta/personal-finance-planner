## Why

Olmenta knows the payments a household makes but not what it owes. Debts are scattered:

- a Sabadell loan disguised as a credit card account, shown as a 9.709 € uncovered card debt;
- installment loans (a BBVA loan, two iPhones, Ikea) as loose categories with no balance or end date;
- money owed to family recorded nowhere.

There is no order to pay them in, no "when am I debt-free?", and nothing stops an installment from being forgotten. People who have never budgeted usually start with debt, so the app needs to give them an honest picture and a simple plan, in plain words.

## What Changes

- **New: debts.** A category can be marked as a debt of one of three kinds, each built on what already exists:
  - **card**: the credit account's payment category; what's owed is the card's uncovered debt;
  - **installment loan**: a category with a finite monthly payment schedule; what's owed is the installments left × the installment;
  - **personal**: a category with an amount owed, optionally due in a given month (the lender needs it back by then).

  Each debt can carry an optional interest rate, per month or per year, or none when the user doesn't know it.
- **New: required versus optional payments.**
  - Required: card plans, loan installments, and personal debts with a due month. They are payment schedules, so they enter the budget, the month overview, the projection and the annual plan.
  - Optional: personal debts without a date, and the monthly extra money for debts.
- **New: card plan.**
  - The user says "how much can you pay a month?" or "when do you want to be done?", and the app computes the other.
  - The bank's minimum payment is always asked, and can be skipped. When the plan falls below it, the app explains why that matters.
  - The plan is a monthly payment schedule on the card's payment category, paid by transfers into the card.
- **New: paydown order and debt-free date.**
  - The monthly extra goes to the first debt in the order: known rate highest first, then unknown rate, then interest-free. Ties go to the smallest balance.
  - When a debt is paid off, its money rolls to the next one.
  - A simulation gives each debt's end month and the debt-free date. Interest is used only when a rate is known.
- **New: "What you owe" screen.**
  - It shows the total, the debt-free date, the debts in order with one plain sentence each ("Pay this one first: it charges you the most. ~9 €/month just for owing it."), and the monthly extra.
  - A coach note suggests keeping a small emergency cushion before putting extra into debts, always with the reason.
  - An always-visible **"Work on my debts"** button sits on the screen and on every debt. In this change it opens the plan editor.
- **New: late-installment nudge.** When a required debt payment is more than 3 days past its day and unpaid, the dashboard shows a coach capsule, like the late-income nudge.
- **New: turn a credit account into an installment loan.** For a loan that was set up as a card: from the installment, installments left and day, it creates a loan debt in a "Deudas" group and archives the account. The user's Sabadell loan is converted this way.
- **Plain language everywhere.** The UI never says TAE, APR, amortization, snowball or avalanche.
- **Docs.** Add the debt rules to project-definition §3, replace the §4.2 "Paying down pre-existing debt" entry with the chat follow-up below, update §6.4, and add a §10 decision entry.

### Next (not in this change)

**Chat about debts.** The same "Work on my debts" button opens a short coach interview instead of the editor. It reuses the onboarding engine: the LLM layer `onboarding`-style route, a versioned prompt config, structured output, and a review screen before anything is saved. The user can say "I owe 2.900 € to my in-laws, they need it in March" or "the iPhone has 14 installments of 45 € left" to create or re-plan debts. The button and its placement ship now, so the follow-up only changes what it opens and adds the sparkle (reserved for the AI coach).

## Capabilities

### New Capabilities

- `debts`:
  - debt kinds and their link to categories, schedules and credit accounts, and what's owed per kind;
  - the optional rate and the card minimum;
  - the debts API, the paydown order, the extra and rollover, the debt-free simulation;
  - converting a credit account into a loan;
  - the "What you owe" screen, the plan editor and its always-visible entry button, and the late-installment nudge.

### Modified Capabilities

- `month-overview`: a card plan occurrence on a payment category counts as paid from transfers into the card. Payment categories with a plan appear in "Still to pay this month". Pending required debt payments report `late`.
- `payment-schedules`: a payment category may hold one monthly plan schedule. Its assignment is computed from the plan like any category with payments, alongside the funded card moves.
- `accounts-api`: credit accounts can be converted into an installment loan (`POST /accounts/{id}/convert-to-loan`).
- `bff-proxy`: the debts routes and the conversion route are proxied.

## Impact

- **Backend:**
  - new `debts` table and an Alembic migration;
  - `services/debts.py` (what's owed, order, simulation) and `routers/debts.py`;
  - `services/overview.py` (card plan matching, `late` flag);
  - `services/budget_view.py` (computed assignment on payment categories with a plan);
  - `routers/accounts.py` (conversion) and `schemas.py`.
- **Webapp:**
  - new `/debts` screen (sidebar "What you owe"), `DebtEditor`, and a late-installment nudge next to the late-income one;
  - the accounts screen gets a "This is a loan" action;
  - `lib/api.ts` and BFF routes.
- **Data:** nothing is seeded. The user enters the installment loans' figures (not known yet) through the editor, and converts the Sabadell loan account with the new action.
- **Unaffected:** income schedules, imports, transfers' math, the MCP server.
