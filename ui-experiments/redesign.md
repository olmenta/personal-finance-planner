# Olmenta conversational redesign implementation specification

**Version 2 — grounded in the existing implementation**  
**Review date:** October 14, 2026  
**Audience:** Engineering, Design, QA  
**Repository:** `/Users/seboraid/playground/seboraid/personal-finance-planner`  
**Baseline:** HEAD `eadb70f` plus the local working tree inspected on the review date.

## 1. Decision and scope

**Keep the financial engine. Build a simpler conversational experience on its existing services, with narrowly scoped corrections and an action-safety layer.** Do not implement the replacement ledger, category partition, or monthly rollover rules proposed in version 1.

Olmenta helps people without financial education answer **“How am I going to pay for everything I need to pay for?”** The product direction remains a refreshed Home with conversation continuity, operational widgets, grouped recommendations, and five destinations: Home, Budget, Transactions, Future, and Accounts.

This revision distinguishes:

- **Implemented:** verified in source; tests are identified where available.
- **Local work in progress:** present in modified or untracked files, not evidence of deployment.
- **Reproduced finding:** observed through an isolated characterization test.
- **Design limitation:** an explicit simplification or missing capability requiring a product decision.
- **Proposed change:** future work, not current behavior.

The Coach service/router/tests and its state migration are local work in progress. `budget_view.py`, models, schemas, Home, Upcoming, and Coach components also have local changes. This review did not modify application source or these changes. OpenSpec documents provide intent; executable code and tests establish implementation status. Codegraph returned incomplete relationships in this workspace, so relevant behavior was checked directly in the source.

### Validation performed

- Full backend suite against the dedicated local PostgreSQL `olmenta_test` database: **369 passed, 1 failed**, 23.20 seconds, no skipped tests reported.
- The failed test was `test_request_values_never_exported`: the string `4520` occurred inside an exported timestamp, not an identified request field. Its isolated rerun passed. This is evidence of a brittle substring assertion, not demonstrated financial-data leakage.
- Ten additional characterization cases were executed in two runs outside the repository. They establish observed behavior, not that the desired behavior is correct. See Section 7.
- Existing Playwright tests were inspected, not executed. No UI code was changed. No live model evaluations, production data inspection, load test, or concurrent-request test was performed.
- Existing tests disable live model calls. Database fixture changes roll back per test. No production or development database was used for the tests.

## 2. What version 1 must no longer require

| Version 1 assumption | Verified implementation and revised instruction |
| --- | --- |
| Introduce a new financial ledger and persist allocation entries | Reuse `Transaction`, `BudgetMonth`, `BudgetAssignment`, and derived views. Add narrowly scoped action records only where required for confirmation/replay/undo. |
| Carry negative category balances forward unchanged | Categories carry only positive availability. Previous cash overspending reduces next month's TBA; credit overspending remains debt. Preserve this tested rule. |
| Unfunded card purchases must not make categories negative | The current category becomes negative and reports `credit_overspent_cents`. The overview corrects the cash partition accordingly. Preserve the existing representation. |
| All card payment reserves stay in saved money | A card category without a plan is saved; with a payment/debt schedule, its covered current obligation participates in “to pay.” Preserve this distinction. |
| Assignments always represent fully backed cash | Assignments can exceed actual money and make TBA negative. The UI must explain overassignment rather than declare every assigned amount funded. |
| Future contribution is always `(target - reserve) / remaining dates` | Reuse the cumulative multi-payment catch-up calculation, with current-month-inclusive monthly slots. Do not replace it with a one-payment shortcut. |
| All calculation uses integer cents internally | Persisted and ledger values are integer cents. Schedules, projections, and debt simulations use floating-point intermediates with boundary rounding. Address reproduced rounding defects locally. |
| Future planning and recurring income need to be created | Both are implemented, including extra salary payments, schedule matching, and a 12-month projection. |
| No goals capability exists | Savings categories and annual `no_date` targets exist. A general goal-management product is not established; do not remove existing target support. |
| CSV supports 10 MB/10,000 rows and stores raw files temporarily | Current limits are 2 MiB/2,000 rows. Raw files are parsed in memory and not persisted. Preserve this unless a separate capacity change is approved. |
| CSV duplicates are reviewed as candidates | Current hashing automatically skips matching rows. Ambiguous duplicates need a targeted improvement, not a new import engine. |
| Every operation already has history, versioning, idempotent replay, and undo | These are proposed additions. Transactions are edited in place and can be hard-deleted; the current data model is not an immutable event ledger. |
| Coach is a general conversational AI | The current Coach is deterministic rules plus actions. AI is implemented in onboarding and categorization; free-form operational coaching is still missing. |

## 3. Current financial engine to preserve

### 3.1 Authoritative seams

| Area | Source and role |
| --- | --- |
| Budget | `backend/app/services/budget_view.py`: `month_math`, `month_chain`, `build_view`, `materialize_month`, `cover_suggestions` |
| Home partition | `backend/app/services/overview.py`: `match_payments`, `build_overview` |
| Payment arithmetic | `backend/app/services/schedules.py`: `occurs`, `normal_amount`, `catch_up`, `amounts` |
| Forecast | `backend/app/services/projection.py`: `_allocate`, `upcoming`, `summary` |
| Expected vs received income | `backend/app/services/income.py`: `month_income` |
| Debt planning | `backend/app/services/debts.py`: rates, payment target, ordering, simulation; editor preview mirrored in `webapp/src/lib/debts.ts` |
| UI interpretation | `webapp/src/components/plan/ThisMonth.tsx`: net left-to-spend and account reconciliation |

### 3.2 Budget arithmetic

For an ordinary category and month `m`:

```text
available(c,m) = assigned(c,m) + rollover(c,m) - spent(c,m)
rollover(c,m)  = max(0, available(c,m-1))

TBA(m) = TBA(m-1)
       + signed uncategorized cash/bank activity(m)
       - sum(assignments(m))
       - cash overspending(m-1)
```

Before the first materialized budget month, confirmed cash/bank activity seeds TBA. The engine walks calendar months, including unopened months with zero assignments. Do not replace this with “previous database row” logic.

Income for reporting is confirmed, positive, uncategorized, non-transfer cash/bank activity. A categorized inflow is a refund. An uncategorized cash outflow already reduces TBA and is separately surfaced for categorization. Card opening debt never increases TBA.

Only confirmed transactions affect these calculations; staged imports do not. All non-credit accounts participate, including archived accounts. There is no implemented arbitrary `included` account flag. `accounts_cents` is confirmed activity through the selected month's end, not a live bank balance guarantee.

### 3.3 Cards

The monthly algorithm applies cash activity first, then funds cards in account creation order. This is a deliberate monthly simplification, not transaction-by-transaction chronological allocation.

```text
pool(c) = max(0, assigned + rollover - cash_spent + card_refunds)
funded(c,card) = min(card_spend(c,card), remaining pool)
move_to_card_payment = funded - card_refunds
credit_overspent(c) = total card_spend - total funded

available(card_payment) = assigned + rollover
                        + derived card funding moves
                        - card payments
```

Funding moves are derived, not stored transactions. Transfers are excluded from ordinary category spending; transfers into a credit account consume its payment category.

The budget invariant is:

```text
TBA + sum(category available) + sum(credit overspent)
    = confirmed cash/bank activity through month end
```

At month rollover, negative availability resets to zero. Only the cash portion is deducted from next month's TBA; the credit portion remains card debt. Existing tests cover mixed cash/card overspending, refunds, payment consumption, multiple cards, and generated histories.

### 3.4 Exact mapping of the requested identity

The actual overview contract is:

```text
accounts_cents = covered_cents
               + left_to_spend.total_cents
               + saved.total_cents
               + to_be_assigned_cents
               - overspent_cents
```

`overspent_cents` excludes credit overspending, which represents debt rather than missing cash. The current frontend already folds this into the spending number. Therefore the four-part user-facing identity can be retained **without rewriting the engine**:

```text
M = accounts_cents
T = covered_cents
L = left_to_spend.total_cents - overspent_cents
F = saved.total_cents
U = to_be_assigned_cents

M = T + L + F + U
```

Do not substitute `to_pay_total_cents` for `T`: the former is the full pending obligation; `covered_cents` is its allocated coverage. “Already paid” is a flow, not part of the account-balance identity.

Scheduled category availability first covers this month's pending payments; excess becomes saved. Savings and card payment categories without schedules are saved. Card payment categories with a schedule follow the scheduled-payment branch. Flexible positive balances contribute to left-to-spend; deficits feed overspending.

A valid identity does not by itself establish affordability. Negative TBA, uncovered payments, overdue items, missing transactions, and card debt must influence explanatory status.

### 3.5 Evidence from the original screenshots

Observed prototype values: €55.00 covered, net spending balance −€1,004.53, saved €577.96, unassigned €4,406.12, accounts €4,034.55. They reconcile exactly:

```text
55.00 - 1,004.53 + 577.96 + 4,406.12 = 4,034.55
```

These are observed screenshot values, not verified live account data. All scenarios below are synthetic. The screenshots also show duplicate rent recommendations and long category lists. The new UI should remove repetition, not reinterpret the accounting.

## 4. Budgets, future expenses, and projections

### 4.1 Assignments and deviations

Opening a month materializes it. Scheduled categories receive their computed assignment immediately, marked confirmed. Other categories copy the previous month's assignment as a draft; a first/new category starts at zero. Draft assignments already participate in calculations.

`PUT /budget/{month}/assignments/{category_id}` rejects direct assignment for categories with schedules (`assignment_from_payments`). Change their payment schedules or explicitly move money instead. Budget moves edit source and destination assignments within the request transaction, bounded by source availability. A source assignment may become negative when using its rollover.

`cover_suggestions` handles the largest deficit first, consumes positive TBA first, then the largest eligible donor. It prevents suggestions from sharing the same euros and protects card payment categories. A suggestion may only partially cover a deficit; it does not combine all possible sources in one result. Savings and scheduled categories are not generally protected donors by this helper, so preview their consequences rather than silently treating them as free money.

Schedule changes recompute current and later materialized assignments, leaving past assignment amounts unchanged. Reads recompute normal/catch-up indicators. Transaction edits do not call `refresh_computed_assignments`; do not describe every transaction as automatically rewriting saved future assignments. Any automatic catch-up proposal must expose the current recommendation separately from the stored assignment.

Reading Budget/Overview/Coach can materialize a month. The redesigned Home must not prefetch or iterate over additional budget months in a way that unexpectedly writes plans. Future simulation uses the current view and does not materialize every simulated future month.

### 4.2 Contribution formulas already implemented

Supported payment patterns: monthly, finite monthly, selected months, annual, every N months, once, and `no_date` annual targets. Income supports dated recurrence patterns, not `no_date`.

Normal monthly amounts:

| Pattern | Normal contribution |
| --- | --- |
| Monthly | Amount; finite monthly only while its occurrence is active |
| Selected months | Amount × number of selected months / 12 |
| Annual or undated annual target | Amount / 12 |
| Every N months | Amount / N |
| Once | Zero normal amount; funded through catch-up |

For all payments within a category, the catch-up contribution is the largest cumulative requirement over the horizon:

```text
P(j) = sum of payments from current month m through month j
S    = category rollover entering month m

catch_up = max(0, max_j((P(j) - S) / (j - m + 1)))
suggested = ceil(max(normal, catch_up))  # cents
```

`normal_cents` uses `round`; catch-up and suggestion use `ceil` with a small floating-point tolerance. The horizon is at least twelve months, extends to later one-off payments, and is capped at 120 months.

This handles multiple obligations sharing one category. Do not split the reserve into persistent per-payment lots merely to present a widget.

**Example:** a €600 annual payment with six inclusive monthly slots left and €150 rollover needs €75 per month. For a full annual cycle, the normal amount is €50. The widget should explain the €25 increase using the existing service output.

The model is monthly: payment day orders matching and supports late indicators, but it does not decide whether the current month's contribution slot is still available. Version 1's daily opportunity rule is deferred, not silently substituted.

### 4.3 Expected income

`IncomeSchedule` already supports multiple recurring sources and extra payments. `month_income` derives expected occurrences from rules and matches actual transactions on each read:

1. Match payee first. A single inflow may cover multiple occurrences when it reaches 90% of their running combined amount.
2. For schedules without a payee, match remaining inflows by amount within 10%, or 25% for estimated income; choose the closest fit.
3. Matched occurrences are received; otherwise past-month occurrences are missed, current ones more than three days overdue are late, and the rest are pending. Missing day means month end.

Matching is derived, not a persisted `IncomeOccurrence` table. Linking currently works through the transaction payee. Opening balances are excluded from matching. Expected schedules never fund actual TBA; actual transactions do.

### 4.4 Forecast and annual plan

`upcoming` returns the selected month plus eleven future months. The selected month reports overview coverage. The simulation then uses saved scheduled reserves and TBA, adds the selected month's still-expected income, and allocates each future month's expected income in order:

1. Payments due now.
2. Current flexible category assignments.
3. Contributions for later dated payments.
4. Undated targets.

If a priority level cannot be fully funded, allocation is proportional within that level. Remaining unassigned money carries; later simulated uncovered payments reduce the next simulated balance. No real money is moved.

Without income schedules, future coverage is unknown (`None`), not automatically safe or unsafe. The projection is conditional on expected income. It is not daily bank liquidity analysis: salary on day 28 may fund a payment on day 1 in the same simulated month.

`summary` compares twelve months of expected income with scheduled payments, flexible assignments × 12, annual undated targets, and a share of one-off payments beyond the window. It expresses a structural annual plan gap, not a current account balance or daily solvency guarantee.

A zero payment `short_cents` does not mean the whole plan is on track. Flexible spending and future contributions may be underfunded; an existing test explicitly covers that distinction.

### 4.5 Debt capabilities to retain

Debt plans support card, loan, and personal debt. Required payments use existing `PaymentSchedule` rules. The service computes rate-based repayment targets, prioritizes debts by its existing rate/order rules, simulates extra payments, and rolls released payments to the next debt, up to 120 months.

Rates use the current explicit convention (annual divided by twelve); loan installments already include interest in the simulation. Keep the debt service and its editor preview aligned. Moving navigation into Accounts/Future must not remove debt editing or replace its calculations with coach arithmetic.

## 5. Current Coach rules and limits

The working-tree Coach is deterministic. It does not call an LLM. It reads budget, overview, projection, and income services on demand; no background continuous analyzer or notification scheduler was found in this flow.

| Kind | Current trigger | Action |
| --- | --- | --- |
| `late_income` | Expected income is late after the three-day grace period | Add income or link an existing transaction |
| `late_debt_payment` | A debt-category payment is marked late by the overview | Open debt plan |
| `short_months` | Future months have payment `short_cents > 0`, with known income | One grouped warning linking to the first affected month |
| `overspending` | Flexible category has three prior materialized months, negative available in at least two, and suggested increase ≥ €10 | Raise assignment |
| `unassigned` | TBA ≥ €10 | Open Budget |
| `underspending` | Flexible category spent less than assigned in all three prior months, and proposed decrease ≥ €10 | Lower assignment |

Spending suggestions use average spending over three months, rounded upward to €5 increments. Scheduled categories do not receive these spending proposals. Alternative sources are at most three flexible categories, each individually able to cover the entire increase.

Priority is the table order above, then descending proposal amount. Fingerprint is kind + subject + month. Dismissal lasts seven days. Accepted fingerprints are hidden for that month, irrespective of later material changes. State stores no amounts.

Frontend actions currently raise/lower immediately, except for source selection when offered. There is no general preview/confirm/undo flow, no general chat composer, and no long-lived operational conversation model. The E2E Coach test explicitly expects no text box.

**Reuse:** detectors, urgency, source calculations, current view services, Pydantic AI routing, and the persisted onboarding interview pattern as an architectural reference.

**Add:** incomplete-budget diagnosis before overspending language, grouped category resolution, warnings for insufficient flexible/future funding, contextual explanation, operational conversation persistence, and safe typed actions. Do not replace deterministic financial rules with model decisions.

## 6. Data, import, and capability inventory

| Capability | Verified status | Redesign work |
| --- | --- | --- |
| Accounts/categories/transfers/refunds | Implemented, with tests | Reuse API and preserve history behavior |
| Budget, rollover, moves, cover suggestions | Implemented, with generated-history invariants | Explain clearly and compose existing operations |
| Schedules/catch-up/income/projection | Implemented, with tests | Add understandable status and repair specific edge cases |
| Debt plans | Implemented, with unit/API/E2E source coverage | Preserve and make reachable in new navigation |
| AI onboarding | Persisted transcript, extraction and setup proposal; tested | Reference pattern, not a substitute for general Coach chat |
| AI categorization and human review | Implemented with fallback | Reuse; avoid pretending confidence is calibrated probability |
| Coach proposals | Local work in progress, backend tests run | Strengthen acceptance safety and add conversation |
| General conversation, action journal, snapshot version, replay and undo | Not found as general Coach capabilities | Add minimal separate models/services |
| Advanced goals | Not established as complete feature | Preserve savings and `no_date`; defer advanced goal product |
| Locale AR/ES/MX | User locale field exists; strings mostly English, amounts es-ES/EUR, clock Madrid | Add explicit locale/tone handling; don't imply multi-currency exists |
| Authentication | Current dependency returns a seeded development user | Production identity is a rollout gate, not a finished feature |

Current persistence includes `User`, `Account`, `CategoryGroup`, `Category`, `PaymentSchedule`, `IncomeSchedule`, `Debt`, `DebtSettings`, `CoachProposalState`, `Payee`, `ImportBatch`, `Transaction`, `OnboardingSession`, `UserPreferences`, `BudgetMonth`, `BudgetAssignment`, and `LlmUsage`. Derived availability, TBA, payment occurrence matching, and forecasts are not stored balances.

### Import contract

The existing ingestion port supports BBVA XLSX, Sabadell XLS, and a custom CSV template with required `date`, `amount`, `description` and optional category/balance. It is not an arbitrary CSV column-mapping wizard. Dates follow supported ISO or day/month/year parsing.

Pipeline: parse → normalize → deduplicate → AI suggestions → staged transactions → human review → confirm. Limits are 2 MiB and 2,000 rows. Raw bytes are not persisted. A staged batch can be resumed or discarded. Confirmation makes its rows financial activity. A second confirmation returns 409; it does not replay the original response.

Deduplication uses account/date/amount/external reference or description, with running balance when available. Identical ambiguous rows are automatically skipped, not placed in a review queue. Review can change category, payee, note, and transfer decisions. An uncategorized confirmed row remains reviewable; the current backend does not require every row to have a category before confirming.

The AI fails open to manual review. Transaction descriptions are sent to the configured categorization provider; document that actual data flow. Do not claim all financial text stays inside the app merely because Coach rules are local. Financial text should remain excluded from general telemetry.

## 7. Findings and proposed targeted corrections

All source locations below refer to the inspected working tree. Priorities describe impact on the redesign, not an instruction to rewrite the engine. Characterization tests used synthetic data and were executed in task scratch space outside the repository. Their scenarios and observed results are recorded below.

### F01 — Projection discards the initial deficit — P1, reproduced

**Source:** `services/projection.py:117–142` (all service paths are under `backend/app`).

A €100 current obligation with no cash creates TBA −€100. With a €100 salary only from next month, next month's €100 payment is reported fully covered. The simulation initializes TBA with `max(0, TBA)` and drops the current deficit. Assigned amounts can also be labeled funded while TBA is negative.

**Change:** Reconcile the initial simulation state with real cash, overassignment, pending current outflows, and selected-month cash overspending. Do not simply subtract every indicator: some describe the same shortfall. Derive and test one conservation equation; retain the existing future priority allocator. Until corrected, show an unresolved current funding deficit and do not issue an unqualified “on track” status.

**Acceptance:** A current shortage must remain visible in the forward scenario or invalidate its coverage claim; no money created by clipping a negative. Preserve existing healthy-plan fixtures.

### F02 — Acceptance can apply a different amount from the displayed proposal — P1, reproduced

**Source:** `services/coach.py:313–354`; `schemas.py:893`.

A proposal displayed a €230 assignment. A historical expense changed the recomputed suggestion to €330 under the same fingerprint. Accepting the old fingerprint returned 200 and applied €330. Recalculating on acceptance is useful, but not sufficient to bind consent to the reviewed change.

**Change:** Add an expected financial revision or proposal-content hash, an explicit before/after preview, and a conflict response when the proposal changes. Store replayable operation result for retry safety. Keep all amounts server-generated.

**Acceptance:** The user either applies exactly the reviewed change or sees an updated preview requiring confirmation. Repeated acceptance returns the same recorded result after implementation of replay.

### F03 — Coach accepts the target category as its own funding source — P1, reproduced

**Source:** `services/coach.py:339–351`; compare `routers/budget.py`'s `same_category` guard.

Passing the target ID as `from_category_id` returned 200. The source decrement was overwritten when the target assignment was set, reducing TBA by €30 despite declaring the category as its own source.

**Change:** Reuse shared move validations, reject identical source/destination, and enforce server-side source eligibility. UI suggestions alone are not an authorization or validity check. Existing accept code also lacks the source-kind restrictions used by its detector; cover that in regression tests.

**Acceptance:** Self-source and invalid source requests make no changes. Valid reallocations preserve total assigned money and M; TBA-funded raises change TBA by the reviewed amount only.

### F04 — Paid summary omits partial scheduled payments — P2, reproduced

**Source:** `services/overview.py:111–127`.

For a €100 scheduled bill with €40 paid, “paid” reports €0 while pending correctly becomes €60. The partial allocated amount is neither a paid occurrence nor leftover spending.

**Change:** Include the paid portion without treating the obligation as settled. Clarify paid amount vs payment completion.

**Acceptance:** Show €40 paid and €60 outstanding, retain coverage identity, and keep full-payment/estimated-payment tests meaningful.

### F05 — Paid summary counts a card purchase and settlement together — P2, reproduced

**Source:** `services/overview.py:107–127`; `services/budget_view.py:383–386`.

A €60 card purchase followed by a €60 settlement produces €120 in the overview's paid total. Both category spending and payment-category transfer consumption enter the aggregation. This does not itself break the balance identity, but the current headline can be interpreted as double spending.

**Change:** Define separate consumption and debt-settlement totals, or a clearly labeled payment-activity breakdown. Do not modify the card funding engine to fix a presentation aggregate.

**Acceptance:** The spending headline counts the purchase once; settlement remains discoverable without inflating consumption.

### F06 — Fractional-cent projection can hide a shortage — P2, reproduced

**Source:** `services/projection.py:30–35` and `_occurrences`.

Two payments of one cent share one cent proportionally. Each gets 0.5 cents; rounding each shortage with `round(0.5)` yields zero, so both are marked covered despite one missing cent.

**Change:** Allocate integer cents with a deterministic remainder rule within each priority group, or conservatively compute coverage before rounding. Reconcile displayed aggregate shortage with available cents.

**Acceptance:** Two cents due with one available cannot report all payments covered. Existing realistic projection fixtures remain stable unless a documented rounding correction explains the difference.

### F07 — Unpaid one-off obligations disappear next month — P2, reproduced design gap

**Source:** `services/overview.py:56–73`; `services/schedules.py:occurs`.

An unpaid October-only €100 payment appears in October and disappears from November's pending list. Occurrences are derived from the selected month's rules; an overdue obligation registry is not implemented.

**Change:** Initially surface unresolved prior-month obligations with a link and explicit limitation. Decide how users confirm paid, rescheduled, or canceled obligations before introducing minimal exception persistence. Do not make old obligations paid just by rolling the month.

**Acceptance:** The unresolved item stays visible or is explicitly carried to an overdue review until resolved. Do not replace category rollover rules.

### F08 — Partial income is treated as received — product policy, reproduced

**Source:** `services/income.py:91–172`.

A €100 payment from a payer with an expected €1,000 salary marks the occurrence received and leaves `still_expected_cents = 0`. Any matched transaction establishes receipt; the difference is reported separately. This also supports intentionally lower salary amounts, so it is not automatically a defect.

**Change:** Ask whether the difference is final, still expected, or canceled. Preserve the existing “salary arrived lower” behavior as one explicit choice. Define installment accumulation before altering matching.

**Acceptance:** A final lower salary does not invent future income; an explicitly partial salary can retain the confirmed remaining expectation without changing real TBA.

### F09 — Ambiguous CSV duplicates can remove legitimate transactions — P2, reproduced limitation

**Source:** `services/import_batch.py:33–78`; `ingestion/custom_csv.py`.

Two real coffees with the same date, amount, and description, without balance/reference, have the same hash and collapse. Existing tests intentionally verify duplicate collapse.

**Change:** Keep high-confidence exact bank-reference deduplication. Expose ambiguity and a keep-both decision for insufficient identifiers, retaining re-import protection.

**Acceptance:** A user can keep two legitimate identical purchases without duplicating them on a later re-import. Update the deliberate deduplication contract explicitly.

### F10 — Payments beyond the horizon receive a zero contribution — P2, reproduced limitation

**Source:** `services/schedules.py:80–87`; `schemas.py:OnceSchedule`.

A one-off payment in October 2037, viewed from October 2026, returns `(normal, catch_up, suggested) = (0, 0, 0)` because it is outside the 120-month horizon. Input accepts the date.

**Change:** Expose “outside planning horizon,” validate the supported range, or extend the algorithm in a separate change. Zero must not imply no funding is needed.

**Acceptance:** An accepted out-of-horizon payment is clearly identified and cannot silently produce a safe status.

### Additional risks and deliberate simplifications

- Monthly forecasts cannot guarantee payment-day liquidity. Keep the monthly model and qualify copy; a daily overlay is optional later work.
- `match_payments` matches aggregate category spending in due-day order, not explicit transaction-to-bill links. Estimated bills count as paid after any matched spending. Explain this and validate with users before changing it.
- Schedule rules are current records, not versioned historical occurrences. Past assignments are preserved, but past interpretation can change after editing a schedule. A full immutable history is not part of the current contract.
- Coach `short_months` ignores underfunded future contributions and flexible budgets when payment shortages are zero. Add a distinct detector using existing funded/wanted fields.
- Three months of zero/incomplete budgets can be misread as habitual overspending. Add a completeness check or neutral explanation before behavioral language.
- Sequential guards are not proven concurrent safety. No general operation idempotency key or financial version/row lock was found for budget mutations. Add tests before claiming concurrent guarantees.
- Accepted fingerprints suppress changed recommendations for the month; evidence-aware reopening needs a product rule.
- The observability test should assert structured sensitive attributes, not search a short number in trace IDs and timestamps.

## 8. Minimal target architecture

```text
Home / chat / operational widgets / existing forms
                         |
                   Next.js BFF
                         |
           typed Coach orchestration and preview
                         |
       existing budget / schedules / income / import / debt services
                         |
           existing models and financial calculation engine
```

The model may understand intent, request data, select a supported widget, and explain results. All authoritative amounts, coverage, sources, and mutation validation remain in deterministic server code. Use the existing `app/llm` logical routes and required eval workflow; do not call a provider SDK from a new Coach service.

### Reuse existing endpoints

- `GET /budget/{month}`, assignment PUT, budget moves, and suggestion confirmation.
- `GET /overview/{month}`.
- `GET /plan/upcoming?from=YYYY-MM` and `/plan/summary?from=YYYY-MM`.
- Payment schedules, income schedules, `/income/{month}`, debts, transactions, and import APIs.
- Working-tree `/coach/proposals`, dismissal, and acceptance after safety improvements.

Do not build a second `/budget/snapshot` calculator. A Home response adapter may compose current outputs and expose consistent versions, quality status, and links.

### Add only required operational persistence

Proposed additive entities: general Coach conversation/messages, a proposal preview bound to a financial revision/content hash, and an action record with user, command, idempotency key, before/after values, status, and result.

Do not replace `BudgetAssignment` with a new accounting ledger. Extract shared validated assignment/move operations if needed so forms and Coach enforce the same contract. Grouped changes run atomically. Undo is a validated inverse action when subsequent edits allow it, not a destructive history rewrite. Existing transaction edit/delete behavior should remain unless separately redesigned.

Required action lifecycle:

```text
Intent → deterministic proposal → visible before/after preview
       → user confirmation → version and source validation
       → atomic application → recorded result → optional validated undo
```

Concurrent different actions must not both spend the same availability. Define locking or financial revision checks at a shared mutation boundary; idempotency alone only handles retries of the same action.

## 9. Home and widget specification

Home option B refreshes the summary on entry and preserves conversation history and pending task references. Avoid repeated greeting messages. Store the draft input and restore context after opening details. Old proposals remain readable but cannot execute without current validation.

```text
[Home | Budget | Transactions | Future | Accounts]
October · Data updated [time] · [Review data]

Coach: Two categories need funding before I can give you a reliable amount.
[Paid this month] [Still to pay: covered / short]
[Left to spend: Needs organizing] [View exact breakdown]
[Review 2 adjustments] [Later]
[Future: monthly contribution needs attention] [Review plan]
[Resume conversation]
[Ask or record something…] [Send]
```

The wireframe is synthetic, with no implied live values. One priority recommendation above the fold; up to three groups, details on demand. Remove the duplicated banner/sidebar recommendation. Keep full categories in Budget, activity in Transactions, future commitments in Future, and debts/accounts accessible through the new structure.

Widgets reuse server fields:

- **Month:** accounts, net left-to-spend mapping, obligation total, covered total, saved, TBA, freshness, incomplete-data reasons.
- **Adjustment:** actual source, affected assignments, available balances before/after, impact on current/future coverage, Confirm/Edit/Cancel.
- **Future:** due rules, normal/catch-up/stored assignment, rollover reserve, funded/wanted amounts, conditional forecast, horizon limitations.
- **Income:** expected, received, difference, pending/late/missed, explicit handling of partial receipt.
- **Import:** current staged batch, review decisions, duplicates/skips, exact confirmation scope and recoverable state.

No accounts → guided setup. Negative TBA or unresolved deficit → “Needs organizing,” with exact detail. Unknown income → “Future coverage unknown.” Stale/partial data → explain limits. AI outage → deterministic views and forms. No humor for urgent shortfalls or distress.

Support keyboard, screen reader labels/announcements, 200% zoom, non-color status cues, and responsive single-column widgets. Do not add unnecessary confirmations to ordinary form entry; preview/confirm applies to generated or grouped financial changes.

## 10. Stories and release acceptance

| ID | User outcome | Reuse and acceptance |
| --- | --- | --- |
| HU01 | Understand what can be spent | Adapt the existing overview; exact four-part reconciliation, correct pending vs covered labels, no claim of affordability from account balance alone. |
| HU02 | Resolve grouped negative categories | Reuse cover/move rules; preview sources and future consequences; stale/self-source requests rejected; no partial batch execution. |
| HU03 | Know whether future payments will be funded | Use cumulative catch-up and existing projection; show monthly assumptions and underfunded contributions even with zero immediate payment shortfall. |
| HU04 | Understand expected income | Keep current matching and TBA separation; explicit difference/partial-income decision; no duplicated income. |
| HU05 | Import and review safely | Reuse staging/adapters/review; retain 2 MiB/2,000 limits; clear ambiguous duplicate handling; retries recover batch state. |
| HU06 | Resume conversation and undo | Add general conversation/action persistence; Home refresh does not lose history or replay operations; inverse actions validate subsequent changes. |

### Regression gate

Preserve existing tests in `test_budget_rules.py`, `test_credit_cards.py`, `test_targets.py`, `test_income.py`, `test_debts.py`, `test_imports.py`, `test_import_transfers.py`, `test_categorization_review.py`, and `test_onboarding.py`. Include working-tree `test_coach.py` in the baseline.

Convert the ten characterization cases into desired-behavior regression tests as each decision/fix is implemented. Current characterization assertions intentionally describe present flaws/limitations and must not become golden expected behavior blindly.

Add concurrency, stale preview, safe source, exact rounding, partial payment, card aggregate, late obligation, and future-funding detector coverage. On any UI implementation, update affected Playwright tests and run the suite under the repository toolchain. Do not report inspected E2E files as executed tests.

## 11. Localization, analytics, and rollout

The launch implementation is EUR with a Madrid clock; a locale column is not full AR/ES/MX support. Add explicit locale and tone preference without changing the currency engine or financial boundaries accidentally. If per-user time zones are introduced, test month boundaries separately.

Native-copy examples remain Spanish: AR “Tenés dos categorías por revisar. ¿Las vemos?”; ES “Tienes dos categorías por revisar. ¿Las vemos?”; MX “Tienes dos categorías por revisar. ¿Las revisamos?”. Humor is optional and about the task, never the person; avoid it for arrears, illness, unemployment, distress, or uncertainty.

Proposed product events—not currently verified as implemented—include `home_viewed`, `financial_summary_viewed`, `recommendation_group_viewed`, `proposal_previewed`, `proposal_confirmed`, `proposal_rejected_stale`, `action_succeeded`, `action_failed`, `action_reversed`, `import_reviewed`, `import_confirmed`, `future_plan_reviewed`, and `conversation_resumed`. Emit success from committed operations. Use pseudonymous identifiers, locale, cohort, variant, version, reason, and latency; omit financial text and amounts. The PM plan defines denominators and windows.

### Delivery sequence

1. **Baseline and focused safety fixes:** preserve current contracts; resolve F01–F03 before broad conversational writes; fix and regression-test misleading aggregates and coverage rounding; agree policies for F07–F10.
2. **Read-oriented Home:** five destinations, deduplicated deterministic summary, existing forms and debt flows reachable, qualified forecast language. No accounting migration required.
3. **Conversation and safe actions:** general chat persistence, typed tools, preview/version/commit/replay, validated grouped moves, controlled undo. Reuse import and onboarding patterns.
4. **Future coaching:** use existing contribution and income engines; add funded/wanted detectors, completeness-aware language, and locale/tone support.
5. **Proactivity:** only after usefulness is validated, add scheduled checks and user-controlled notifications; avoid notifying on each Home entry.

Separate flags for Home, conversational actions, grouped recommendations, future coaching, and notifications. Pilot with consent, then 5% → 25% → 50% → general availability after the PM gates and adequate observation windows. Current seeded-user authentication must be replaced before real multi-user exposure.

Rollback disables affected new actions and restores safe forms. Preserve valid data and history; never mass-reverse valid transactions. A violated money identity, an unreviewed amount applied, a duplicate action, or cross-user access pauses the affected capability immediately.

**Out of scope:** replacing the financial engine, introducing Open Banking, executing bank payments, multi-currency accounting, a general investment product, or a new advanced-goals system.

## 12. OpenSpec reconciliation and implementation sequencing

### 12.1 Scope and evidence hierarchy

Reviewed `openspec/config.yaml`; the active `coach-proposals` proposal, design, tasks, and all four capability deltas; the current financial, budget, import/review, model, and LLM specifications; and the archived budget-rules, category-targets/annual-plan, and income-schedules designs to recover the reasons behind the rules. The archive was inventoried for context; this is not a claim that every archived scenario was re-tested.

Use OpenSpec to identify the intended contract, source to identify present behavior, and executed tests to establish observed results. A checked task or an archived change is not independent proof of deployment or of a successful test run on today's working tree. All tasks in the active Coach change are checked, including E2E, but this audit only inspected E2E source. Keep that distinction in release reporting.

The active Coach change has not been consolidated into `openspec/specs/coach-proposals/spec.md`. Its deltas remove the old standalone late-income and late-debt nudges; the base `income-schedules` and `debts` specs still contain those requirements. This is an active-change overlay, not a reason to restore the old capsules.

### 12.2 Existing decisions confirmed by OpenSpec

| Contract | What the redesign must retain |
| --- | --- |
| `specs/budget-api/spec.md`, “Budget month view” and “Rollover carries unspent balances forward” | Cumulative TBA, signed uncategorized cash activity, positive category rollover, cash overspending deduction, credit overspending kept as debt, and calendar-month walking. |
| `specs/budget-api/spec.md`, “Move money between categories” | Atomic paired assignment edits, source availability bounds, rejection of the same category, and negative source assignment permitted when moving rollover. |
| `specs/payment-schedules/spec.md`, “Normal and catch-up monthly amounts” | Cumulative multi-payment catch-up, monthly slots including the current month, a 10-year cap, and `max(normal, catch_up)` rather than a new savings formula. |
| `specs/payment-schedules/spec.md`, “Assignment computed from payments” | Automatic scheduled assignments, explicit moves allowed, and 409 for manual assignment PUT. |
| `specs/income-schedules/spec.md` | Shared occurrence rules, 14-pay support, real vs expected separation, read-time matching, and no probable-bonus field. |
| `specs/credit-cards/spec.md` and `specs/debts/spec.md` | Derived card funding and existing debt schedules, payoff simulation, payment category behavior, and explicit extra assignment. |
| `specs/statement-import/spec.md` and `specs/transaction-review/spec.md` | Stage/review/confirm, one pending batch, human-confirmed transfer matches, shared review controls, and an AI-unavailable manual path. |
| `specs/llm-layer/spec.md` | Reuse logical routes and usage records; production telemetry excludes content. Prompt-version changes require the separate evaluation workflow. |

The archived targets design explicitly deferred reserved-category protection, learned bill estimates, and Coach proposals. These are not grounds for replacing the schedule engine. It also rejected a separate generic “have X saved by date” primitive in favor of a dated future expense. Preserve that choice unless product deliberately reopens it.

### 12.3 Reclassification of the reproduced findings

- **F01 is an unsafe projection assumption explicitly present in the spec**, not simply a source divergence: `payment-projection` says only positive TBA carries. Change its initial-state requirement together with the narrow projection fix. Preserve actual budget rollover; specify deficit accounting without double-counting unpaid obligations.
- **F02 is an action-contract gap.** The active design intentionally recomputes on accept but does not bind acceptance to the version or amount the user saw. Extend the contract with reviewed input/version binding; keep recomputation as validation rather than permission to change the accepted action.
- **F03 violates the promised move semantics.** Coach design D4 promises the budget move rules; `budget-api` explicitly rejects `same_category`. Reusing only assignment helpers does not meet that promise.
- **F04 is a missing partial-payment scenario** under the overview's “confirmed spending” summary. Add a scenario defining the paid portion and pending remainder separately.
- **F05 exposes an ambiguous metric.** The overview spec includes paid card plans and category spending while the credit-card spec says spending is counted at purchase. Define consumption and settlement totals separately before changing the display. Do not alter the card ledger logic to repair a summary label.
- **F06 is an uncovered rounding boundary.** The projection explicitly uses pro-rata allocation but lacks a cent-conservation and exact-coverage scenario. Add both.
- **F07 is a lifecycle gap in the month-local contract.** Add an overdue-obligation requirement and tests rather than treating schedule recurrence as invoice persistence.
- **F08 implements the stated income policy.** The spec defines `received` as an assigned inflow and shows a lower salary as received with a difference. Partial-vs-final handling is a new product decision, with existing lower-final-salary behavior retained.
- **F09 implements the stated dedupe policy.** Hash collisions are deliberately skipped, and running balance distinguishes identical purchases when available. Ambiguity without that discriminator requires an extension to import review, not removal of reimport protection.
- **F10 exposes an internal spec tension.** `once` promises a future expense “however far ahead,” while catch-up is capped at 10 years. Resolve the promise through an explicit supported horizon or an extended algorithm; do not silently display a zero requirement.

### 12.4 Specification drift and misleading states

| ID | Evidence | Required documentation or UX change |
| --- | --- | --- |
| OS01 | `specs/data-model/spec.md:87` still summarizes TBA as `income − Σ assigned`; `budget-api` and the archived budget-rules design define the cumulative chain. | Replace the stale shorthand with a reference to the authoritative budget formula. No engine rewrite. |
| OS02 | `specs/data-model/spec.md:96` lists stored `scheduled` kind; `payment-schedules` and the revised targets design say kind is derived. `models.py:85` stores `flexible`/`savings` as the user flag and exposes effective kind. | Clarify stored flag vs API effective kind, including `credit_payment`; do not migrate computed kinds into storage. |
| OS03 | Generic “every category drafts” / “first month starts at zero” scenarios in `budget-api` and `budget-suggestions` conflict with their own scheduled-category requirements. | Qualify those scenarios as categories without schedules. Retain scheduled first-month assignment tests. |
| OS04 | `category-suggestions` still requires Anthropic and one request per batch. `llm-layer` requires provider-agnostic logical routes; `services/category_suggestions.py` uses chunks of 200. | Update the older specification to the shared route, chunk-level failure fallback, and actual data sent for inference. Keep human review. |
| OS05 | Active `coach-proposals` requires an empty feed to say the plan looks on track. `CoachFeed.tsx:89` implements that line. A dismissed warning, missing income, insufficient history, or a structural set-aside gap can yield no visible proposals. | Empty feed must mean “no visible suggestions,” not a solvency verdict. Derive financial status independently from completeness, pending risks, and forecast fields. Test a dismissed risk and an unfunded set-aside with no uncovered dated payment. This is source/spec analysis, not one of the ten executed characterization cases. |
| OS06 | `payment-projection` explicitly allows all dated payments to be covered while set-asides remain underfunded. The active Coach only detects uncovered dated payments. | Add a separate grouped reserve/structural-gap detector using existing funded/wanted and annual-gap fields. Do not label the plan healthy merely because `short_months` is absent. |

### 12.5 Proposed OpenSpec changes for the next implementation

These are implementation-planning recommendations; this audit does not create, modify, or archive repository OpenSpec files.

1. **Reconcile baseline specifications.** Correct OS01–OS04 and contradictory horizon wording. Preserve archived designs as historical records; amend current specs through a new change with explicit deltas. Integrate or archive the active Coach work only after its release checks, without overwriting the user's local changes.
2. **Harden existing Coach operations.** Extend `coach-proposals` with immutable reviewed amounts, stale rejection, same-source rejection, eligible source rules, transaction atomicity, idempotency, and persisted action outcomes. Add tests F02/F03 before changing the frontend to execute more powerful actions.
3. **Correct financial read models narrowly.** Update `payment-projection` for F01/F06, `month-overview` for F04/F05, and the relevant contracts for F07–F10 after product decisions. Keep all healthy budget/card fixtures unchanged.
4. **Specify conversation and Home B as a new capability.** The active Coach explicitly excludes free-form chat, LLM copy, and analytics, and requires removal of the text input. A new change must deliberately supersede that temporary feed-only requirement. Add persistent messages, resume behavior, deterministic widgets, locale settings, safe tool actions, five-destination navigation, and events. Keep the deterministic feed as a fallback.
5. **Specify structural reserve guidance.** Add OS05/OS06 scenarios, grouped recommendations and donor impact. A money-move preview must show the effect on future obligations, even when the existing move API legally allows the transfer.
6. **Update user documentation and verification.** `openspec/config.yaml` requires tasks updating `docs/user-guide.md` and `docs/debt-guide.md` whenever screens, flows, labels, copy, or money rules change. Include this in each user-visible change. Add backend regressions, E2E of changed flows, and locale/LLM evaluations where relevant; do not infer these passed from checked historical tasks.

**OpenSpec release acceptance:** each changed requirement has a scenario, a named automated or user-research check, an observed result, and an owner. Each deliberate financial policy change is visible in a delta and signed off as a product decision; unchanged mathematical behavior has regression evidence. Base specs and active deltas must no longer tell developers to build mutually incompatible UIs.
