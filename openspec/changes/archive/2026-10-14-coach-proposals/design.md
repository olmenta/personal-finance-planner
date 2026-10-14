## Context

**The coach UI today.**

- `CoachRail` and `/coach` render `CoachConversation`, a scripted chat with mock messages, a fake "Set the 300 € cap" button, suggestion chips and a text input that sends nothing.
- The dashboard has three separate capsules: `LateIncomeNudge`, `LateDebtNudge` (both real, dismissed in `localStorage`), and a static "You're spending 18% more on dining" fallback.
- The budget screen's suggestion capsule (confirm drafted assignments, budget-suggestions) is out of scope and stays.

**Data already computed that proposals read:**

- `budget_view.build_view(month)`: per category, assigned, spent, available, kind; To Be Assigned.
- `overview.build_overview(month)`: `to_pay` with `late`.
- `projection.upcoming(month)`: months with uncovered occurrences.
- `income.month_income(month)`: occurrences with `late`.
- Category kinds: flexible, scheduled, savings, credit_payment.

**Constraints:**

- Coach v1 has no free-form chat.
- No financial data in telemetry (GDPR).
- Plain language.
- The sparkle icon is reserved for the coach.

## Goals / Non-Goals

**Goals:**

- One deterministic, testable source of coach proposals, with exact numbers and one action each.
- Principle 8: repeated overspending proposes raising the budget, and repeated underspending proposes lowering it.
- One place for coach attention: the feed (rail and `/coach`) plus a single dashboard capsule.
- No nagging: urgency order, 3 visible, one-week dismissal, acceptance remembered.

**Non-Goals:**

- LLM-written copy, free-form chat, chatting about debts.
- The annual gap breakdown and unplanned income → debts (later kinds that plug into the same framework).
- Notifications outside the app.
- Analytics events. The state table makes acceptance measurable later without amounts.

## Decisions

### D1. Detectors are pure rules over existing services

`services/coach.py` has one detector per kind. Each reads the services above and returns `Proposal(fingerprint, kind, urgency, amount_cents, title, body, action, payload)`. Thresholds are module constants:

- `MIN_DIFF_CENTS = 1000`
- `ROUND_TO_CENTS = 500`
- `HISTORY_MONTHS = 3`
- `OVERSPENT_MIN_MONTHS = 2`
- `UNDERSPENT_MIN_MONTHS = 3`
- `DISMISS_DAYS = 7`

*Alternative considered:* an LLM that reads a summary and writes suggestions. Rejected for v1:

- the numbers must be exact and testable;
- it would send financial data to a provider for every page load;
- the voice can be met with templates.

The LLM layer can later rephrase the same structured proposals without changing detection.

### D2. Closed-month history from the budget view

The overspending and underspending detectors build the budget view for each of the last 3 closed months (the months before the current one) once, and reuse it across categories.

- A month counts as **overspent** for a category when its `available_cents < 0` at that month's end.
- A month counts as **underspent** when `spent_cents < assigned_cents`.
- The suggested amount is `ceil(mean(spent over the 3 months) / 500) × 500`.
- Only `flexible` categories, not archived, present in all 3 months.

*Trade-off:* three view builds per request. They're cheap locally, and the result can be cached per request. A month the user never opened has no assignments, so the category lacks history and gets no proposal, which is the right outcome.

### D3. Fingerprints and state

- **Fingerprint:** `"{kind}:{subject}:{YYYY-MM}"`, for example `overspending:<category_id>:2026-10`. For `short_months` the subject is the earliest short month. For `unassigned` there's no subject.
- **Table:** `coach_proposal_states(user_id, fingerprint, state dismissed|accepted, until?, created_at)`, unique `(user_id, fingerprint)`.
- **Visibility:** a proposal is visible unless its fingerprint is `accepted`, or `dismissed` with `until > now`.

Including the month in the fingerprint means a dismissed or accepted proposal naturally comes back next month if its condition still holds. After an accepted raise, the condition usually no longer holds, because the assignment now matches the average.

The table holds no amounts, names or ids beyond the opaque subject id inside the fingerprint, so it is safe for later acceptance metrics.

### D4. Accept applies through the budget's own operations

- **`raise` without a source:** set the assignment (the same path as `PUT /budget/{month}/assignments/{id}`). If the increase is more than To Be Assigned, return 409 `not_enough_to_assign`.
- **`raise` with `from_category_id`:** move the difference from that category (the same rules as `POST /budget/{month}/moves`, bounded by its available).
- **`lower`:** set the assignment. The freed money returns to To Be Assigned.

The proposal is recomputed at accept time. If it no longer exists (the condition changed), the API returns 404 `proposal_not_found`. Only `flexible` categories are affected, so the "computed from payments" guard never applies.

### D5. Actions that aren't one-tap stay client-side

`add_income`, `link_income` and `open` don't hit the accept endpoint:

- `add_income` opens the prefilled add-transaction dialog;
- `link_income` opens the income breakdown;
- `open` navigates.

This is the same behavior the late-income and late-debt nudges have today, moved into the feed card. Their dismissal moves to the server (`POST …/dismiss`).

### D6. Webapp

- **`components/coach/ProposalCard.tsx`:** title, body, action and "Not now". For `raise` with `sources`, it expands a small picker of the source categories.
- **`components/coach/CoachFeed.tsx`:** `useQuery(["coach-proposals"])`, first 3 plus "See more (N)", and the empty state. Used by `CoachRail` and the `/coach` page.
- **`CoachConversation`:** its scripted chat and input are deleted. `CoachHeader` stays.
- **Dashboard:** `CoachCapsuleTop` renders the first proposal as a `CoachCapsule` with the action and "Not now". `LateIncomeNudge`, `LateDebtNudge` and the static fallback capsule are removed. The prefilled `AddTransactionDialog` and `IncomeBreakdown` wiring moves into the card's action handler.
- **Invalidation:** money writes (`invalidateMoneyQueries`) also invalidate `["coach-proposals"]`, since any transaction or assignment can change them.

### D7. Copy templates (plain language)

| kind | title | body |
|---|---|---|
| `overspending` | "Restaurantes keeps going over" | "It went over in 2 of the last 3 months. You usually spend about 230,00 €. Raise it from 200,00 €?" |
| `underspending` | "Gasolina always has money left" | "You've spent about 60,00 € a month lately. Lower it from 120,00 € and free 60,00 €?" |
| `unassigned` | "210,00 € with no job yet" | "Give every euro a job: assign it to what's coming." |
| `short_months` | "March won't be fully covered" (or "March and June…") | "500,00 € short for Seguro coche. Plan for it now." |
| `late_income` | "Your Nómina isn't here yet" | "It usually arrives on the 27th (2.800,00 €)." |
| `late_debt_payment` | "Your Ikea payment is late" | "It was due on the 5th and hasn't gone out yet." |

The coach says "I" sparingly, and copy stays in sentence case.

### D8. Found while implementing

- **Parallel requests could both open the same budget month.** The dashboard and the coach feed load at the same time, and both could try to create the month, which raised a unique violation. `materialize_month` now creates it inside a savepoint and reuses the month the other request created.
- **The rail is hidden on `/coach`.** The page shows the same feed full width, so a second copy beside it would be noise.
- **Upcoming payments opens `?month=`.** "See the month" lands on that month's row.

## Risks / Trade-offs

- **[Proposals feel naggy]** → Mitigations: urgency order, 3 visible, one-week dismissal, and 10 € minimums. Kinds can be tuned through constants.
- **[A raise taken from To Be Assigned leaves nothing for other categories]** → The 409 plus the sources picker makes the trade-off explicit. The budget's To Be Assigned hero still shows the result.
- **[Short months depend on income schedules]** → Without income schedules the projection has no coverage, so no `short_months` proposal is produced. That's correct: it can't know.
- **[History quality]** → Months the user never opened, or partial first months, can distort averages. Requiring all 3 months with an assignment limits this.
- **[Removing the scripted chat makes the rail emptier]** → The empty state copy and real proposals replace it. That's more honest than a fake conversation.

## Migration Plan

1. The Alembic revision creates `coach_proposal_states` (no data step).
2. Deploy the backend and webapp together. Old `localStorage` dismissals for late nudges are simply ignored, so at worst a late note shows once more.
3. Rollback: drop the table and restore the previous webapp.

## Open Questions

- None blocking. The thresholds (2 of 3, 3 of 3, 10 €, round to 5 €) are constants to tune after real use.
