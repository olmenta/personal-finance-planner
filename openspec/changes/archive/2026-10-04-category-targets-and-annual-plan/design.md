## Context

Budget math lives in `services/budget_view.py`, and after `budget-rules` it has a forward-pass chain: carry-over To Be Assigned, overspending reset, and the invariant `TBA + Σ available = Σ confirmed activity`. Categories only have name, icon and group, and nothing knows *when* money is due. Drafts copy last month's assignment.

The approved prototype (`ui-experiments/este-mes-y-pagos.local.html`, gitignored, built from the user's real budget) contains a working client-side engine for occurrences, the normal and catch-up amounts, and a priority-allocation projection. This change ports that engine to the backend and builds the three prototype screens on top.

Product decisions this implements (2026-09-30/10-01):

- Budget ≠ payment schedule; the app always computes the monthly amount.
- Coverage of future payments must be explicit.
- An annual plan with the monthly gap.
- Probable money (bonuses) is never budgeted.
- Three category kinds.
- The home screen shows what to solve now: paid, to pay, left to spend.

## Goals / Non-Goals

**Goals:**

- A user describes a payment once ("632 € September to June, day 5") and never divides by 12 again.
- The home screen answers *what do I need to solve this month* with numbers that add up to the money in the accounts.
- Any future payment that won't be covered is visible months ahead, with the amount and the month.
- One honest yearly number: fixed income versus the plan.

**Non-Goals:**

- Onboarding extraction of schedules, and coach proposals (repeated overspending, monthly plan adjustments, "skip reserved categories" in cover suggestions). These are follow-up changes that consume this one's API.
- Card charges as scheduled payments and per-account balances. They come with `accounts-and-transfers`, and the contracts here leave room for them.
- Learning estimates from real bills, i.e. adjusting an estimated amount to the average of past bills. That's a follow-up; here estimates only change how matching works.
- Multi-budget, multi-currency, debt payoff.

## Decisions

### D1: Kind is derived from payments; only "savings" is a user choice

Revised on 2026-10-04 after the first manual test: picking a category "type" in the payment editor read as choosing the *payment's* type and confused the model. Now:

- **The rule belongs to each payment** (`pattern`).
- **The category's kind is derived:** `scheduled` if it has any payment, else `savings` if the user flagged it, else `flexible`.
- **Storage:** `Category.kind` stores just that flag (`"savings"` / `"flexible"`), and the API exposes the derived `kind` plus `savings`.
- **Budget math:** none of this changes it. The kind only decides how the assignment is set (D4), the home-screen bucket (D5) and the projection priority (D6).

### D2: One `payment_schedules` table with pattern-specific nullable columns

Columns: `id, user_id, category_id, name, amount_cents > 0, pattern, months int[] (some_months), month 1–12 (annual), every_n 2–12 + start_month "YYYY-MM" (every_n; also the first month for monthly payments with a count), count (monthly, optional), once_month "YYYY-MM" (once), day 1–31 (optional), estimated bool`.

The API validates each pattern with a Pydantic discriminated union, so an `annual` schedule without `month` is a 422 `invalid_schedule`, never a half-valid row.

*Alternatives:*
- RFC 5545 RRULE strings. Rejected; overkill, hard to map to the sentence-style editor, and every pattern here is month-granular.
- A JSON `spec` column. Rejected; typed columns keep validation and migrations honest.

Patterns: `monthly` (optional `count` from `start_month`), `some_months`, `annual`, `every_n`, `once`, `no_date` (an annual goal: amount per year, no occurrences). A savings goal is always *for a future expense*: it's a `once` payment on its date, never a separate "have X saved by a date" pattern (proposed and rejected on 2026-10-04).

### D3: Occurrences and amounts are pure functions (`services/schedules.py`)

- **`occurs(schedule, month) -> bool`** is month-granular. The day is only used for ordering, display and the overview's paid/pending split.
- **Normal amount of a schedule in month M:**

  | Pattern | Normal amount |
  |---|---|
  | `monthly` | amount (0 after its count runs out) |
  | `some_months` | amount × number of months ÷ 12 |
  | `annual` | amount ÷ 12 |
  | `every_n` | amount ÷ N |
  | `no_date` | amount ÷ 12 |
  | `once` | 0 (the catch-up amount covers it) |

- **Category normal:** the sum over its schedules.
- **Catch-up for category c in month M, given `saved` (its rollover at the start of M, from the `budget-rules` chain):**

  ```
  catch_up = max over j in M..H of (Σ payments(M..j) − saved) / (j − M + 1), floored at 0
  H = max(M + 11, month of the latest `once` payment), capped at 10 years
  ```

  It is the minimum constant monthly set-aside for which no payment goes uncovered. A future expense, even years away, is spread over every month until it. Once the user catches up, the amount falls back to the normal amount by itself.
- **Suggested monthly amount:** `max(normal, catch_up)`, rounded **up** to the cent.

This mirrors the prototype engine, and its fixtures (colegio: normal 582,92 €, catch-up 721,40 € in October with nothing saved) become unit tests.

### D4: Categories with payments are assigned their computed amount

Revised on 2026-10-04: a payment of 40 €/month next to a hand-typed 32 € assignment made no sense. Now:

- **Assigned automatically:** a category with payments is assigned `max(normal, catch_up)` when the month is materialized (state `confirmed`, not a draft), including in the first month.
- **Kept in sync:** it is recomputed in the current and later materialized months whenever one of its payments changes (walked in order so each month sees the previous balance). Past months keep their history.
- **Never typed:** `PUT /budget/{month}/assignments/{id}` returns 409 `assignment_from_payments`, and the row shows the amount read-only with "From your payments".
- **Moving money is still allowed**, as an explicit decision; the projection flags any payment it leaves short.
- **Everything else** keeps copying the previous month as a draft.

The view exposes `normal_cents` and `catch_up_cents` (null for categories without payments).

### D5: The month overview partitions Σ available exactly

`GET /overview/{month}` uses "today" in Europe/Madrid. Past months count everything as due and future months nothing.

Matching payments to transactions: the category's confirmed spending in the month is allocated to its occurrences in day order (a missing day counts as day 1). An occurrence is paid when:

- the allocation covers its amount; or
- it is `estimated` and any spending was allocated to it (the bill arrived; the difference is ordinary over- or under-spending).

Buckets, per category with available `a` (from the budget view):

| Kind | Rule |
|---|---|
| flexible | `a ≥ 0` → **left to spend**; `a < 0` → **overspent** |
| savings | `a ≥ 0` → **saved**; `a < 0` → **overspent** |
| scheduled, with `p` = pending amount this month | `a ≥ p` → **to pay covered** `p`, **saved** `a − p`; `0 ≤ a < p` → **covered** `a`, **short** `p − a`; `a < 0` → **overspent** `−a`, **short** `p` |

The sum is `covered + left + saved − overspent = Σ available`. The response also returns `accounts_cents` (Σ confirmed activity up to the month's end) and To Be Assigned, so the check `accounts = covered + left + saved + TBA − overspent` is exact by construction, not a UI approximation. "Already paid" is the month's confirmed spending: paid occurrences are listed individually, and flexible categories as spent totals.

### D6: The projection allocates expected fixed income by priority (`services/projection.py`)

`GET /plan/upcoming?from=YYYY-MM` returns 12 months.

- **Month M (current):** reports the overview's real coverage.
- **Months M+1..M+11:** simulated from the projected end-of-M state.
  - Starting state:
    - scheduled categories keep `max(0, a − pending)`;
    - savings keep `a`;
    - flexible start at 0 (assumed spent; leftovers are a bonus, never counted on);
    - To Be Assigned carries if it's positive.
  - Each simulated month:
    - money = expected fixed income + carried To Be Assigned;
    - it is allocated in priority order: (1) payments due that month, (2) flexible budgets (each flexible category's current assignment), (3) catch-up set-asides for later payments, (4) `no_date` goals;
    - within a level that doesn't fit, allocation is pro-rata;
    - leftovers stay unassigned and carry.
  - A payment is at risk when its category can't cover it that month.

Output per month:

- occurrences with `covered` (bool) and `short_cents`;
- day-to-day funded (assigned versus budget);
- set-aside funded versus wanted;
- unassigned left.

This is the prototype's `simulate`, which showed on the user's data that dated payments stay covered while the structural gap surfaces as set-asides that can't be funded. That is why both ratios are part of the contract.

When no expected income is known, the projection returns schedule totals with `income_known = false` and no coverage (never a guess).

### D7: The annual plan is a 12-month window, not a calendar year

`GET /plan/summary?from=YYYY-MM` returns:

- `income_cents`: expected fixed income × 12;
- `scheduled_cents`: Σ occurrences in the window;
- `flexible_cents`: Σ flexible assignments of M × 12;
- `goals_cents`: Σ `no_date` amounts;
- `gap_cents` and `gap_monthly_cents`.

A rolling window matches the timeline and avoids a January cliff.

`GET/PUT /plan/income {expected_monthly_cents}` reads and writes `income.expected_monthly_cents` through `PreferencesStore`, the same field onboarding fills. Bonuses have no field by design.

### D8: UI follows the prototype, built from Olmenta primitives

- **Dashboard (`/`):** an "Este mes" panel (already paid, to pay with ✓/⚠ chips, left to spend) plus a side column: saved for the future (grouped chips), unassigned, the accounts check line, and the next 3 months with "See all". Recent transactions stay below. The old BalanceCard-first header gives way.
- **"Próximos pagos" (`/upcoming`, sidebar entry; on mobile reached from the dashboard):** annual summary cards, then the 12 expandable month rows with the two funding bars.
- **Schedule editor:**
  - a dialog opened from a budget row ("Set up payments") and from Settings → categories;
  - a kind selector (Day-to-day / Scheduled / Savings);
  - the payment list with per-payment normal amounts;
  - a sentence-style form with a pattern picker, month chips and a day field;
  - normal and catch-up cards, with the balance chart from the prototype (bars; shortfall uses `--warning`, never `--expense`, because it's a projection, not money that left).
- **Copy** stays English placeholder until next-intl (the prototype's Spanish copy is the target wording). The sparkle icon stays reserved for the coach; none of these screens is the coach.

### D9: Today is computed server-side in Europe/Madrid

The overview's paid/pending split and the projection's month M use the server's clock in Europe/Madrid, the same zone as calendar months. Tests inject the date.

## Risks / Trade-offs

- [Matching by category and amount mislabels a payment (two bills in one category, one arrives early)] → day-order allocation is deterministic, estimated bills match on arrival, and the list shows amounts so the user can spot it. A per-transaction link to an occurrence is a possible later refinement.
- [Projection assumptions (flexible spent in full, a fixed monthly income) differ from reality] → stated in the UI ("If you keep your current plan…"), recomputed on every read, and never used to move money.
- [No expected income for users who skipped the onboarding question] → projection coverage is hidden behind an inline "Add your monthly income" prompt; totals still show.
- [Drafting changes (computed amounts) surprise users who liked copying last month] → only scheduled categories change. The row shows "Suggested from your payments", and edits win as today.
- [More work on every budget read] → schedules are loaded once per request, and occurrences are O(schedules × 12). Negligible next to the chain's three grouped queries.

## Migration Plan

1. Alembic: `categories.kind` (varchar, default `'flexible'`, not null) and the `payment_schedules` table with an FK to categories and an index on (user_id, category_id). The downgrade drops both.
2. Backend: schedules service + CRUD → drafting → overview → projection + summary + income. Each is testable on its own.
3. Webapp: BFF routes and API client → schedule editor → dashboard "Este mes" → "Próximos pagos".
4. Rollback: revert the code and downgrade. With the old code, categories without schedules behave exactly as before.

## Open Questions

- Sidebar label and icon for "Próximos pagos" are settled at implementation, following the existing shell conventions.
