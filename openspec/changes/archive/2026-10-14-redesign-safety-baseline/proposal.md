## Why

The conversational redesign (`ui-experiments/redesign.md`, version 2) keeps the financial engine and builds a simpler Home on top of it. Home will refresh on entry, keep the conversation, show widgets, and execute grouped changes. Before any of that can write money, its review found defects that would make a coach say the wrong thing or apply the wrong amount:

- The forecast hides a current deficit (F01) and rounds a missing cent away (F06).
- Accepting a coach proposal can apply an amount the user never saw (F02), or use the target category as its own source (F03).
- "Already paid" omits partial payments (F04) and counts a card purchase and its settlement twice (F05).
- A payment beyond the 10-year horizon silently needs nothing (F10).
- An empty coach feed claims the plan is on track (OS05).
- Several base specs contradict the code (OS01–OS04).

The redesign's own delivery sequence puts these fixes first: "resolve F01–F03 before broad conversational writes".

## What Changes

- **Forecast starts from real money (F01).** The projection carries signed To Be Assigned, deducts the selected month's cash overspending and the uncovered part of its pending payments, then adds its still-expected income. A current shortage stays visible next month instead of being clipped to zero. **BREAKING** for the spec rule "positive To Be Assigned carries".
- **Forecast allocates whole cents (F06).** Pro-rata allocation within a priority level distributes integer cents with a deterministic remainder rule, so two cents due with one available never report everything covered.
- **Coach acceptance binds to what the user reviewed (F02).**
  - Every one-tap proposal carries a `revision`, a hash of its fingerprint and amounts.
  - Accepting requires that revision. If the proposal changed, the API answers 409 `proposal_changed` with the fresh proposal.
  - Repeating an accepted revision returns the same result without applying it again.
- **Coach funding sources are validated (F03).** The target can't be its own source (422 `same_category`), and a source must be an eligible day-to-day category whose available covers the difference. Forms and the coach share the same move rules.
- **"Already paid" tells the truth (F04, F05).**
  - The paid portion of a partially paid bill appears in `paid` (marked partial) while the rest stays pending.
  - Card settlements move to a separate `card_payments` section, so the spending headline counts each purchase once.
  - The money identity is unchanged.
- **Supported planning horizon (F10).** A dated payment (a `once` schedule, or a personal debt's due month) beyond the 120-month horizon is rejected with 422 `outside_planning_horizon` instead of silently computing zero.
- **An empty coach feed is not a verdict (OS05).** It says there are no suggestions right now, never that the plan is on track.
- **Spec reconciliation (OS01–OS04).**
  - The data model points to the cumulative To Be Assigned chain and to the derived category kind.
  - The draft scenarios are limited to categories without payments.
  - Category suggestions describe the LLM-layer route, the chunked requests with per-chunk fallback, and the data actually sent to the provider.
- **Policies for F07–F09 recorded for sign-off**, not implemented here (see design):
  - unpaid past obligations (F07);
  - partial income (F08);
  - ambiguous import duplicates (F09).
- **Test hygiene.** The observability test asserts structured attributes instead of searching for a number in trace ids and timestamps. The redesign's characterization cases become desired-behavior regression tests for F01–F06 and F10.
- **Docs.** The user guide explains "Already paid" versus card payments, and the coach's empty state.

### Roadmap (next changes, from the redesign's delivery sequence)

1. **This change:** the baseline and safety fixes.
2. **`redesign-home-navigation`:** a read-oriented Home option B and five destinations (Home, Budget, Transactions, Future, Accounts). It includes the deterministic summary (M = T + L + F + U with "Needs organizing"), one priority action, up to three grouped recommendations, debts reachable from Accounts, and qualified forecast language. It requires no accounting migration.
3. **`coach-conversation-actions`:** chat persistence and resume, typed tools on the LLM layer, a preview → revision → commit → replay lifecycle, validated grouped moves, and controlled undo. It deliberately supersedes coach-proposals' "no text input" rule. The deterministic feed stays as the fallback.
4. **`future-coaching`:**
  - funded-versus-wanted and structural-gap detectors (OS06);
  - completeness-aware language;
  - the F07 overdue obligations and F08 partial-income flows;
  - locale and tone preferences (es-ES / es-AR / es-MX).
5. **`coach-proactivity`:** scheduled checks and user-controlled notifications, only after usefulness is validated.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `payment-projection`: signed initial state (F01) and integer-cent allocation (F06) in the upcoming projection.
- `month-overview`: the paid portion of partial payments (F04), card settlements reported separately from spending (F05), and the "Este mes" card showing card payments apart.
- `payment-schedules`: a supported planning horizon for dated payments (F10).
- `coach-proposals`: acceptance bound to a reviewed revision, with replay (F02); validated funding sources (F03); and the empty feed not being a verdict (OS05). It depends on the active `coach-proposals` change, which must be archived first.
- `data-model`: the To Be Assigned formula reference (OS01) and the stored flag versus derived kind (OS02).
- `budget-api` and `budget-suggestions`: draft scenarios qualified to categories without payments (OS03).
- `category-suggestions`: the LLM-layer route, chunking with per-chunk fallback, and data sent for inference (OS04).

## Impact

- **Backend:**
  - `services/projection.py` (initial state, integer allocator);
  - `services/overview.py` and `schemas.py` (partial paid items, `card_payments`);
  - `services/coach.py` and `routers/coach.py` (revision, replay, source validation through a shared move validator extracted from `routers/budget.py`);
  - `schemas.py` (once/due-month horizon);
  - a migration adding `revision` to `coach_proposal_states`;
  - tests (regressions for F01–F06, F10, and the observability assertion).
- **Webapp:**
  - the coach card sends the revision and handles `proposal_changed` by showing the updated proposal;
  - `ThisMonth` shows card payments apart from "Already paid";
  - the feed's empty copy;
  - e2e updates.
- **Depends on:** the uncommitted `coach-proposals` change on `feat/coach-proposals`. It lands first, or together in the same PR.
- **Unaffected:** budget math, rollover, card funding, the catch-up formula, income matching, debts and imports.
