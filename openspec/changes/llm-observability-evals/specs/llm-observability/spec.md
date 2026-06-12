# llm-observability Delta Specification

## ADDED Requirements

### Requirement: Env-gated LLM call telemetry

The backend SHALL support sending LLM call telemetry (model, latency, token usage, outcome, failure cause) to the configured observability platform through LiteLLM callbacks, configured in exactly one module invoked at application startup. Telemetry SHALL be enabled only when the platform API key is configured AND the environment is non-production or an explicit `LLM_TELEMETRY_ENABLED` flag is set. With no key configured, LLM calls SHALL behave exactly as before — no callbacks registered, no overhead, no errors.

#### Scenario: Dev with key

- **WHEN** `CONFIDENT_API_KEY` is set in a development environment
- **THEN** each LiteLLM call emits a success or failure trace to the platform

#### Scenario: No key

- **WHEN** no telemetry key is configured
- **THEN** no callbacks are registered and LLM calls succeed/fail exactly as without this feature

#### Scenario: Production locked by default

- **WHEN** the app runs in production with `CONFIDENT_API_KEY` set but `LLM_TELEMETRY_ENABLED` unset
- **THEN** no telemetry leaves the system

### Requirement: Telemetry respects content privacy in production

User content (onboarding transcripts, bank transaction descriptions, prompts containing either) SHALL NOT be sent to third-party telemetry in production. Application logs for failed LLM calls SHALL include the error class and underlying cause chain but SHALL NOT include prompt or message content.

#### Scenario: Failure logged with cause, without content

- **WHEN** an onboarding turn fails with a connection error
- **THEN** the log line carries the exception class and cause (e.g. DNS failure) and no message content

#### Scenario: Production content stays home

- **WHEN** production handles an onboarding turn while telemetry is force-enabled by flag
- **THEN** enabling that flag is documented as requiring a completed GDPR data-processor review

### Requirement: Eval suites gate prompt-version bumps

The repo SHALL contain DeepEval suites for each live prompt — onboarding interview (extraction accuracy per fixture conversation, proposal quality rubric) and category suggestions (categorization accuracy and payee cleaning against labeled fixture rows). Suites SHALL run outside the default `pytest` invocation (they make live LLM calls) via a documented command, and the documented workflow SHALL require a green eval run before a prompt config's `version` is bumped.

#### Scenario: Extraction regression caught

- **WHEN** a prompt edit makes the model stop extracting `household.management_style` for a fixture answer that previously settled it
- **THEN** the onboarding eval suite fails before the version bump ships

#### Scenario: Default test run unaffected

- **WHEN** `uv run pytest` runs in CI
- **THEN** no eval (live LLM) test executes and suite duration is unchanged
