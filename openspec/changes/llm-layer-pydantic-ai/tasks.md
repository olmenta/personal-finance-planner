# Tasks — LLM Layer on Pydantic AI

## 1. Layer

- [x] 1.1 Dependencies: `uv add "pydantic-ai-slim[anthropic]" genai-prices logfire` and `uv add --dev pydantic-evals`; pin minor versions
- [x] 1.2 `app/llm/routes.py`: `RouteConfig` (model, output mode, max tokens, effort, caching, fallback) and `ROUTES` with `onboarding`, `category_suggestions`, `judge`; per-route env overrides; replaces `ANTHROPIC_MODEL` in `config.py`
- [x] 1.3 `app/llm/agents.py`: agent factory per route (cached) and `run_structured(route, output_type, messages|prompt, user_id)` returning the validated output plus run usage
- [x] 1.4 Anthropic prompt caching on instructions per route (`anthropic_cache_instructions`); verify `cache_read_tokens` on repeated calls in a manual check

## 2. Port the call sites

- [x] 2.1 `services/onboarding.py`: `_call_model` on `run_structured("onboarding", InterviewTurn, …)`; one retry, `OnboardingUnavailable`, class-only failure logging unchanged
- [x] 2.2 `services/category_suggestions.py`: `_call_model` on `run_structured("category_suggestions", SuggestionResponse, …)`; chunk degradation unchanged
- [x] 2.3 Test seams: tests patch the layer instead of `litellm.completion`; `test_onboarding.py`, `test_category_suggestions.py`, `test_categorization_review.py` green with no behavioral edits

## 3. Usage and cost

- [x] 3.1 Alembic migration: `llm_usage` table (design D3), with downgrade
- [x] 3.2 `app/llm/usage.py`: record per run with genai-prices cost in micro-euros (`LLM_USD_EUR_RATE`), never failing the request
- [x] 3.3 Tests: a suggestion run records usage without content; a recording failure still returns suggestions

## 4. Observability

- [x] 4.1 `app/llm/observability.py`: `configure_logfire()` (dormant without `LOGFIRE_TOKEN`; EU region; instrument Pydantic AI, FastAPI, HTTPX), content policy per `LOGFIRE_ENVIRONMENT` (production forces content off), scrubbing patterns for financial fields
- [x] 4.2 `telemetry.py`: drop Sentry's `LiteLLMIntegration`; backend `traces_sample_rate` default 0; update the module docstring
- [x] 4.3 Tests with an in-memory span exporter: production exports no prompt or output text even with the flag on; no request bodies or SQL bound parameters in spans; no token → no exporter

## 5. Evals

- [x] 5.1 `backend/evals/` with `pydantic_evals` suites: onboarding (fixture conversations; expected-field extraction evaluators; LLM-judge proposal rubric on route `judge`) and category suggestions (labeled fixture rows; accuracy + payee normalization)
- [x] 5.2 Runner `uv run python -m evals <suite>` (not collected by pytest; `testpaths` excludes it), Logfire experiment publishing when configured; `evals/README.md` with the prompt-version-bump workflow, referenced from `app/prompts/*.md`
- [x] 5.3 Baseline: run both suites on `claude-sonnet-4-6` and on the new route defaults (Sonnet 5 for onboarding, Haiku 4.5 for suggestions), and record the results in `design.md` as the first baseline

## 6. Remove LiteLLM and update docs

- [x] 6.1 `uv remove litellm`; no import of `litellm` left in `backend/`
- [x] 6.2 CLAUDE.md: replace "Use LiteLLM for LLM calls" with "All LLM and decision-model calls go through the Pydantic AI layer (`app/llm`, by route); never call provider SDKs directly"; tech stack line; Logfire mention
- [x] 6.3 `.env.example`: `LOGFIRE_TOKEN`, `LOGFIRE_ENVIRONMENT`, `LOGFIRE_INCLUDE_CONTENT`, `LLM_ROUTE_*` overrides, `LLM_USD_EUR_RATE`; remove `CONFIDENT_API_KEY` and `ANTHROPIC_MODEL`
- [x] 6.4 Update the `use-litellm-for-llm-calls` memory to the new rule

## 7. Verification

- [ ] 7.1 `uv run pytest` green in `backend/`
- [x] 7.2 `volta run npm run e2e` green (onboarding and import flows exercise the ported paths with AI off)
- [ ] 7.3 Manual with the API key: an onboarding conversation and an import with suggestions; traces visible in the Logfire dev project; usage rows recorded with costs
