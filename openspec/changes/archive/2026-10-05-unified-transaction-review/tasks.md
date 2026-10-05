# Tasks — Unified Transaction Review

## 1. Backend: shared review core

- [x] 1.1 `services/review.py`:
  - `twin_matches(db, rows)`, grouped by account, with the import's rule;
  - `apply_decisions(db, user, rows, decisions)`, covering category (null clears), payee, note, accepted matches (adopt) and transfer marking (`link_existing`), and returning the dropped payee ids.
  - Move `TwinMatchSuggestion` and `MATCH_WINDOW_DAYS` here (design D1).
- [x] 1.2 `services/import_batch.py`:
  - `match_suggestions` and `confirm_batch` delegate to `review.py`, with unchanged behavior;
  - `test_imports.py` and `test_import_transfers.py` stay green, untouched.

## 2. Backend: review endpoints

- [x] 2.1 `schemas.py`:
  - add `ReviewRowOut` (transaction fields + `suggested_category_id`, `suggested_payee`, `confidence`, `match`), `ReviewView`, `ReviewApplyRequest` (the import's five maps) and `ReviewApplyResponse` (`applied`);
  - remove `SuggestCategoriesRequest/Response`, `CategoryProposal`, `CategoryAssignment` and `ApplyCategories*` once they are unused.
- [x] 2.2 `routers/transactions.py`: `POST /transactions/review` (design D2):
  - rows: confirmed, uncategorized, not transfer, not opening balance; newest first, cap 500;
  - AI suggestions through `category_suggestions.suggest` (no write, degrades to null);
  - matches through `twin_matches`.
- [x] 2.3 `POST /transactions/review/apply`: restrict to the user's confirmed, uncategorized, non-transfer rows, run `apply_decisions`, clean up orphan payees, and return the applied count.
- [x] 2.4 Remove `suggest-categories` and `apply-categories` from `routers/transactions.py`.
- [x] 2.5 Rewrite `tests/test_categorization_review.py` for the new contract:
  - listing (all months, exclusions, newest first, cap);
  - AI suggestions as defaults with nothing written (mocked service);
  - no AI → rows without suggestions;
  - apply of category, payee and note;
  - transfer marking creates the twin;
  - accepted match deletes the duplicate;
  - foreign and categorized rows skipped.

## 3. Webapp: shared review

- [x] 3.1 BFF:
  - add `app/api/transactions/review/route.ts` and `app/api/transactions/review/apply/route.ts`;
  - delete `suggest-categories` and `apply-categories`.
- [x] 3.2 `lib/api.ts`:
  - add `ReviewRowOut`, `ReviewView`, `ReviewDecisions` (the five maps, shared with `confirmImport`), `fetchReview()` and `applyReview(decisions)`;
  - make `confirmImport` take a `ReviewDecisions`;
  - remove the old suggest/apply types and functions.
- [x] 3.3 `components/review/useTransactionReview.ts` (design D4):
  - `ReviewItem` input;
  - per-row maps and stable dispatchers;
  - transfer groups memoized per account and direction;
  - `rowProps(item)` and `buildDecisions()` (diffing against the stored values, defaults included).
- [x] 3.4 `components/review/TransactionReview.tsx`: the bordered list of `TransactionReviewRow`s, plus an empty state slot. Move `TransactionReviewRow` into `components/review/`.
- [x] 3.5 Import dialog:
  - map staged rows to items (default = staged category, badge "Suggested");
  - use the hook and the component;
  - confirm with `buildDecisions()`;
  - keep the upload, skipped-count, resume, discard and cover-prompt behavior.
- [x] 3.6 `components/review/CategorizationReviewDialog.tsx` (replaces `SuggestCategoriesDialog`):
  - fetch the review on open, with a loading state;
  - map rows to items (default = suggestion or none; payee = suggestion or stored; badge = confidence; low confidence first);
  - "Apply changes", disabled when `buildDecisions()` is empty;
  - an empty state when nothing is uncategorized;
  - invalidate money queries, transactions and payees on apply.
- [x] 3.7 Entry points:
  - transactions page: "Review uncategorized" opens the dialog, shown while uncategorized rows exist;
  - budget block: "Categorize now" opens it;
  - delete `SuggestCategoriesDialog.tsx`.

## 4. Specs and docs

- [x] 4.1 Check that the deltas match the implementation: `transaction-review` added, `category-suggestions` on-demand requirement removed, `webapp-server-state` and `budget-assignment` modified.

## 5. Verification

- [x] 5.1 `uv run pytest` green in `backend/`.
- [x] 5.2 Type check, lint and build green in `webapp/`. Use `NEXT_DIST_DIR=.next-verify` with the dev server running, and revert any `tsconfig.json` rewrite.
- [x] 5.3 e2e: extend `import-review.spec.ts`. Confirm an import leaving rows uncategorized, open "Review uncategorized" (no AI in e2e), and check the rows are listed. Set a category and a note on one row, mark another as a transfer, apply, and check the budget block count drops. `volta run npm run e2e` green.
- [x] 5.4 Manual checks automated in `e2e/categorization-review.spec.ts` (2026-10-05):
  - AI suggestions as defaults with confidence badges, injected into the review response because e2e has no LLM;
  - transfer marked from the review;
  - twin match linked;
  - the import review stays covered by `import-review.spec.ts`.
  - Only the live model call itself remains a hands-on check with the API key.
