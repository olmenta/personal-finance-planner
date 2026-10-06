"""Entry point: `uv run python -m mcp_server` (stdio transport only)."""

import os
import sys

import httpx

from .client import DEFAULT_API_URL, OlmentaClient, is_loopback
from .server import build_server


def main() -> None:
    api_url = os.environ.get("OLMENTA_API_URL", DEFAULT_API_URL)
    if not is_loopback(api_url):
        # Dev-only by construction (design D5): never point at a shared API.
        sys.exit(
            f"olmenta-dev MCP: OLMENTA_API_URL={api_url!r} is not a local address. "
            "This server only talks to a backend on localhost."
        )
    http = httpx.Client(base_url=api_url, timeout=httpx.Timeout(60.0, connect=3.0))
    build_server(OlmentaClient(http)).run("stdio")


if __name__ == "__main__":
    main()
