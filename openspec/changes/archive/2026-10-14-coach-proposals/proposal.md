## Why

The coach is decoration today. The side rail and `/coach` show a scripted conversation ("Set the 300 € cap", "On track for Japan?") with a text box that does nothing. The dashboard's coach capsule says "You're spending 18% more on dining" for everyone. Meanwhile the app already computes everything a good coach would point out, and the two real warnings (late income, late debt payment) live as separate dashboard capsules. Principle 8 also promises that "if a category overspends month after month, the coach proposes raising its budget", and nothing does that yet.

## What Changes

- **New: coach proposals.** Rules detect a fixed set of situations from data the app already has:
  - late income;
  - a late debt payment;
  - months ahead with a payment that won't be covered;
  - a day-to-day category that keeps going over;
  - money with no job;
  - a day-to-day category that keeps money left over.

  Each proposal carries a plain-language title and body built from templates, with exact numbers, and one action. No LLM: detection and copy are deterministic, and no financial data leaves the app.
- **New: one-tap raise and lower.** For repeated overspending or underspending, "Raise it" or "Lower it" sets this month's assignment to the average actual spending. Later months follow, because a new month drafts from the previous one. When raising needs more than Ready to assign holds, the proposal offers the categories that can give the difference.
- **New: proposal state.** "Not now" hides a proposal for one week. An accepted raise or lower doesn't come back until its condition holds again. The state is stored server-side, so it's the same on every device, and it lets acceptance be measured later without amounts or personal data.
- **Coach feed replaces the mock conversation.** The Coach rail (≥1440px) and the `/coach` page show the real proposals, ordered by urgency. Three are visible, with "See more (N)". The text box is removed until there is a real chat.
- **The dashboard shows the most urgent proposal** as one coach capsule. It replaces the separate late-income and late-debt capsules and the static "18% more on dining" capsule.
- **Docs.**
  - Update the user guide and the debt guide where they describe the late notes.
  - Add a coach section to the user guide.
  - Mark principle 8's coach proposal as done in project-definition and add the §10 entry.

### Not in this change

- The annual plan gap with where to adjust.
- Unplanned income → toward debts.
- Chatting about debts.
- LLM phrasing of proposals.
- Free-form chat.

## Capabilities

### New Capabilities

- `coach-proposals`: the proposal kinds and their rules and thresholds, the proposals API (list, dismiss, accept), urgency order, proposal state (one-week dismissal, acceptance until the condition recurs), one-tap raise and lower with the source picker, the coach feed in the rail and on `/coach`, and the dashboard capsule.

### Modified Capabilities

- `income-schedules`: the "Late income nudge on the dashboard" requirement is removed. Late income becomes a coach proposal with the same actions ("Add it", "It's already here").
- `debts`: the "Late debt payment nudge" requirement is removed. A late debt payment becomes a coach proposal linking to "What you owe".
- `bff-proxy`: the coach proposals routes are proxied.

## Impact

- **Backend:**
  - new `coach_proposal_states` table and an Alembic migration;
  - `services/coach.py` (detectors, ordering, state) and `routers/coach.py`;
  - reads from `budget_view`, `overview`, `projection`, `income` and `debts`. No change to budget math.
- **Webapp:**
  - `CoachFeed` and the proposal card;
  - `CoachRail` and `/coach` page without the scripted chat or input;
  - the dashboard capsule, removing `LateIncomeNudge` and `LateDebtNudge`;
  - `lib/api.ts` and BFF routes;
  - e2e updates for income and debts, plus a new coach spec.
- **Docs:** `docs/user-guide.md`, `docs/debt-guide.md`, `project-definition.md`.
