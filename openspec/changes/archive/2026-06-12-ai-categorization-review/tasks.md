# Tasks — AI categorization review

## 1. Suggestion service upgrade (shared with import)

- [x] 1.1 `category_suggestions.py`: `history` parameter — sample up to ~100 distinct recent `(description, payee_name, category_name)` triples from the user's categorized confirmed transactions; render as worked examples in the prompt (design D1)
- [x] 1.2 Output schema gains `confidence` (missing → `low`) and `payee` (cleaned name, null when unclear); `suggest()` returns `{row: (category_id, payee, confidence)}` or equivalent; import staging passes history, resolves the proposed payee find-or-create onto staged rows; batch discard deletes payees no other transaction references
- [x] 1.3 Service tests: history triples appear in the prompt, confidence parsed and defaulted, payee passed through, fail-open unchanged; import tests: staged rows carry the proposed payee, discard removes orphan payees

## 2. Endpoints

- [x] 2.1 Schemas: `SuggestCategoriesRequest{transaction_ids?}`, `CategoryProposal{transaction_id, category_id, payee, confidence}`, `SuggestCategoriesResponse{proposals}`, `ApplyCategoriesRequest{assignments: {txn_id: {category_id?, payee?}}}`, `ApplyCategoriesResponse{applied}`
- [x] 2.2 `POST /transactions/suggest-categories`: default = confirmed uncategorized (500 newest cap), optional explicit ids (owner-scoped); proposals only for rows where the model placed a category or payee; AI failure → empty list, 200 (design D2, D3)
- [x] 2.3 `POST /transactions/apply-categories`: validate each assignment (owner, confirmed, category in user's tree), resolve payee find-or-create, skip invalid, write in one transaction, return applied count
- [x] 2.4 API tests with mocked client: default targeting, explicit ids, proposals never write, apply writes accepted subset and skips vanished rows, AI failure → empty proposals; `uv run pytest` green

## 3. BFF and client

- [x] 3.1 Route Handlers: `webapp/src/app/api/transactions/suggest-categories/route.ts` + `apply-categories/route.ts` (POST via `proxyFetch`)
- [x] 3.2 `webapp/src/lib/api.ts`: proposal types, `suggestCategories(ids?)`, `applyCategories(assignments)`

## 4. Review UI

- [x] 4.1 "Suggest categories" secondary button on the transactions screen, visible when confirmed uncategorized rows exist; fires the suggest call with a pending state (design D4)
- [x] 4.2 `SuggestCategoriesDialog`: rows with checkbox (default checked), date, description, amount tone, category select + payee input prefilled, confidence Badge (high mint / medium neutral / low warning), low-confidence first; footer "Apply N categories" / Cancel (design D5)
- [x] 4.3 Apply posts checked rows with overrides; invalidate `["transactions"]` + `["budget", m]` / `["summary", m]` per affected month; empty-proposals state invites manual categorization
- [x] 4.4 No sparkle icon — reserved for the coach; plain verb label

## 5. Verification

- [x] 5.1 `uv run pytest` green (TEST_DATABASE_URL exported); `volta run npm run build` + `volta run npm run lint` green
- [x] 5.2 E2E with both processes and a real `ANTHROPIC_API_KEY`: import BBVA file → staged rows carry proposed payees; run suggestions over confirmed uncategorized rows → review shows category+payee proposals with confidence → apply subset → list/budget/dashboard update; re-run shows only the remainder
- [x] 5.3 At sync/archive time: merge the `bff-proxy` proxied-routes list with whatever has landed, and reconcile the `payees` main spec (imported rows may now carry reviewed AI payees)
