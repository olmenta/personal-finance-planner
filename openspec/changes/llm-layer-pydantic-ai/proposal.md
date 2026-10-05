# LLM Layer on Pydantic AI

## Why

Olmenta is moving toward a chat-first coach (explore, 2026-10-06). That needs an agent loop with typed tools, a "the model proposes, the user confirms" mechanism, a model per task, per-user cost control, a non-generative decision model (TypeSafe Jev) and evals that gate prompt changes.

Today the backend makes two `litellm.completion(..., response_format=...)` calls. LiteLLM is a model-access layer and covers none of the application-level needs above. Pydantic AI covers them in-process:

- agents with typed tools and outputs;
- deferred tools for human approval;
- `FallbackModel`;
- Anthropic prompt caching and effort settings;
- usage reporting, with genai-prices for cost;
- Jev through `TypeSafeModel`;
- OpenTelemetry instrumentation feeding Logfire, plus `pydantic_evals`.

With two call sites, this is the cheapest moment to switch.

This change also replaces the deleted `llm-observability-evals` proposal (LiteLLM callbacks + DeepEval/Confident AI). Its intent carries over: production privacy, failure logs without content, and evals that gate prompt-version bumps.

## What Changes

- **One LLM layer: Pydantic AI.** Onboarding turns and category suggestions run as Pydantic AI agents with typed `output_type`s. Prompts, schemas, retries and degradation behavior stay unchanged, and the existing tests are the acceptance bar.
  - **BREAKING (internal):** LiteLLM is removed from the backend.
- **Routes, not model ids.**
  - Code asks for a logical route: `onboarding`, `category_suggestions`, and later `coach_fast`, `coach_plan`, `judge`, `decision`.
  - A config table maps each route to a model, settings (effort, max tokens, caching) and an optional fallback, overridable from the environment.
  - It replaces the single `ANTHROPIC_MODEL` setting.
- **Per-call usage and cost.**
  - Each run records route, model, tokens (including cache reads and writes), cost computed with genai-prices, latency and outcome.
  - The record is keyed to the user, without content.
  - This is the base for per-user monthly caps in the coach; enforcing the caps is out of scope here.
- **Logfire observability (EU region).**
  - Pydantic AI, FastAPI and HTTPX instrumentation.
  - **LLM content is excluded in production** (`include_content=False`); dogfooding and offline evals may include content.
  - Scrubbing extended to Olmenta's financial field names.
  - Dormant without a token, exactly as Sentry is without a DSN.
- **Sentry stays for errors.** Its LiteLLM integration and backend performance tracing give way to Logfire for traces.
- **Evals with `pydantic_evals`:**
  - an onboarding suite (extraction accuracy per fixture conversation, proposal quality judged by an LLM);
  - a category-suggestions suite (accuracy and payee cleaning on labeled fixture rows).

  They run outside the default `pytest`, results land in Logfire, and a prompt-version bump requires a green run.
- **The rule changes.** CLAUDE.md "Use LiteLLM for LLM calls" becomes "All LLM and decision-model calls go through the Pydantic AI layer (routes); never call provider SDKs directly". The `CONFIDENT_API_KEY` env var goes away.

## Capabilities

### New Capabilities

- `llm-layer`:
  - provider-agnostic LLM access through Pydantic AI and logical routes;
  - per-call usage and cost records;
  - Logfire observability with the production content policy;
  - eval suites gating prompt-version bumps.

### Modified Capabilities

- `ai-onboarding`: interview turns invoke the model through the LLM layer (route `onboarding`) instead of LiteLLM. Behavior is unchanged.

## Impact

- **Backend:**
  - New `app/llm/` (routes config, agent factory, usage recording, Logfire setup).
  - `services/onboarding.py` and `services/category_suggestions.py` move off LiteLLM.
  - `telemetry.py` (Sentry without the LiteLLM integration, Logfire configuration), `config.py` (routes, Logfire token and environment).
  - A new `llm_usage` table, via an Alembic migration.
  - New `evals/` directory.
- **Dependencies:**
  - added: `pydantic-ai-slim[anthropic]`, `genai-prices`, `logfire`, and `pydantic-evals` (dev);
  - removed: `litellm`.
- **Docs:** CLAUDE.md rule and tech stack line; the `use-litellm-for-llm-calls` memory updated to the new rule; `.env.example` (`LOGFIRE_TOKEN`, `LOGFIRE_ENVIRONMENT`, routes; `CONFIDENT_API_KEY` removed).
- **Not affected:** the webapp, the API contracts, `dev-mcp-server` (no LLM inside it).
- **Unblocks:** `decision-model-spike` (Jev through the same layer) and the in-app coach.
- **Out of scope:**
  - enforcing per-user caps;
  - the LiteLLM Proxy or a Pydantic AI Gateway;
  - online content-based evals in production (they need explicit consent);
  - Next.js tracing in Logfire.
