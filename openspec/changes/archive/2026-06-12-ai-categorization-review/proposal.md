# Proposal — AI categorization review

## Why

AI category suggestions exist only at import time, and they fire blind: the model sees the category tree but nothing about how this user actually categorizes. Meanwhile the BBVA import landed hundreds of confirmed-but-uncategorized rows that can only be fixed one by one. One upgrade serves both: a history-informed suggestion service, and an anytime review flow that proposes categories for existing transactions and lets the user accept them in bulk.

## What Changes

- **History-informed suggestions (shared service upgrade)**: the suggestion prompt gains few-shot examples sampled from the user's already-categorized transactions (recent description → category pairs), so repeated merchants resolve the way this user resolves them. Import suggestions improve with no API change. Each suggestion now carries a `confidence` (`high` | `medium` | `low`) and a proposed clean `payee` name extracted from the bank description ("MERCADONA VALENCIA …" → "Mercadona"), so imports stop leaving payees empty.
- **Imports gain payees**: staged rows carry the AI-proposed payee (find-or-create on the cleaned name); the review keeps showing everything before anything lands, and discarding a batch removes payees nobody else references.
- **On-demand suggestion run**: `POST /transactions/suggest-categories` proposes categories and payees for confirmed transactions — by default every uncategorized one, optionally an explicit id list — returning `{transaction_id, category_id, confidence}` proposals without writing anything. Same fail-open posture as import: AI failure returns an empty proposal list, never an error that blocks the user.
- **Bulk apply**: `POST /transactions/apply-categories` writes the accepted `{transaction_id: category_id}` assignments (owner-scoped, confirmed-only, category-validated) in one request.
- **Review UI**: a "Suggest categories" action on the transactions screen (enabled when uncategorized rows exist) → dialog listing each proposal (date, description, amount, suggested category in an editable select, confidence badge) with select-all/none and "Apply" — mirroring the import review pattern. On apply, transactions/budget/summary queries refresh for affected months.
- **BFF**: two new proxied routes.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `category-suggestions`: requirement extended — history-informed prompt with per-row confidence and proposed payee; new requirement for the on-demand suggest/apply contract.
- `payees`: imported rows may now reference AI-proposed payees (reviewed before confirm) instead of always staying null.
- `bff-proxy`: proxied-routes requirement gains `POST /api/transactions/suggest-categories` and `POST /api/transactions/apply-categories`.
- `webapp-server-state`: new requirement — suggestion review flow on the transactions screen with cache invalidation.

## Impact

- `backend/app/services/category_suggestions.py`: history sampling, confidence in the output schema, shared by import + on-demand.
- `backend/app/routers/transactions.py` (or a small `suggestions` router): the two endpoints; `schemas.py`: request/response models.
- `backend/tests/`: service tests (history included in prompt, confidence parsed) + endpoint tests with mocked client.
- `webapp/src/app/api/transactions/suggest-categories|apply-categories/route.ts`, `api.ts` helpers, `SuggestCategoriesDialog` + entry button on the transactions screen.
- No schema migration — proposals are transient, nothing new is stored.
