"""Reset the e2e database to a clean, seeded state.

The e2e database (olmenta_e2e in the local Postgres, docker-compose.yml) holds
no personal data: migrate to head, truncate every table, and run the dev
seed. The Playwright suite runs this before each spec file.

Run: uv run python -m app.e2e_reset
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from .config import get_settings


def _target(url: str) -> tuple[str, int, str]:
    """(host, port, database) — the pooler and direct hosts of a Neon branch
    count as the same target."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").replace("-pooler", "")
    return host, parsed.port or 5432, parsed.path.lstrip("/")


def main() -> None:
    settings = get_settings()
    app_url = settings.e2e_database_url
    migrations_url = settings.e2e_migrations_database_url
    if not app_url or not migrations_url:
        sys.exit("E2E_DATABASE_URL and E2E_MIGRATIONS_DATABASE_URL must be set")

    # Truncating is destructive: refuse anything that points at the dev database.
    # Dev and e2e may share a server (local Postgres), so compare the database
    # too, not only the host.
    e2e_targets = {_target(app_url), _target(migrations_url)}
    dev_targets = {_target(settings.database_url), _target(settings.alembic_url)}
    if len(e2e_targets) != 1 or e2e_targets & dev_targets:
        sys.exit("E2E database URLs must point at the e2e database only, never at dev")

    # Env vars beat .env values: alembic/env.py and the seed then target e2e.
    os.environ["DATABASE_URL"] = app_url
    os.environ["MIGRATIONS_DATABASE_URL"] = migrations_url
    get_settings.cache_clear()

    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(migrations_url)
    with engine.begin() as conn:
        tables = [t for t in inspect(conn).get_table_names() if t != "alembic_version"]
        if tables:
            names = ", ".join(f'"{t}"' for t in tables)
            conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    engine.dispose()

    from .seed import main as seed_main

    seed_main()
    print(f"Reset e2e database ({len(tables)} tables truncated)")


if __name__ == "__main__":
    main()
