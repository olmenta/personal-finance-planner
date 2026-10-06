# Evals

Eval suites for the live prompts, built with `pydantic_evals` (spec: `llm-layer`). They make **live model calls**, which cost money, so `pytest` never collects them.

```bash
cd backend
uv run python -m evals category_suggestions            # route defaults
uv run python -m evals onboarding
uv run python -m evals onboarding --model anthropic:claude-sonnet-4-6   # compare another model
```

- **Results:** a table in the terminal and, when `LOGFIRE_TOKEN` is set, an experiment in Logfire. The `evals` environment includes LLM content because the fixtures are synthetic.
- **Requirement:** `ANTHROPIC_API_KEY` must be set in `backend/.env`.

| Suite | Cases | Evaluators |
|---|---|---|
| `onboarding` | Synthetic interview answers plus one full interview | Expected extraction fields settled (or deliberately not settled when the user skips); proposal shape (cards are credit accounts, loans are categories); an LLM judge (route `judge`) on proposal quality |
| `category_suggestions` | Labeled Spanish bank rows against the default tree | Category accuracy; payee normalization |

## Rule: no prompt-version bump without an eval run

Before bumping `version` in a prompt file (`app/prompts/*.md`) or changing a route's model:

1. Run the affected suite on the current version or model. That's the baseline; skip this step if the last recorded run is recent.
2. Make the change and run the suite again.
3. Ship only if no evaluator that passed before now fails. Record the pass rates in the change's design (or in Logfire experiments).

Add a case whenever a real conversation or bank row exposes a mistake. The `dev-mcp-server` call log and your own categorized history are the main sources.
