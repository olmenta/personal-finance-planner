## Why

Delivery 2 of the conversational redesign (`ui-experiments/redesign.md` v2, §3, §8–§10). Today Olmenta has eight navigation destinations. The dashboard mixes a long "Este mes" panel, category lists, a weekly chart and recent transactions. The coach appears twice (dashboard capsule and side rail). Nothing tells the user when the money picture isn't reliable: negative "Left to spend" sits next to large "Unassigned" money with no explanation.

The redesign asks for a Home that answers "what do I need to resolve now?" and five destinations. Home is read-oriented in this delivery. It is built on the services that already exist, with no accounting migration, so the next delivery can add the conversation on top.

## What Changes

- **Five destinations:** Home, Budget, Transactions, Future and Accounts.
  - **Desktop:** the sidebar lists them, plus Settings at the bottom.
  - **Mobile:** five labeled tabs around the add-transaction button. Settings is reachable from the top bar.
  - **Goals** leaves the navigation (still mock, v2).
  - **Upcoming payments becomes Future** at `/future`, and `/upcoming` redirects.
  - **What you owe** stays at `/debts`, reached from Accounts, which is highlighted while there.
  - **The coach lives on Home:** the Coach rail is removed and `/coach` redirects to Home.
- **New: `GET /home`.** An adapter that composes the month overview, the coach proposals, the projection and data-quality signals into one response with a `snapshot_version`. It adds no second calculator: every amount comes from the existing services.
- **New: the month status.**
  - **"Organized":** shows "Left to spend" (net of overspending).
  - **"Needs organizing":** shown when money is over-assigned (To Be Assigned below zero), categories are overspent, card spending wasn't budgeted, or payments this month aren't covered. Each reason comes with its amount.
  - The exact breakdown always reconciles **Money in accounts = To pay + Left to spend + Saved + Unassigned**, using the redesign's mapping of today's overview contract.
- **New: data status.**
  - "Last transaction" date;
  - uncategorized transactions;
  - an import waiting for review;
  - whether expected income is known.

  When something limits the picture, Home says what, with a link to fix it ("Review data").
- **New: the Future status.**
  - **On track:** under the current plan and expected income.
  - **Needs attention:** a later month has an uncovered payment or underfunded set-asides.
  - **Coverage unknown:** there are no income schedules.

  The wording is always qualified: it's a monthly forecast, not a guarantee.
- **New Home screen.** In one column, top to bottom:
  - month and freshness;
  - one deterministic coach line;
  - the month widget, with "View exact breakdown";
  - **one priority action** (the most urgent coach proposal);
  - **up to three grouped recommendations** (late money, coming up, budget adjustments, money with no job), with the rest on demand;
  - the Future widget.

  There's no category list, weekly chart or transaction list on Home: the weekly chart moves to Transactions. With no accounts, Home guides you to add one and shows no numbers. Chat comes in the next change.
- **Accounts shows a "What you owe" card:** total and debt-free month, linking to `/debts`.
- **Docs:** the user guide's navigation, home screen, coach and Upcoming → Future sections; the debt guide's "where to find it".

## Capabilities

### New Capabilities

- `home`: the `GET /home` contract (summary mapping, month status and reasons, data status, Future status, grouped proposals, priority, snapshot version) and the Home screen with its states.
- `navigation`: the five destinations on desktop and mobile, Settings access, and redirects (`/upcoming` → `/future`, `/coach` → `/`).

### Modified Capabilities

- `month-overview`: the "Este mes" card requirement is removed. Home's month widget replaces it, reading the same overview.
- `webapp-server-state`: the "Dashboard served by the API" requirement is removed. Home reads `GET /api/home`, and the weekly chart moves to Transactions.
- `coach-proposals`: the feed moves to Home as grouped recommendations (no rail, no `/coach` page). The dashboard capsule becomes Home's priority action.
- `payment-projection`: the "Upcoming payments" screen becomes "Future" at `/future`.
- `debts`: "What you owe" is reached from Accounts instead of its own sidebar entry.
- `bff-proxy`: proxies `GET /api/home`.

## Impact

- **Backend:** `services/home.py` (composition, status rules, grouping, snapshot version), `routers/home.py` and `schemas.py`. It reads `overview`, `coach`, `projection`, `income`, `budget_view`, transactions and import batches. No migration.
- **Webapp:**
  - the new Home (`app/(app)/page.tsx` rewritten, `components/home/*`);
  - `Sidebar`, `BottomNav` and `TopBar` (Settings on mobile);
  - `/future` (moved from `/upcoming`, with a redirect) and the `/coach` redirect;
  - `CoachRail` removed;
  - a "What you owe" card on Accounts;
  - the weekly chart on Transactions;
  - `lib/api.ts`, the BFF route, and e2e updates (coach, income, debts and category-targets specs, plus a new home spec).
- **Unaffected:** budget math, the overview contract, projection, coach rules, debts, income and imports.
