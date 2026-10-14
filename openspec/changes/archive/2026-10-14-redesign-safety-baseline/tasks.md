## 1. Baseline

- [x] 1.1 Confirm that `coach-proposals` is complete and lands first, or in the same PR (it's uncommitted on `feat/coach-proposals`). Run `uv run pytest` to record the baseline and note any failure.
- [x] 1.2 Fix `test_request_values_never_exported` to assert structured span attributes instead of a substring search in the export (D9).

## 2. Forecast (F01, F06)

- [x] 2.1 `services/projection.py`: change the first month's projected end to `TBA(M) − overspent_cents(M) − Σ short_cents(to_pay) + still_expected(M)`, signed and never clipped (D1).
- [x] 2.2 `_allocate` in integer cents: floor shares, then distribute the remainder by largest fractional part with ties in priority order. Round wanted amounts up to whole cents. Compute coverage and `short_cents` on integers (D2).
- [x] 2.3 Regression tests:
  - a current deficit stays visible next month (F01);
  - two 1-cent payments with one cent available (F06);
  - existing projection and summary fixtures (`test_targets.py`) unchanged or explained.

## 3. Coach safety (F02, F03, OS05)

- [x] 3.1 Extract `services/budget_moves.py::validate_source` from `routers/budget.py` (same category, unknown source, availability). Make the move endpoint use it with unchanged behavior (D4).
- [x] 3.2 Coach accept:
  - the eligible source rule (flexible, not archived, not card payment, scheduled or savings);
  - 422 `same_category`;
  - 409 `not_enough_in_source`;
  - no mutation before validation.
- [x] 3.3 Proposal `revision` hash in `services/coach.py` and `CoachProposalOut`. Accept requires `revision`: 409 `proposal_changed` with the current proposal on mismatch, and a no-op 200 for an already accepted revision. Add a migration for the nullable `coach_proposal_states.revision` (D3).
- [x] 3.4 Tests:
  - stale revision → 409 with the new amount, nothing applied (F02);
  - retry with the same revision applies once;
  - self-source → 422 with no change (F03);
  - a savings source → 409;
  - a valid source keeps total assigned and accounts unchanged.
- [x] 3.5 Webapp: the coach card sends the rendered `revision`; on `proposal_changed` it replaces the card with the returned proposal and a note that the numbers changed. The empty feed says "No suggestions right now." (D7).

## 4. Already paid and card payments (F04, F05)

- [x] 4.1 `services/overview.py`: partial paid items (`partial = true`) for unpaid, non-estimated occurrences with allocated money. Card payment category activity and card plan occurrences go to a new `card_payments` section, never to `paid`. Update `schemas.py` and `lib/api.ts` (D5).
- [x] 4.2 `ThisMonth`: partial items read "paid in part"; a "Card payments" line under "Already paid" when there are settlements.
- [x] 4.3 Tests:
  - 40 € paid of 100 € → 40 € in `paid` (partial) and 60 € pending (F04);
  - a 60 € card purchase plus a 60 € settlement → `paid` counts 60 € once, `card_payments` 60 € (F05);
  - the identity holds;
  - update the card plan overview tests (paid plan now under `card_payments`).

## 5. Planning horizon (F10)

- [x] 5.1 Validators for `once_month` (payment and income schedules) and the personal debt's `due_month`, limited to the current month + 119 months → 422 `outside_planning_horizon` (D6).
- [x] 5.2 Tests: October 2037 rejected and April 2028 accepted, seen from October 2026, for a schedule and a personal debt.

## 6. Spec reconciliation and docs

- [x] 6.1 Check that the OS01–OS04 deltas (`data-model`, `budget-api`, `budget-suggestions`, `category-suggestions`) match the code. Adjust wording if the code differs (no code change intended).
- [x] 6.2 Record the F07–F09 policies (design D8) in the backlog memory and the roadmap entries for `future-coaching` and the import change.
- [x] 6.3 Update the end-user guides: in `docs/user-guide.md`, "Already paid" versus card payments, partial payments, the coach's empty state ("no suggestions right now"), and that a payment more than 10 years away can't be planned. Check `docs/debt-guide.md` for the card payment wording.

## 7. Verification

- [x] 7.1 `uv run pytest` green in `backend/`.
- [x] 7.2 Type check, lint and build green in `webapp/` (build with `NEXT_DIST_DIR=.next-verify`).
- [x] 7.3 e2e:
  - update `category-targets.spec.ts` if the paid totals change;
  - update `coach.spec.ts` (the raise sends the revision; the empty state copy);
  - update `debts.spec.ts` if the card plan display changes;
  - run `volta run npm run e2e` green.
