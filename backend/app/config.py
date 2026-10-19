"""Application settings.

DATABASE_URL is required (no default — Postgres/Neon everywhere, no SQLite).
Locally everything runs on the docker-compose Postgres (dev, test and e2e
databases). On Neon, app traffic uses the pooler host and Alembic migrations
the direct host (MIGRATIONS_DATABASE_URL, falling back to DATABASE_URL).
"""

from datetime import date
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="allow": per-route model overrides (LLM_ROUTE_<ROUTE>_MODEL) are
    # read from .env without declaring one field per route (app/llm/routes.py).
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    database_url: str
    migrations_database_url: str | None = None
    test_database_url: str | None = None
    # E2E database for the Playwright suite (see app/e2e_reset.py).
    e2e_database_url: str | None = None
    e2e_migrations_database_url: str | None = None
    # Pins "today" (app/clock.py) for the e2e suite; ignored in production.
    fixed_today: date | None = None

    # LLM provider key. Missing key degrades AI features (uncategorized
    # staging, onboarding unavailable) — never blocks an import. Models are
    # chosen per route in app/llm/routes.py, not here.
    anthropic_api_key: str | None = None
    # USD -> EUR for llm_usage costs (provider prices are in USD).
    llm_usd_eur_rate: float = 0.92

    # Logfire (EU project) — dormant without a token. LLM content is never
    # exported in production; elsewhere only when explicitly enabled
    # (app/llm/observability.py).
    logfire_token: str | None = None
    logfire_environment: str = "development"
    logfire_include_content: bool = False

    # Sentry error monitoring — dormant when no DSN is set. PII stays off:
    # never log or expose financial data in telemetry (GDPR).
    sentry_dsn: str | None = None
    sentry_environment: str = "development"
    # Traces belong to Logfire now; Sentry keeps errors and logs.
    sentry_traces_sample_rate: float = 0.0
    # Forward Python logging to Sentry Logs. Safe with our logging rules:
    # log lines never carry transcripts or financial data.
    sentry_enable_logs: bool = False
    # Sentry's own PII switch (request data). Forced off in production.
    sentry_send_default_pii: bool = False

    # Environment and authentication (spec: authentication, auth0-users D3).
    # local/test may run as the seeded development user; dev/beta/prod must
    # validate Auth0 tokens. The audience is the environment's API identifier
    # (https://api-dev|api-beta|api.olmenta.com), never shared.
    app_env: Literal["local", "test", "dev", "beta", "prod"] = "local"
    auth_mode: Literal["dev_user", "auth0"] = "dev_user"
    auth0_domain: str | None = None  # e.g. olmenta.eu.auth0.com (no scheme)
    auth0_audience: str | None = None

    @property
    def alembic_url(self) -> str:
        return self.migrations_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


class ConfigurationError(RuntimeError):
    pass


def check_auth_config(settings: Settings) -> None:
    """Refuse to serve with an unsafe auth setup: the development user only
    exists in local and test, and Auth0 needs its domain and audience."""
    if settings.auth_mode == "dev_user" and settings.app_env in ("dev", "beta", "prod"):
        raise ConfigurationError(
            f"AUTH_MODE=dev_user is not allowed with APP_ENV={settings.app_env}: set AUTH_MODE=auth0"
        )
    if settings.auth_mode == "auth0" and not (settings.auth0_domain and settings.auth0_audience):
        raise ConfigurationError("AUTH_MODE=auth0 needs AUTH0_DOMAIN and AUTH0_AUDIENCE")

