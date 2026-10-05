# Unified Transaction Review

## Why

Olmenta has two screens for the same job: going through a list of transactions and deciding what each one is (a category, a transfer, or the other side of a transfer that already exists).

- **The import review** handles staged rows and offers everything: note, payee, category, "Transfers →", and twin-match suggestions.
- **The AI categorization review** handles confirmed rows. It only shows the rows the AI managed to classify, it can't mark a transfer or catch a duplicate twin, and without AI it is empty.

Testing showed that a confirmed transaction left uncategorized often *is* a transfer or a duplicate of one. The user should resolve it with the same tool, and that tool should list every uncategorized transaction whether or not the AI is available.

## What Changes

- **One review, two sources.** The review lists rows and resolves each one through the same decisions. A single webapp component serves both entry points: the import dialog (staged rows of a batch) and "Suggest categories" / "Categorize now" (confirmed uncategorized rows).
  - The decisions are category, "Ready to assign"/"Uncategorized", note, payee, "Transfer → <account>", and accepting or ignoring a twin match.
  - The component holds the row layout, the per-row state, the payload building and the stable-props performance contract.
- **Categorization review lists everything uncategorized.** `POST /transactions/review` returns every confirmed uncategorized transaction of the user (newest first, capped at 500), whatever its month.
  - Transfer twins and opening balances are excluded.
  - Each row carries the AI suggestion as a default (`suggested_category_id`, `suggested_payee`, `confidence`), plus a twin-match suggestion computed like the import's.
  - Without AI the rows are still listed with no suggestion. Nothing is written.
- **Applying works like confirming an import.** `POST /transactions/review/apply` takes the same decision maps as `POST /imports/{id}/confirm`: category overrides (null clears), payee and note overrides, transfer marking (creates the twin) and accepted matches (the existing twin is adopted and the confirmed duplicate removed).
  - Only rows the user changed, or whose suggestion they kept, are written. There are no per-row checkboxes.
- **BREAKING (internal API):** `POST /transactions/suggest-categories` and `POST /transactions/apply-categories` are removed along with their BFF routes. The only callers are the dialog this change replaces.
- **Budget block:** "Categorize now" opens the same review. It lists every uncategorized transaction in all months, so it never dead-ends when the AI is unavailable.

## Capabilities

### New Capabilities

- `transaction-review`:
  - the review contract for confirmed uncategorized transactions (list with AI defaults and twin matches; apply with the import's decisions);
  - the shared webapp review component and the behavior both entry points get from it.

### Modified Capabilities

- `category-suggestions`: the on-demand proposals and apply endpoints are removed. The suggestion service now feeds the review instead.
- `webapp-server-state`: the AI categorization review flow becomes the shared review over all uncategorized transactions, with no checkboxes and with transfers and matches.
- `budget-assignment`: "Categorize now" opens the shared review, which works without AI.

## Impact

- **Backend:**
  - New `services/review.py`, extracted from `services/import_batch.py` so the import and the review share one implementation: twin matching over arbitrary rows grouped by account, plus applying category, payee, note, transfer and adopt decisions.
  - `confirm_batch` keeps its contract and uses the shared code.
  - New routes in `routers/transactions.py`; `suggest-categories` and `apply-categories` are removed.
  - Schemas: `ReviewRowOut`, `ReviewView`, `ReviewApplyRequest`; `CategoryAssignment` is removed.
  - `tests/test_categorization_review.py` is rewritten for the new contract, and the import tests must stay green.
- **Webapp:**
  - `components/review/`:
    - a `TransactionReview` table and a `useTransactionReview` state hook, built on the existing `TransactionReviewRow`;
    - `CategorizationReviewDialog` replaces `SuggestCategoriesDialog`.
  - The import dialog is reduced to its upload step plus the shared review.
  - BFF routes: `/api/transactions/review` and `/api/transactions/review/apply`.
  - The transactions page and the budget page both open the new dialog.
- **Specs:** `category-suggestions` loses its on-demand requirement; `transaction-review` is created.
- **Out of scope:**
  - Reviewing staged and confirmed rows in one list.
  - Undoing a match adoption after apply (unlink and delete work as today).
  - Bulk actions across rows.
