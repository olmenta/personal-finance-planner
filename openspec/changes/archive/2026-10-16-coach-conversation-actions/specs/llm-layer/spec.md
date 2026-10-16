## MODIFIED Requirements

### Requirement: One provider-agnostic LLM layer with logical routes

Every LLM and decision-model call in the backend SHALL go through the LLM layer (Pydantic AI), addressed by a logical route — never by a model id in service code and never through a provider SDK directly. A route SHALL map to a model, its settings (output mode, max tokens, effort, prompt caching, request timeout) and an optional fallback, defined in one configuration module and overridable per route from the environment. The routes `onboarding`, `category_suggestions` and `coach` SHALL exist. Besides single structured calls, the layer SHALL run agents with typed tools (`run_with_tools`) on a route, recording usage and observability the same way, and adding a route SHALL require no change outside that module and the calling service.

#### Scenario: Model changed by configuration

- **WHEN** `LLM_ROUTE_CATEGORY_SUGGESTIONS_MODEL` is set to another supported model
- **THEN** category suggestions run on that model with no code change

#### Scenario: Behavior preserved on the new layer

- **WHEN** the backend test suite runs after the port
- **THEN** onboarding (one retry, then unavailable; re-ask on a done turn without proposal) and category suggestions (chunk-level degradation to empty, never raising) behave exactly as before

#### Scenario: A tool-using agent on a route

- **WHEN** the coach service runs the `coach` route with its tools
- **THEN** the call goes through the LLM layer, the tools run in-process, and one `llm_usage` row is recorded for the run
