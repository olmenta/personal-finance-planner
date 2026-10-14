## 1. Data model

- [x] 1.1 Add `CoachProposalState` (`user_id`, `fingerprint`, `state` dismissed|accepted, `until`, `created_at`; unique `(user_id, fingerprint)`) to `models.py`.
- [x] 1.2 Write the Alembic revision creating `coach_proposal_states`, after `d6e3f9a2b1c7`.

## 2. Detectors

- [x] 2.1 Add `services/coach.py`:
  - the `Proposal` dataclass;
  - the threshold constants;
  - the fingerprint helper;
  - closed-month history (3 budget views built once per request).
- [x] 2.2 Write the detectors:
  - `late_income`, from `month_income(current)`;
  - `late_debt_payment`, from the overview's `to_pay.late`;
  - `short_months`, from `projection.upcoming(current)` months after the first with an uncovered occurrence, grouped;
  - `overspending` (flexible, at least 2 of 3 closed months with available < 0, suggestion rounded up to 5 €, at least 10 € above this month's assignment, `sources` when To Be Assigned can't cover it);
  - `unassigned` (To Be Assigned ≥ 10 €);
  - `underspending` (flexible, 3 of 3 closed months with spent < assigned, at least 10 € below).
- [x] 2.3 Order by urgency, then amount. Filter by state (accepted, or dismissed with `until` in the future). Return the copy templates from design D7 in plain language.
- [x] 2.4 Unit and API tests for every coach-proposals scenario:
  - Restaurantes raise to 230 €;
  - Gasolina lower to 60 €;
  - differences under 10 € ignored;
  - short months grouped;
  - money with no job;
  - urgency order;
  - kinds never produced for scheduled, savings or card payment categories, or with under 3 months of history.

## 3. API

- [x] 3.1 Add `routers/coach.py`:
  - `GET /coach/proposals` (`proposals`, `total`);
  - `POST /coach/proposals/{fingerprint}/dismiss` (7 days);
  - `POST /coach/proposals/{fingerprint}/accept` (`raise`/`lower` through the assignment and move operations; optional `from_category_id`).

  Errors: 409 `not_enough_to_assign`, 409 `not_acceptable`, 404 `proposal_not_found`. Register it in `main.py`.
- [x] 3.2 Tests:
  - dismiss hides it until +7 days (pinned clock), then it reappears;
  - accept raise from To Be Assigned;
  - raise without enough returns 409, and with a source it moves the money;
  - accept lower frees money;
  - an accepted proposal stays gone;
  - the state table holds no amounts.

## 4. Webapp

- [x] 4.1 Add BFF routes `api/coach/proposals`, `api/coach/proposals/[fingerprint]/dismiss` and `api/coach/proposals/[fingerprint]/accept`. Add types and functions to `lib/api.ts`. `invalidateMoneyQueries` also invalidates `coach-proposals`.
- [x] 4.2 Add `components/coach/ProposalCard.tsx`:
  - title and body;
  - the action button per kind ("Raise it", "Lower it", "Add it", "It's already here", "See my plan", "See the month", "Give it a job");
  - "Not now";
  - a source picker for a `raise` with sources;
  - the `add_income` (prefilled `AddTransactionDialog`) and `link_income` (`IncomeBreakdown`) handlers.
- [x] 4.3 Add `components/coach/CoachFeed.tsx`: the first 3, "See more (N)", and the empty state. In `CoachRail` and `/coach`, replace `CoachConversation`'s scripted chat and remove the input (keep `CoachHeader`).
- [x] 4.4 Dashboard: show the top proposal as one `CoachCapsule` with its action and "Not now". Remove `LateIncomeNudge`, `LateDebtNudge` and the static "18% more on dining" fallback capsule.

## 5. Docs

- [x] 5.1 Update the end-user guides.
  - `docs/user-guide.md`:
    - a "Your coach" section (what it suggests, "Not now" for a week, "See more", raise and lower);
    - replace the late-income note wording.
  - `docs/debt-guide.md`: the late-payment note now comes from the coach.
- [x] 5.2 Update `project-definition.md`: principle 8 (the coach proposal is now live, with underspending too), the §4.2 "Coach proposals on the plan" entry (keep only the deferred kinds), and a §10 resolved entry.
- [x] 5.3 Check that the deltas match the implementation: `coach-proposals` added, the late nudges removed from `income-schedules` and `debts`, `bff-proxy` modified.

## 6. Verification

- [x] 6.1 `uv run pytest` green in `backend/`.
- [x] 6.2 Type check, lint and build green in `webapp/` (build with `NEXT_DIST_DIR=.next-verify`).
- [x] 6.3 e2e:
  - update `income.spec.ts` (the late income comes from the dashboard coach capsule; "Add it" still clears it);
  - update `debts.spec.ts` (the late installment is shown by the coach);
  - add `e2e/coach.spec.ts`: an overspending history raises the budget in one tap; "Not now" hides a proposal; the rail shows 3 plus "See more"; no text input in the rail;
  - `volta run npm run e2e` green.
