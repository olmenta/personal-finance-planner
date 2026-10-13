## Context

Today the user's debts live in three improvised shapes:

- **"Sabadell - Prestamo".** A `credit` account at −9.709,83 €, payment day 2, with its system payment category. It is treated as a card, so its whole balance shows as uncovered card debt.
- **"Sabadell - Visa".** A real card at −634,62 €, already following the YNAB card model (principle 10).
- **A "Deudas" category group.** "Tarjeta de crédito", "Préstamo BBVA", "Préstamo Manameli", "Iphone Caro", "Iphone Seba" and "Ikea" are `flexible` categories with no schedules, so the app knows no balance, installment or end.

What already exists and is reused:

- **Payment schedules.** Rules, `monthly` with `count`, `once`, computed assignment, catch-up, matching in the month overview, projection and annual plan.
- **Credit cards.** Payment category, funded moves, `uncovered_debt_cents`.
- **Late-income nudge.** The pattern for a dashboard coach capsule.

The installment figures for the BBVA loan, the iPhones, Ikea and Manameli are not known yet. Nothing is seeded: the user enters them in the editor.

## Goals / Non-Goals

**Goals:**

- One honest picture of what's owed, the order to pay it in, and a debt-free date, in plain words.
- Required debt payments (card plans, installments, personal debts with a date) inside the budget, the overview, the projection and the annual plan, with a nudge when late.
- An optional rate that only orders the debts and produces one "~X €/month just for owing it" sentence.
- An always-visible "Work on my debts" entry point that the chat follow-up can take over.

**Non-Goals:**

- Chat capture of debts. It's the documented follow-up.
- Loan accounts with reconciled balances, interest/principal split, amortization tables, or early-repayment fees.
- Multi-currency. Family debt in COP is recorded in euros.
- Automatic budget assignments for the extra. The screen tells the user where to put it; assigning stays an explicit action.
- A snowball option. The order is fixed: by rate, with ties going to the smallest balance.

## Decisions

### D1. A `debts` table linked one-to-one to a category

`debts(id, user_id, category_id unique, kind card|loan|personal, rate_bp?, rate_period month|year?, minimum_cents?, owed_cents?, due_month?, created_at)`:

- `owed_cents` is used by `personal` only.
- Card and loan amounts owed are derived (D2).
- A per-user `debt_settings(user_id pk, extra_monthly_cents)` holds the extra.

*Alternatives considered:*

- **Debt columns on `categories`.** Rejected because they would be nullable fields on every category for a minority of rows, and they mix budget structure with a plan.
- **Loan accounts (YNAB-style).** Rejected for now. They need interest/principal splitting and reconciliation, which is more than a beginner needs. The user's own loan-as-card setup shows the account model confuses more than it helps here.
- **The extra in the preferences document.** Rejected for the same reason income left it: planning shouldn't read interview memory.

### D2. What is owed is derived, never typed twice

- **card**: `−balance − max(0, available − this month's unpaid plan)`. Spending set aside at purchase isn't debt. The plan assigned this month sits in the payment category too, but it hasn't paid anything until the transfer, so counting it would subtract it twice (once as set aside, once as the simulated payment).
- **loan**: the installment × the occurrences of its `monthly`/`count` schedule from the current month on, minus the current month's occurrence when the overview reports it paid.
- **personal**: `owed_cents − Σ confirmed spending in its category since created_at`, floored at 0.

Loans ignore interest by design. The installment already includes it, and "installments left" is the number people actually know.

### D3. The card plan is a payment schedule on the payment category

Required card payments need everything schedules give: computed assignment, coverage in "Still to pay", the projection, the annual plan and the late nudge. So the plan is one `monthly` schedule on the payment category, created and edited only through the debts API. Two consequences:

- **Matching.** The overview counts its occurrence as paid when the month's transfers into the card reach the plan amount (payments are transfers, never spending). The payment category's activity already tracks those payments, so this is a small branch in `match_payments`.
- **Assignment.** The payment category's computed assignment is the plan amount. Funded card moves still arrive on top (credit-cards math is unchanged), so new spending is covered and the plan pays down the old balance.

*Alternative considered:* a plan amount stored on the debt, with bespoke budget and overview code. Rejected because it duplicates schedule behavior in four places.

### D4. Loans and dated personal debts are ordinary schedules

- **Loan**: one `monthly` schedule with `count = installments_left`, `start_month = next_month`, and `day` on its category.
- **Personal with a due month**: one `once` schedule of `owed_cents` in that month, whose catch-up spreads the saving until then. Editing `owed_cents` or `due_month` rewrites it.

The debts API is the only writer of these schedules. Editing them in the payment editor shows "Managed from What you owe" with a link.

### D5. Order and simulation in pure functions

`services/debts.py`:

- **Order key.** `(group, -monthly_rate, owed)`, where group is 0 for a known rate, 1 for an unknown rate, and 2 for a personal debt without a rate. The monthly rate normalizes yearly rates as `rate / 12` (simple, not compounded: good enough for ordering and one sentence).
- **Simulation.** A loop of up to 120 months. Each debt gets its required payment. The first debt in the order gets the extra plus the pool of freed payments. Interest accrues before the payment when a rate is known. Each debt's `end_month` is the month its owed reaches 0.
- **Card plan from a target month.** The annuity formula `P·r / (1 − (1+r)^−n)`, rounded up to the cent. Without a rate, `ceil(P / n)`.

Pure functions, so the editor's live preview can mirror them client-side, like `lib/schedules.ts` mirrors `services/schedules.py`.

### D6. Converting the loan-as-card account

`POST /accounts/{id}/convert-to-loan` runs in one transaction:

1. ensure the "Deudas" group;
2. create the category named after the account;
3. create the loan debt and its schedule;
4. move the payment category's positive available into the new category (a current-month move);
5. archive the account, which archives its payment category.

The account's history stays (archiving keeps transactions counting), so the all-time balance still reflects the real loan.

This is generic, not a one-off script. Anyone who set a loan up as a card gets the same fix, and the user's Sabadell loan is converted with it.

### D7. Late debt payments reuse the overview

`OverviewPending` gains `late: bool`. It's true only for occurrences of debt schedules in the current month that are more than 3 days past their day (a missing day counts as month end). The dashboard nudge (`LateDebtNudge`) mirrors `LateIncomeNudge`: one capsule, a link to `/debts`, and dismissal in `localStorage` keyed by month and the set of late schedule ids.

It's limited to debts so estimated bills (water, electricity), which often charge late, don't nag.

### D8. Webapp

- **`/debts` page.** Sidebar label "What you owe", wallet icon (no sparkle until chat). It renders `GET /debts`.
- **`DebtEditor` sheet.** Kind picker, then kind-specific fields, then the rate question, with a live preview from a TS mirror of D5. "Work on my debts" opens it from the page header and every row.
- **Accounts screen.** Gains "This is a loan, not a card" on credit accounts, opening a short form for the D6 conversion.
- **Server state.** TanStack keys `["debts"]`. Debt writes invalidate money queries (budget, overview, upcoming, plan-summary, accounts) plus `["debts"]`.

### D9. Plain language

Copy rules:

- Rates read "1,5 % a month" or "18 % a year".
- Unknown rates read "rate unknown".
- The first debt's reason reads "it charges you the most" or, on a tie, "it's the closest to done".
- Interest reads "~9 €/month just for owing it".
- Payoff dates read "done in January".

Never TAE, APR, amortization, snowball or avalanche. The cushion note always states its reason.

## Risks / Trade-offs

- **[A card's `owed` jumps when new spending isn't budgeted (credit overspending adds to uncovered debt)]** → This is the honest behavior: the plan's end month moves out, and the screen shows it. The existing credit overspending cues in the budget remain the first line of defense.
- **[Card plan "paid" when transfers ≥ plan, although part of the transfer paid new spending]** → It's an approximation, but cheap and predictable. The owed amount (D2) stays exact because it comes from the balance, not from the matching.
- **[Loan owed ignores early repayments]** → After paying extra on a loan, the user updates "installments left" in the editor. The coach copy says so. Extra rarely reaches loans before they end, because cards rank first.
- **[Yearly rate normalized as rate / 12]** → It slightly overstates the monthly interest of compounded APRs. That's fine for ordering and one approximate sentence, and it's labeled "~".
- **[Debt schedules edited in the generic payment editor would desync the debt]** → D4 makes the debts API their only writer. The payment editor shows them read-only with a link.

## Migration Plan

1. The Alembic revision creates `debts` and `debt_settings`, with no data step.
2. After deploy, the user converts "Sabadell - Prestamo" through the accounts action. They mark "Sabadell - Visa" as a card debt with a plan, and add the "Deudas" loans in the editor once they know the figures.
3. Rollback: dropping the tables leaves the schedules as ordinary payments. The converted account stays archived and can be unarchived.

## Open Questions

- After the user decides what "Tarjeta de crédito" in "Deudas" is, it should become either the Sabadell Visa's card debt (and the category is archived) or a loan. That's resolved in the editor when the figures arrive.
- The cushion size (300 € to 1.000 €, from one month of required payments) is a starting rule. Tune it after real use.
