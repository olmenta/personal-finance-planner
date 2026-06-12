# Design — LLM Observability & Evals

## Context

Two LiteLLM call sites exist: `app/services/category_suggestions.py` (`_call_model`) and `app/services/onboarding.py` (`_call_model`). Both log failures as exception type names only — deliberately, because transcripts and bank descriptions must not hit logs (ai-onboarding spec, transcript privacy; CLAUDE.md: never log financial data). That same constraint shaped this design: observability must not become an exfiltration path.

`CONFIDENT_API_KEY` already sits in `.env.example`, unused. DeepEval is Confident AI's SDK: eval metrics + platform tracing. LiteLLM supports pluggable success/failure callbacks process-wide (`litellm.success_callback = [...]`).

## Goals / Non-Goals

**Goals:**

- See every LLM call's model, latency, token usage, and failure cause in one dashboard during development.
- Catch prompt regressions before a version bump ships (extraction accuracy, suggestion accuracy).
- Zero behavior change when no telemetry key is configured.

**Non-Goals:**

- Production telemetry (blocked on GDPR data-processor review; flag exists but defaults off).
- General error monitoring (Sentry, separate change), metrics/alerting infra, or webapp changes.
- Eval coverage for future prompts (structure accommodates them; only the two live prompts get suites now).

## Decisions

### D1 — One telemetry module, process-wide LiteLLM callbacks

`app/telemetry.py` exposes `configure_llm_telemetry()` called once at app startup (`main.py`) and at eval-suite startup. It sets `litellm.success_callback`/`litellm.failure_callback` to the DeepEval/Confident integration only when enabled. Call sites stay untouched — no decorator creep, provider stays config.

*Why not per-call wrappers?* Two call sites today but the rule "LLM calls go through LiteLLM" already centralizes; callbacks are LiteLLM's native extension point.

### D2 — Enablement: key present AND (dev OR explicit flag)

```
enabled = bool(confident_api_key) and (env != "production" or llm_telemetry_enabled)
```

`llm_telemetry_enabled` defaults to `False` and is the single switch a future GDPR review would flip. Until then, production sends nothing to Confident AI even if the key leaks into the environment. The existing `Settings` object carries both values.

### D3 — Failure logging gets the cause, never the content

The current `logger.warning("... %s", type(error).__name__)` lines gain the provider's error message **class and cause chain** (e.g. `APIConnectionError ← ConnectError: [Errno 8] nodename nor servname`), which is what debugging actually needs. Prompt content, messages, and transcripts stay out of log lines — unchanged invariant.

### D4 — Evals live in `backend/evals/`, outside the default pytest run

DeepEval test cases make live LLM calls (the judged model and often a judge model) — slow and costly. They are not unit tests:

- `backend/evals/test_onboarding_evals.py` — fixture conversations as `(transcript, expected_extraction)` pairs; metric: exact-field extraction accuracy plus a G-Eval rubric for proposal quality.
- `backend/evals/test_category_suggestion_evals.py` — fixture rows + category tree; metric: suggested-category accuracy against labeled fixtures, payee-cleaning correctness.
- Run with `uv run deepeval test run evals/` (requires `ANTHROPIC_API_KEY`; uses `CONFIDENT_API_KEY` to publish runs when set).
- `pytest` default run excludes `evals/` via `testpaths = ["tests"]` (already the effective behavior) so CI speed is unaffected.

### D5 — Prompt-version bump gate is convention, enforced by review

The eval suites parameterize on the active prompt config. The workflow — edit prompt, run evals, compare to the previous version's run, then bump `version:` — is documented in `evals/README.md`. No CI hard-gate yet (live-call cost); revisit when prompts churn more.

## Risks / Trade-offs

- [DeepEval pulls heavy transitive deps] → dev dependency group only; production image unaffected.
- [Telemetry accidentally enabled in prod] → double gate (D2): key alone is not enough; flag defaults off.
- [Eval fixtures drift from real user language] → fixtures seeded from the manual-walkthrough transcripts (anonymized, synthetic identities); grow per regression found.
- [Confident AI traces include prompts/completions by design] → acceptable in dev (synthetic/dev data only); the D2 gate is what keeps real user data out, since dev runs against the dev user.
- [Judge-model evals are nondeterministic] → exact-match metrics for extraction/categorization (deterministic); G-Eval rubric only for proposal quality where exactness is impossible, with threshold not equality.

## Migration Plan

1. Add deps + telemetry module + settings (no behavior change with key unset).
2. Land eval suites with fixtures; run once to baseline `onboarding_v1` and the current suggestion prompt.
3. Rollback = remove the callback wiring; eval suite is inert tooling.

## Open Questions

- None blocking. CI eval gating deferred (D5) until prompt-change frequency justifies the spend.
