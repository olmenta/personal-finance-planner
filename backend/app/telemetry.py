"""Sentry initialization — errors and logs.

Dormant without SENTRY_DSN. GDPR posture: request bodies never attach and
send_default_pii is honored only outside production. Traces and LLM
observability belong to Logfire (app/llm/observability.py), so Sentry
records no gen-AI spans and backend tracing defaults to off.
"""

import logging

from .config import get_settings

logger = logging.getLogger(__name__)


def configure_sentry() -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        return

    import sentry_sdk

    send_pii = settings.sentry_send_default_pii and settings.sentry_environment != "production"

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=send_pii,
        max_request_body_size="never",
        enable_logs=settings.sentry_enable_logs,
    )

    logger.info(
        "sentry initialized (env=%s, logs=%s, pii=%s)",
        settings.sentry_environment,
        settings.sentry_enable_logs,
        send_pii,
    )
