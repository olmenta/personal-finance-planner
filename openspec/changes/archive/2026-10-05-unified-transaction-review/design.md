# Design — Unified Transaction Review

## Context

- **Import review.** `ImportBankTransactionsDialog` renders staged rows through `TransactionReviewRow`: date, editable note, payee, amount, category combobox, "Transfers →", and twin-match chips. It submits `POST /imports/{id}/confirm` with five decision maps: `overrides`, `payee_overrides`, `note_overrides`, `transfer_overrides` and `accept_matches`. The backend logic lives in `services/import_batch.py`:
  - `match_suggestions(batch)`;
  - `_apply_payee_overrides`, `_apply_note_overrides`, `_mark_transfers` (via `transfers.link_existing`) and `_adopt_matches`;
  - `confirm_batch` orchestrates them.
- **AI review.** `SuggestCategoriesDialog` uses the same row but a different flow. `POST /transactions/suggest-categories` returns proposals only for rows the AI classified. `POST /transactions/apply-categories` accepts `{category_id, payee, note}` per row, with checkboxes.
- **Decisions taken with the user (2026-10-05):**
  - list every uncategorized transaction;
  - no checkboxes, behave exactly like the import;
  - always all months, whichever entry point opens it.

## Goals / Non-Goals

**Goals:**

- One webapp component and one backend implementation for "resolve these transactions", fed by two sources: staged rows of a batch, or confirmed uncategorized rows.
- Confirmed rows get transfer marking and twin matching, with the same rules as import.
- The categorization review works, minus suggestions, when the AI is unavailable.

**Non-Goals:**

- Mixing staged and confirmed rows in one list.
- New matching heuristics: the ±3 days, same signed amount, app-written twin rule stays.
- Any change to the import's upload, resume or discard behavior.

## Decisions

### D1: `services/review.py` is the shared core

The decision logic moves out of `import_batch.py` into functions that work on any list of the user's rows:

- **`twin_matches(db, rows)`:** returns row id → `TwinMatchSuggestion`.
  - Groups the rows by `account_id`.
  - For each account, loads the confirmed transfer rows with `source = "manual"` (still app-written) within ±3 days of that account's rows.
  - Applies today's rule: same signed amount, closest date wins, one twin per row.
  - Rows that are already transfers are skipped.
- **`apply_decisions(db, user, rows, decisions)`:** applies, in today's order:
  1. category overrides (null clears);
  2. payee overrides;
  3. note overrides;
  4. accepted matches: the row is deleted and the twin takes the row's hash and source;
  5. transfer marking: `link_existing`, creating a confirmed twin.

  It returns the payee ids that lost references.

**How the callers use it:**

- `confirm_batch` becomes: `apply_decisions` on the batch's staged rows, flip to confirmed, clean up orphan payees. Its behavior and tests do not change.
- `match_suggestions(batch)` becomes `twin_matches(staged_rows(batch))`.

**Alternative rejected:** duplicating the logic for confirmed rows. Two implementations of transfer and adopt semantics would drift, and those are the riskiest writes in the app.

### D2: The review endpoints

**`POST /transactions/review`.** It is a POST because it may run one AI call; it writes nothing.

- **Which rows:** the user's confirmed rows with no category and no `transfer_pair_id`, with `source != "opening_balance"`, newest first, capped at 500.
- **What each row carries:** the transaction fields, plus `suggested_category_id`, `suggested_payee`, `confidence` (null when the AI is off, fails, or has nothing), plus `match` (a `TwinMatch` or null).
- **AI failure:** degrades to null suggestions and never fails the request.

**`POST /transactions/review/apply`.** Takes the import's five maps, restricted to confirmed, uncategorized, non-transfer rows of the user. Rows that are invalid or vanished are skipped silently, as the import does, and the response reports how many rows were written.

**Alternative rejected:** keeping `suggest-categories` / `apply-categories` next to the new endpoints. Nothing else calls them, and two apply paths with different semantics is exactly what this change removes.

### D3: AI suggestions are defaults on the client, never stored

Staged import rows already store the AI category in `category_id`, because staging is a draft. Confirmed rows must not be written before the user applies.

- The review response therefore carries the suggestion separately.
- The client uses it as the row's default selection and payee, and the badge shows its confidence.
- Applying sends a category override whenever the effective selection differs from the stored (null) category. A kept suggestion is sent; an untouched row without one is not.

### D4: One webapp review: `useTransactionReview` + `TransactionReview`

**`useTransactionReview(items)`** is the hook both dialogs use.

- **Input:** `ReviewItem`s:

  ```ts
  { row; defaultSelection; defaultPayee; badge?: { label; tone }; match }
  ```

- **State it owns:** the per-row maps (selection, payee, note, match decision), stable `(id, value)` dispatchers, memoized transfer groups per direction (from the accounts query and each row's own account), and the accounts and payees lookups.
- **What it returns:**
  - `rowProps(item)`, carrying the memo contract;
  - `buildDecisions()`, producing the five maps the backend expects.

**`TransactionReview`** renders the list (or the empty state passed in).

**How each dialog uses them:**

- **The import dialog** maps staged rows to items: the default is the staged `category_id`, the badge is "Suggested". It keeps its own chrome: upload step, skipped count, Discard, "Confirm import".
- **`CategorizationReviewDialog`** maps review rows to items: the default is the suggestion or "none", the badge is the confidence. It shows "Apply changes", disabled while nothing would be written.

Transfer targets are computed per row's account, because confirmed rows can come from different accounts, unlike a batch.

### D5: Entry points

- Both the "Suggest categories" button (renamed "Review uncategorized") and the budget's "Categorize now" open `CategorizationReviewDialog`. The dialog requests the review when it opens and shows a loading state while the AI runs.
- The transactions page still shows its button only while uncategorized rows exist.

## Risks / Trade-offs

- **[A 500-row review with an AI call is slow to open]** → The loading state names it ("Suggesting categories…"). The cap and the AI chunking are unchanged from the old suggest endpoint.
- **[Adopting a match deletes a confirmed row]** → It happens only on an explicit "Link them", it is shown before apply (the row is dimmed with "won't be added twice"), and it is the same operation the import performs on a staged row.
- **[Refactoring the import's confirm path]** → `test_imports.py` and `test_import_transfers.py` cover it today and must pass unchanged. The review tests reuse the same fixtures.
- **[Transfer groups per account cost a memo per account]** → They are computed once per account in the hook. Rows receive the group list of their own account and direction, so references stay stable.

## Migration Plan

No data migration.

- Removing the old endpoints and their BFF routes ships in the same deploy as the new dialog. There are no other clients.
- Rollback is reverting the commit.

## Open Questions

None. The three product decisions were taken with the user.
