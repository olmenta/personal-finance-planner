"""Application settings.

DATABASE_URL is required (no default — Postgres/Neon everywhere, no SQLite).
App traffic uses the Neon pooler host; Alembic migrations use the direct host
(MIGRATIONS_DATABASE_URL, falling back to DATABASE_URL).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    migrations_database_url: str | None = None
    test_database_url: str | None = None

    # AI category suggestions (import pipeline). Missing key degrades to
    # uncategorized staging — never blocks an import (design D5).
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-8"

    @property
    def alembic_url(self) -> str:
        return self.migrations_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
