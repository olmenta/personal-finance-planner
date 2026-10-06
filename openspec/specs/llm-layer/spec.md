# llm-layer Specification

## Purpose

Provider-agnostic LLM access through Pydantic AI and logical routes, per-call usage and cost records, Logfire observability with the production content policy, and eval suites gating prompt-version bumps.

## Requirements

### Requirement: One provider-agnostic LLM layer with logical routes

Every LLM and decision-model call in the backend SHALL go through the LLM layer (Pydantic AI), addressed by a logical route — never by a model id in service code and never through a provider SDK directly. A route SHALL map to a model, its settings (output mode, max tokens, effort, prompt caching) and an optional fallback, defined in one configuration module and overridable per route from the environment. The routes `onboarding` and `category_suggestions` SHALL exist, and adding a route SHALL require no change outside that module and the calling service.

#### Scenario: Model changed by configuration

- **WHEN** `LLM_ROUTE_CATEGORY_SUGGESTIONS_MODEL` is set to another supported model
- **THEN** category suggestions run on that model with no code change

#### Scenario: Behavior preserved on the new layer

- **WHEN** the backend test suite runs after the port
- **THEN** onboarding (one retry, then unavailable; re-ask on a done turn without proposal) and category suggestions (chunk-level degradation to empty, never raising) behave exactly as before

### Requirement: Usage and cost recorded per call without content

Each LLM run SHALL record its route, model, input and output tokens, cache read and write tokens, cost (computed from the provider's published prices, stored in micro-euros), latency, outcome (`ok`, `error`, `fallback`) and the user it ran for. The record SHALL NOT contain prompts, outputs, or user financial data. A failure to record usage SHALL NOT fail the user's request.

#### Scenario: Suggestion run recorded

- **WHEN** an import triggers category suggestions for a user
- **THEN** one usage record per model call exists for that user and route with token counts and a non-zero cost, and no prompt or row text

#### Scenario: Recording failure is harmless

- **WHEN** writing the usage record fails
- **THEN** the suggestions are still returned and a warning is logged

### Requirement: Observability with a production content policy

The backend SHALL send traces of LLM runs, requests and outbound HTTP calls to Logfire (EU region) when a Logfire token is configured, and SHALL behave exactly as without it when none is. In the `production` environment LLM prompts and outputs SHALL never be included in telemetry, regardless of any flag; outside production they MAY be included only when explicitly enabled. Request and response bodies and SQL bound parameters SHALL NOT be recorded, and scrubbing SHALL redact Olmenta's financial fields (descriptions, payees, notes, amounts, IBANs, onboarding transcripts and extractions). Application logs for failed LLM calls SHALL carry the exception class and cause chain, never content. Sentry SHALL remain the error tracker.

#### Scenario: Production keeps content home

- **WHEN** production handles an onboarding turn with Logfire configured and content inclusion requested by flag
- **THEN** the exported spans carry route, model, tokens, latency and outcome but no prompt or output text

#### Scenario: No token, no telemetry

- **WHEN** no Logfire token is configured
- **THEN** no exporter is set up and requests behave exactly as before

#### Scenario: Failure logged without content

- **WHEN** an onboarding turn fails with a connection error
- **THEN** the log line names the exception class and its cause and contains no message content

### Requirement: Eval suites gate prompt-version bumps

The repository SHALL contain `pydantic_evals` suites for each live prompt — onboarding (extraction of the expected fields per fixture conversation, proposal quality judged by an LLM on the `judge` route) and category suggestions (category accuracy and payee normalization on labeled fixture rows). The suites SHALL run outside the default `pytest` invocation through a documented command, SHALL publish results to Logfire as experiments when configured, and the documented workflow SHALL require a run without regression against the last recorded experiment before a prompt configuration's version is bumped.

#### Scenario: Extraction regression caught

- **WHEN** a prompt edit stops the model from extracting a field that a fixture answer previously settled
- **THEN** the onboarding suite reports the regression before the version bump ships

#### Scenario: Default test run unaffected

- **WHEN** `uv run pytest` runs
- **THEN** no eval case executes and no live model call is made
