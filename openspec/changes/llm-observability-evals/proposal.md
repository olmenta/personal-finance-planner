# LLM Observability & Evals

## Why

LLM failures are currently opaque: a turn that dies surfaces only an exception type name in the backend log (e.g. `APIConnectionError` during onboarding with no cause), and there is no way to measure whether a prompt change makes extraction or categorization better or worse. With two production prompts live (onboarding interview, category suggestions) and prompt versions explicitly tracked (§6.6), the project needs LLM call tracing and a regression-gating eval suite.

## What Changes

- **LiteLLM telemetry callbacks, env-gated**: when `CONFIDENT_API_KEY` is set, LiteLLM success/failure callbacks send call traces (model, latency, tokens, errors) to Confident AI via the DeepEval SDK. No key → no callbacks, zero overhead. Configured in one shared place, not per call site.
- **Privacy guard**: telemetry is dev-only by default. Onboarding transcripts and bank descriptions never leave for the telemetry platform in production — the ai-onboarding spec's transcript-privacy requirement extends to third-party telemetry; an explicit environment flag (off by default) is the only way to enable callbacks outside dev, pending a GDPR data-processor review.
- **DeepEval eval suites** (dev dependency) for both prompts:
  - Onboarding: fixture conversations → assert extraction accuracy (fields settled per answer) and proposal shape quality.
  - Category suggestions: fixture transaction rows + category trees → assert suggestion accuracy and payee cleaning.
- **Prompt-version gate**: bumping a prompt version (e.g. `onboarding_v1` → `v2`) requires a green eval run; documented as the workflow in the eval suite README/comments.

## Capabilities

### New Capabilities

- `llm-observability`: contract for LLM call telemetry (env-gated callbacks, single configuration point, privacy constraints) and the eval suites that gate prompt-version bumps.

### Modified Capabilities

<!-- none — ai-onboarding transcript-privacy requirement already forbids transcript telemetry; this change implements within it -->

## Impact

- **Backend**: `deepeval` added to the `dev` dependency group; small `app/telemetry.py` (or equivalent) wiring `litellm.success_callback`/`failure_callback` behind settings; `Settings` gains `confident_api_key` and `llm_telemetry_enabled`; richer failure logging (error class + provider cause, still no prompt/transcript content).
- **Tests/evals**: new `backend/evals/` with fixture datasets and DeepEval test cases, runnable via `uv run deepeval test run` (or pytest marker), excluded from the default CI-fast `pytest` run (live LLM calls cost money).
- **Config**: `.env.example` documents `CONFIDENT_API_KEY` (already present) and `LLM_TELEMETRY_ENABLED`.
- **No webapp changes.** Sentry (frontend/backend error monitoring) is being added separately and is out of scope here.
