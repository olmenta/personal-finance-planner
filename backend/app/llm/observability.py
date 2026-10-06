"""Logfire observability with the content policy as code (llm-layer design D4).

Dormant without LOGFIRE_TOKEN. LLM prompts and outputs are never exported in
production, whatever the flags say; elsewhere they are exported only when
LOGFIRE_INCLUDE_CONTENT=true (the developer's own dev project and data) or
in the `evals` environment (synthetic or reviewed fixtures). Request bodies,
endpoint argument values and SQL parameters never leave the process.
"""

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)

# Olmenta's financial fields, redacted wherever they appear as attribute keys
# (on top of Logfire's default patterns: passwords, tokens, cookies…).
SCRUB_PATTERNS: Sequence[str] = (
    "description",
    "payee",
    "note",
    "amount",
    "iban",
    "transcript",
    "extracted",
)


def include_llm_content(environment: str, flag: bool) -> bool:
    """The production rule lives here, not in configuration."""
    if environment == "production":
        return False
    return environment == "evals" or flag


def _no_request_values(request: Any, attributes: dict[str, Any]) -> dict[str, Any] | None:
    """FastAPI instrumentation would record parsed endpoint arguments (amounts,
    descriptions, notes). Keep only validation error *locations*, no values."""
    errors = attributes.get("errors")
    if not errors:
        return None
    return {"errors": [{"loc": e.get("loc"), "type": e.get("type")} for e in errors]}


# Written by `logfire auth` / the setup wizard (gitignored); Logfire reads it
# itself when no LOGFIRE_TOKEN is set.
CREDENTIALS_FILE = Path(".logfire") / "logfire_credentials.json"


def configure_logfire(app: Any = None, *, additional_span_processors: Sequence[Any] = ()) -> bool:
    """Set up Logfire for the API (and Pydantic AI). Returns whether it is on.
    On with LOGFIRE_TOKEN or a `.logfire/` credentials file in the working
    directory; `additional_span_processors` lets tests capture spans offline."""
    settings = get_settings()
    has_credentials = bool(settings.logfire_token) or CREDENTIALS_FILE.is_file()
    if not has_credentials and not additional_span_processors:
        return False

    import logfire

    logfire.configure(
        token=settings.logfire_token,
        send_to_logfire="if-token-present" if has_credentials else False,
        service_name="olmenta-api",
        environment=settings.logfire_environment,
        console=False,
        scrubbing=logfire.ScrubbingOptions(extra_patterns=list(SCRUB_PATTERNS)),
        additional_span_processors=list(additional_span_processors) or None,
    )
    include = include_llm_content(settings.logfire_environment, settings.logfire_include_content)
    logfire.instrument_pydantic_ai(include_content=include, include_binary_content=False)
    logfire.instrument_httpx(capture_headers=False, capture_request_body=False, capture_response_body=False)
    if app is not None:
        logfire.instrument_fastapi(
            app, capture_headers=False, request_attributes_mapper=_no_request_values
        )
    logger.info(
        "logfire initialized (env=%s, llm_content=%s)", settings.logfire_environment, include
    )
    return True
