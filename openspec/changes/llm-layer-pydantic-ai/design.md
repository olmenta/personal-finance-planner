# Design — LLM Layer on Pydantic AI

## Context

- **Two LLM call sites, both `litellm.completion(model=f"anthropic/{settings.anthropic_model}", response_format=Schema)`:**
  - `services/onboarding.py::_call_model` (one interview turn, one retry, `OnboardingUnavailable` on failure);
  - `services/category_suggestions.py::_call_model` (chunked import suggestions; a failed chunk degrades to EMPTY).
- **Both log failures as exception class names only.** Transcripts and bank descriptions must never reach logs (ai-onboarding spec; CLAUDE.md).
- **Sentry:**
  - `telemetry.py` initializes Sentry with `LiteLLMIntegration` and gen-AI spans;
  - LLM content is allowed only outside production (`send_default_pii` forced off in prod).
- **Settings:** a single `ANTHROPIC_MODEL` (default `claude-sonnet-4-6`) and `ANTHROPIC_API_KEY`.
- **Decisions behind this change (explore, 2026-10-06):**
  - Pydantic AI replaces LiteLLM as the application LLM layer;
  - Logfire (EU) handles observability and evals;
  - Jev arrives through Pydantic AI's `TypeSafeModel` in a later spike;
  - a gateway (LiteLLM Proxy / Pydantic AI Gateway) stays optional for later.

## Goals / Non-Goals

**Goals:**

- One provider-agnostic layer with logical routes; no model ids in services.
- Port the two call sites with identical behavior (prompts, schemas, retries, degradation, logging).
- Usage and cost per call, keyed to user and route, without content.
- Logfire traces with a strict production content policy.
- Eval suites that gate prompt-version bumps.

**Non-Goals:**

- The coach agent, deferred-tool approvals, Jev (later changes build on this layer).
- Enforcing per-user caps.
- Online content-based evals in production.
- Next.js tracing.
- A gateway service.

## Decisions

### D1: `app/llm/`, the only place that knows about models

```
app/llm/
  routes.py      ROUTES: route → RouteConfig(model, settings, fallback)  (+ env overrides)
  agents.py      agent(route, output_type, instructions) → pydantic_ai.Agent (cached per route)
  usage.py       record_usage(user_id, route, result) → llm_usage row (tokens, cost, latency, outcome)
  observability.py  configure_logfire() — dormant without LOGFIRE_TOKEN; content policy
```

**Services ask for a route and a schema, never a model:**

```python
turn = run_structured("onboarding", InterviewTurn, messages=..., user_id=...)
```

**Routes in this change:**

| Route | Model (default) | Settings |
|---|---|---|
| `onboarding` | `anthropic:claude-sonnet-5` | instructions cached; `max_tokens` 4000 |
| `category_suggestions` | `anthropic:claude-haiku-4-5` | instructions cached; `max_tokens` 16000 |

Each route can be overridden by an env var, for example `LLM_ROUTE_ONBOARDING_MODEL`.

**The default models change on purpose** (decided 2026-10-06), from the current single `claude-sonnet-4-6` to a model per route. The eval suites (D5) run on both the old and the new models; the results are recorded here as the first baseline. A regression is then fixed through the prompt or the route settings, not by reverting the default.

**Baseline (2026-10-06, `uv run python -m evals …`):**

| Suite | New default | Pass rate · avg latency | Previous model (`claude-sonnet-4-6`) |
|---|---|---|---|
| `category_suggestions` (10 cases) | `claude-haiku-4-5` | 100% · 1.1 s | 100% · 2.0 s |
| `onboarding` (6 cases incl. LLM-judged proposal) | `claude-sonnet-5` | 100% · 4.7 s | 100% · 4.5 s |

Two fixture fixes landed before the final numbers (evaluator issues, not model errors): payee comparison ignores word order ("Cines Yelmo" = "Yelmo Cines"), and utilities expect the prompt's canonical values (`electricity`, `water & sewage`), not the user's words.

**Implementation notes:**

- The onboarding route uses `max_tokens` 16000, not 4000: Sonnet 5 thinks adaptively by default, and a low cap risks truncating the turn.
- Prompt caching verified on the onboarding route: about 3,960 of 4,006 input tokens are read from cache on a repeated turn, at about $0.002 per turn.

### D2: Behavior kept exactly at the call sites

- **Onboarding:** one retry on any failure, then `OnboardingUnavailable`. The `done`-without-proposal re-ask logic stays in the service, unchanged.
- **Category suggestions:** chunking unchanged; a failed or unparseable chunk degrades to EMPTY; it never raises.
- **Output modes:** Pydantic AI's output mode is chosen per route. Native structured output is used where the provider supports it; tool output is the fallback. The existing tests (`test_onboarding.py`, `test_category_suggestions.py`, `test_categorization_review.py`) must pass with only their mocking seam changed: they patch `run_structured` (or the service's `_call_model`) instead of `litellm.completion`.
- **Failure logging:** still the exception class name, plus the cause chain's class names. Never content.

### D3: Usage and cost records

- **The `llm_usage` table:** `id`, `user_id`, `route`, `model`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_micro_eur`, `latency_ms`, `outcome` (`ok` / `error` / `fallback`), `created_at`. No prompt, output or ids of user data.
- **Cost:** computed with genai-prices `calc_price` from the run's usage, converted to EUR with a configured rate (`LLM_USD_EUR_RATE`, default 0.92) and stored in micro-euros as an integer.
- **A recording failure never fails the user request.** It logs a warning instead.
- **This is the input the coach's per-user monthly caps will read.** Enforcing them is a later change.

### D4: Logfire, with the content policy as code

**Setup:** `configure_logfire()` runs at startup next to Sentry. It is dormant without `LOGFIRE_TOKEN` and instruments Pydantic AI, FastAPI and HTTPX. The project is in the **EU region**.

**Content policy:**

| `LOGFIRE_ENVIRONMENT` | LLM content (prompts and outputs) |
|---|---|
| `production` | Never: `include_content=False`, regardless of any flag |
| `development` / `dogfood` | Allowed only when `LOGFIRE_INCLUDE_CONTENT=true` — the developer's own dev environment and Logfire project, used with their personal financial data (decided 2026-10-06) |
| `evals` | Included (synthetic or reviewed fixtures) |

**Scrubbing:** the default scrubbing patterns are extended with `description`, `payee`, `note`, `amount_cents`, `iban`, `transcript`, `extracted`.

**What must stay out of spans** (verified in tests):

- request and response bodies, since the BFF passes transactions through the API;
- SQL bound parameters.

**Sentry:** the LiteLLM integration is removed. The backend's `traces_sample_rate` defaults to 0 once Logfire traces requests; Sentry keeps errors and logs.

**Alternative rejected:** keeping Sentry's AI spans. Logfire's Pydantic AI instrumentation and eval integration are the reason for adopting it; two AI-span pipelines would double the privacy surface.

### D5: Eval suites with `pydantic_evals`

**Where and how they run:**

- `backend/evals/onboarding.py` and `backend/evals/category_suggestions.py`;
- run with `uv run python -m evals <suite>`, never collected by `pytest`;
- results go to Logfire as experiments when `LOGFIRE_TOKEN` is set.

**Onboarding cases:** fixture conversations.

- Evaluators: whether the expected extraction fields are settled after each answer (deterministic), plus a proposal-quality rubric judged by an LLM on route `judge` (`anthropic:claude-opus-5`).
- The judge writes its reasoning before the score.

**Category-suggestion cases:** labeled fixture rows with a category tree.

- Evaluators: category accuracy and payee normalization (deterministic).

**The workflow** (documented in `evals/README.md` and referenced from the prompt files): bumping a prompt `version` requires a run with no regression against the last recorded experiment.

## Risks / Trade-offs

- **[Output-mode differences change structured outputs]** → The existing tests plus the eval suites must be green before the swap ships. Per-route output mode is configurable.
- **[New model defaults regress quality]** → D1: the evals compare against the current model, and the old default is kept if a suite regresses.
- **[Telemetry becomes an exfiltration path]** → The production content policy is enforced in code, not configuration. Scrubbing covers the financial field names. A test asserts that no prompt content reaches the span exporter when the environment is `production`.
- **[A Logfire outage or a missing token]** → Logfire is dormant and the app is unaffected; exporting is non-blocking.
- **[Pydantic AI's pace of change]** → Pin the minor version. The tests and eval suites are the upgrade gate.
- **[Vendor concentration on Pydantic]** → Logfire is OpenTelemetry, so the exporter can be swapped. Pydantic AI is provider-agnostic and MIT-licensed.

## Migration Plan

1. Add the dependencies and `app/llm/`; port the two call sites behind routes; adjust the test seams; run the full suite.
2. Run both eval suites on the old model (`claude-sonnet-4-6`) to record the baseline, then on the new defaults; keep or revert each route's default (D1).
3. Add the `llm_usage` migration and recording.
4. Configure Logfire (EU) with the content policy and scrubbing; remove Sentry's LiteLLM integration.
5. Remove `litellm`; update CLAUDE.md, `.env.example` and the memory rule.

**Rollback:** revert the commit. The `llm_usage` table is additive.

## Open Questions

- **The data processing agreement with Pydantic (Logfire)** is needed before enabling it in production. Until then Logfire runs only in the developer's dev environment and project, where content may include the developer's own financial data by their choice. That project must never receive other users' data.
