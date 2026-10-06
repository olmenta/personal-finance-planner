"""Shared eval setup: route overrides for baselines and Logfire experiments."""

import os

from app.config import get_settings


def use_model(route: str, model: str | None) -> None:
    """Run a route on another model for this process (baseline comparisons)."""
    if model:
        os.environ[f"LLM_ROUTE_{route.upper()}_MODEL"] = model


def setup_observability() -> None:
    """Publish experiments to Logfire when a token is configured. The `evals`
    environment includes content: fixtures are synthetic or reviewed."""
    os.environ["LOGFIRE_ENVIRONMENT"] = "evals"
    get_settings.cache_clear()
    from app.llm.observability import configure_logfire

    configure_logfire()


def require_key() -> None:
    if not get_settings().anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set in backend/.env — evals make live calls.")
