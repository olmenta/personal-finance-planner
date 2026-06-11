# Tasks — AI categorization review

## 1. Suggestion service upgrade (shared with import)

- [ ] 1.1 `category_suggestions.py`: `history` parameter — sample up to ~100 distinct recent `(description, category_name)` pairs from the user's categorized confirmed transactions; render as worked examples in the prompt (design D1)
- [ ] 1.2 Output schema gains `confidence: Literal["high","medium","low"]` (missing → `low`); `suggest()` returns `{row: (category_id, confidence)}` or equivalent; import call site passes history and keeps using just the ids
- [ ] 1.3 Service tests: history pairs appear in the prompt, confidence parsed and defaulted, fail-open unchanged

## 2. Endpoints

- [ ] 2.1 Schemas: `SuggestCategoriesRequest{transaction_ids?}`, `CategoryProposal{transaction_id, category_id, confidence}`, `SuggestCategoriesResponse{proposals}`, `ApplyCategoriesRequest{assignments}`, `ApplyCategoriesResponse{applied}`
- [ ] 2.2 `POST /transactions/suggest-categories`: default = confirmed uncategorized (500 newest cap), optional explicit ids (owner-scoped); proposals only for rows the model placed; AI failure → empty list, 200 (design D2, D3)
- [ ] 2.3 `POST /transactions/apply-categories`: validate each assignment (owner, confirmed, category in user's tree), skip invalid, write in one transaction, return applied count
- [ ] 2.4 API tests with mocked client: default targeting, explicit ids, proposals never write, apply writes accepted subset and skips vanished rows, AI failure → empty proposals; `uv run pytest` green

## 3. BFF and client

- [ ] 3.1 Route Handlers: `webapp/src/app/api/transactions/suggest-categories/route.ts` + `apply-categories/route.ts` (POST via `proxyFetch`)
- [ ] 3.2 `webapp/src/lib/api.ts`: proposal types, `suggestCategories(ids?)`, `applyCategories(assignments)`

## 4. Review UI

- [ ] 4.1 "Suggest categories" secondary button on the transactions screen, visible when confirmed uncategorized rows exist; fires the suggest call with a pending state (design D4)
- [ ] 4.2 `SuggestCategoriesDialog`: rows with checkbox (default checked), date, description, amount tone, category select prefilled, confidence Badge (high mint / medium neutral / low warning), low-confidence first; footer "Apply N categories" / Cancel (design D5)
- [ ] 4.3 Apply posts checked rows with overrides; invalidate `["transactions"]` + `["budget", m]` / `["summary", m]` per affected month; empty-proposals state invites manual categorization
- [ ] 4.4 No sparkle icon — reserved for the coach; plain verb label

## 5. Verification

- [ ] 5.1 `uv run pytest` green (TEST_DATABASE_URL exported); `volta run npm run build` + `volta run npm run lint` green
- [ ] 5.2 E2E with both processes and a real `ANTHROPIC_API_KEY`: run suggestions over the imported uncategorized BBVA rows → review shows proposals with confidence → apply subset → list/budget/dashboard update; re-run shows only the remainder
- [ ] 5.3 At sync/archive time: merge the `bff-proxy` proxied-routes list with whatever `edit-delete-transactions` / `manage-categories` have landed (three changes modify the same requirement)
