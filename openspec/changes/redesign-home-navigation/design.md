## Context

The redesign (`ui-experiments/redesign.md` v2) keeps the engine and asks for a read-oriented Home in its second delivery:

- five destinations;
- a deduplicated deterministic summary;
- existing forms and debt flows still reachable;
- qualified forecast language;
- no accounting migration.

The first delivery (`redesign-safety-baseline`) already made the forecast honest, coach acceptance exact and "Already paid" truthful.

**Today:**

- **Sidebar:** 8 entries (Overview, Transactions, Accounts, Budgets, Upcoming, What you owe, Goals, Coach) plus Settings.
- **Mobile bottom bar:** Home, Report, FAB, Coach, Settings.
- **Dashboard:** the coach capsule, the "Este mes" panel with side column, the weekly chart and recent transactions.
- **Coach rail:** the same feed again at ≥1440px.

**What Home reads**, all already implemented:

- `build_overview` (the exact identity);
- `coach.visible`;
- `projection.upcoming`;
- `income.user_schedules`;
- the pending import batch;
- transaction dates and uncategorized counts.

## Goals / Non-Goals

**Goals:**

- One screen that says what to resolve now, with an honest status and a reconcilable breakdown.
- Five destinations with nothing lost: debts, categories and settings stay reachable.
- One server response per visit, so the next change (conversation) can bind to a `snapshot_version`.

**Non-Goals:**

- Chat, conversation persistence, typed actions, undo (`coach-conversation-actions`).
- Funded-versus-wanted coach proposals and locale/tone (`future-coaching`).
- Feature flags. Olmenta has one seeded development user and no production identity yet. Rollback is a revert, and flags become meaningful once real auth exists (a launch gate in the redesign).
- Any change to the overview, projection or coach math.

## Decisions

### D1. `GET /home` composes, never computes

`services/home.py::build_home(db, user)` calls:

- `build_overview(current month)`;
- `coach.visible`;
- `projection.upcoming(current month)`, only when income is known, to avoid work;
- small queries for the data status.

The summary maps the overview exactly, as the redesign's §3.4 prescribes:

- `M = accounts_cents`;
- `T = covered_cents`;
- `L = left_to_spend.total_cents − overspent_cents`;
- `F = saved.total_cents`;
- `U = to_be_assigned_cents`.

A test asserts `M = T + L + F + U` on generated data.

*Alternative considered:* the client composes the existing endpoints. Rejected because the redesign wants one versioned snapshot per visit, and the status rules belong server-side, next to the data.

### D2. Status rules

`needs_organizing` applies when any reason holds:

| Reason | Condition |
|---|---|
| `over_assigned` | U < 0 |
| `overspent_categories` | a flexible category has available < 0 |
| `unbudgeted_card_spending` | Σ `credit_overspent_cents` > 0 |
| `uncovered_payments` | Σ `short_cents` of `to_pay` > 0 |

`no_accounts` applies when there's no active account. Otherwise the month is `organized`.

The amounts come from the overview and the budget view of the current month: the per-category overspending list comes from the view's categories with negative available.

### D3. Data status and freshness

`limited` is true when:

- there's an uncategorized outflow this month;
- there's a pending import batch;
- or the newest confirmed transaction is more than **14 days** old. The redesign leaves freshness to product, so this is a proposed threshold, kept as a constant.

Without bank sync there's no real "updated at", so Home shows the generation time ("Updated 10:42") and the last transaction date.

### D4. Future status from the existing projection

Over `months[1:]` of `upcoming`:

- **`needs_attention`:** any `short_cents > 0`, or any month with `set_aside_funded_cents < set_aside_wanted_cents`. It reports the first such month and its gap.
- **`unknown`:** `income_known` is false.
- **`on_track`:** otherwise.

The copy says "under your current plan and expected income". This is the redesign's OS06 visibility. The coach detector for it stays in `future-coaching`.

### D5. Grouping and priority

**Priority:** `visible[0]`.

**Groups**, by kind:

| Group | Title | Kinds |
|---|---|---|
| `late` | "Money that's late" | `late_income`, `late_debt_payment` |
| `coming_up` | "Coming up" | `short_months` |
| `adjustments` | "Budget adjustments" | `overspending`, `underspending` |
| `unassigned` | "Money with no job" | `unassigned` |

The priority is excluded from its group, and empty groups are dropped. Groups are ordered by their first proposal's urgency. The webapp shows three, plus "See more".

### D6. Snapshot version

`snapshot_version = sha256(json(summary, status, reasons, data, future, [(fingerprint, revision) for proposals]))[:16]`.

It changes with any money write, any proposal change, or a new day that changes lateness. It's informational in this change: the conversation change will bind actions to it.

### D7. Webapp structure

- **`components/home/`:**
  - `HomeHeader`;
  - `CoachLine`, with deterministic copy per status: "Two categories need money before I can give you a reliable amount to spend" or "Your month is organized";
  - `MonthWidget`, with an expandable exact breakdown;
  - `PriorityAction`, reusing `ProposalCard` and `useProposalActions`;
  - `RecommendationGroups`;
  - `FutureWidget`;
  - `NoAccounts`, the guided empty state.
- **`app/(app)/page.tsx`:** rewritten to read `["home"]`. `invalidateMoneyQueries` adds `home`.
- **Navigation:** `Sidebar` and `BottomNav` are reduced to five. `TopBar` gains a Settings icon on mobile. Active matching treats `/debts` as Accounts.
- **Redirects:** `app/(app)/upcoming/page.tsx` → `app/(app)/future/page.tsx` (moved). `app/(app)/upcoming/page.tsx` becomes a client redirect that keeps `?month=`. `/coach` becomes a server `redirect("/")`.
- **Removed:** `CoachRail` and the layout slot.
- **Accounts:** gains a `DebtsCard` reading `["debts"]`.
- **Transactions:** gains the weekly `SpendChart`, moved from the dashboard, below the list.

### D8. No humor for shortfalls

The coach line and status copy are plain and second-person. Humor and locale variants come with `future-coaching`.

## Risks / Trade-offs

- **[The Home request does more work: overview, coach, projection]** → All are existing reads, and local Postgres makes them fast. The projection runs only when income is known. A p95 target can be checked later.
- **[Removing the rail removes an always-visible coach on wide screens]** → Home is the coach now, and the redesign explicitly removes the duplicated sidebar recommendation.
- **[Users with bookmarks to `/upcoming` or `/coach`]** → Redirects.
- **[14-day freshness may be wrong for people who record weekly]** → It's a constant, to tune with real use, and the copy explains instead of blocking.
- **[No flags]** → This is a pre-launch single user. Revert is the rollback, and the redesign's flag gates apply once auth lands.

## Migration Plan

There's no data migration. Deploy the backend and webapp together. Rollback is to revert the webapp and drop the endpoint.

## Open Questions

- The 14-day freshness threshold and the exact coach line copy, to validate with use.
