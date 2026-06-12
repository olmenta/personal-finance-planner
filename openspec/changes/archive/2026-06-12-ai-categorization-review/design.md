# Design — AI categorization review

## Context

`services/category_suggestions.py:suggest(categories, rows)` makes one structured-output LLM call per import batch — through **LiteLLM**, never a provider SDK directly, so the provider stays configuration (model from `anthropic_model`, default `claude-opus-4-8`, bare names resolve to the `anthropic/` provider) — validates ids, and fails open to all-null. It only ever sees `NormalizedTransaction`s at import time, with no knowledge of the user's categorization habits. The BBVA backfill left hundreds of confirmed rows with `category_id = null` (suggestions ran without an API key); fixing them is currently one edit at a time. Transactions are signed-cents rows keyed by `["transactions"]`/`["budget", m]`/`["summary", m]` queries in the webapp; the import review dialog is the established bulk-review pattern.

## Goals / Non-Goals

**Goals:**

- One suggestion service serving both import and on-demand runs, now informed by the user's own categorization history with a confidence signal per row.
- Bulk categorization of existing confirmed transactions behind explicit user review — AI never writes a category directly.
- Same fail-open posture everywhere: AI down → empty proposals, the user can still categorize by hand.

**Non-Goals:**

- Auto-applying high-confidence suggestions without review (later, once confidence is calibrated).
- Persisting proposals or learning per-merchant rules in the DB (the history prompt is the memory for now).
- Re-categorizing rows that already have a category by default (only via explicit id selection).
- Streaming/progress UI for large runs — one request, bounded row count.

## Decisions

### D1 — Shared service, richer prompt: history few-shot + hint + confidence

`suggest()` gains a `history` argument: up to ~100 `(description, payee_name, category_name)` triples sampled from the user's most recent categorized transactions (distinct descriptions, newest first — recency beats frequency for drifting habits, and distinctness keeps Mercadona from filling the budget). The prompt lists them as worked examples before the target rows; `category_hint` handling stays. The Pydantic output schema gains `confidence: Literal["high","medium","low"]` per row (defaulting to `low` when missing) and `payee` — the clean merchant/payer name extracted from the raw bank description, null when unclear. History examples carry the payee alongside the category so both mappings learn from the user. Import calls pass the same history, so import suggestions improve for free; staged rows resolve the proposed payee find-or-create at staging time, and discarding a batch deletes payees that no other transaction references (keeps rejected suggestions from polluting the list). One call per run (via `litellm.completion` with the Pydantic schema as `response_format`), capped rows, fail-open unchanged. Alternative rejected: per-merchant rule table in the DB — real learning, but premature while the prompt window holds the whole history sample.

### D2 — Stateless two-step: suggest, then apply

`POST /transactions/suggest-categories` (body: optional `transaction_ids`; default = all confirmed uncategorized, capped at 500 newest) returns `{proposals: [{transaction_id, category_id, payee, confidence}]}` — rows where the model placed neither a category nor a payee are omitted. Nothing is written; nothing is stored. `POST /transactions/apply-categories` (body: `{assignments: {txn_id: {category_id, payee}}}`) validates each id (owner, confirmed, real category — invalid entries are skipped, response reports `applied` count) and writes in one transaction. Stateless keeps the API free of proposal lifecycle (expiry, conflicts); the review dialog holds the proposals in memory exactly like the import review holds staged rows. Alternative rejected: staging proposals server-side — a second staging mechanism duplicating what import batches already do, for no persistence need.

### D3 — Suggest-categories is a POST that reads

The suggest endpoint mutates nothing but costs one model call and takes seconds — POST (not GET) keeps it out of caches and prefetchers and gives it a body. It reuses the transactions router's auth/db plumbing.

### D4 — Review dialog mirrors the import review

"Suggest categories" secondary button on the transactions screen (shown when uncategorized confirmed rows exist; pressing it fires the suggest call and opens `SuggestCategoriesDialog`). Rows: checkbox (default checked), date, description, amount tone, category select prefilled with the proposal, confidence Badge (`high` mint / `medium` neutral / `low` warning). Footer: "Apply N categories" + Cancel. Apply posts only checked rows (with any per-row overrides), then invalidates `["transactions"]` and `["budget", m]`/`["summary", m]` for each affected month. Empty proposals (AI down or nothing uncategorized) render an actionable empty state, never an error wall. The sparkle icon stays reserved for the coach — the button uses a plain verb label.

### D5 — Confidence is presentation, not gating

Confidence renders as a badge and default-sorts the list (low first, so the user's attention lands where the model is unsure) but never gates applying. No threshold knobs in v1; calibrate first, automate later.

## Risks / Trade-offs

- [AI payee names could flood the payee list] → names only land via staged-import confirm or explicit apply, both behind review; discard cleans batch-only payees.
- [Large history bloats the prompt] → capped sample (~100 distinct recent pairs); rows capped at 500 per run.
- [Model returns ids for rows the user didn't ask about] → proposals filtered to requested rows server-side, same id-validation as import.
- [Apply races a concurrent edit/delete] → per-row validation at apply time skips vanished rows; response reports the applied count.
- [Three in-flight changes modify `bff-proxy`'s proxied-routes requirement] → merge endpoint lists at sync time (same note as `manage-categories`).
- [Token cost of history per import] → one extra ~100-line block per batch call; acceptable against import frequency.

## Migration Plan

1. Service upgrade (history, confidence) + tests — import benefits immediately.
2. Endpoints + tests.
3. BFF routes + api.ts + dialog.
Rollback: revert webapp commit; endpoints additive; service change is prompt-only.

## Open Questions

- None blocking.
