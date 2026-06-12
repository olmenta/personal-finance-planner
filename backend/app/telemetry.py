"""Sentry initialization — errors, traces, logs, and LLM (gen-AI) spans.

Dormant without SENTRY_DSN. GDPR posture: request bodies never attach, and
send_default_pii — which puts LLM prompts/completions (onboarding transcripts,
bank descriptions) inside gen-AI spans — is honored only outside production,
regardless of the flag (ai-onboarding spec: transcripts never reach telemetry
in prod). LLM *quality* telemetry is the separate llm-observability-evals
change.
"""

import logging

from .config import get_settings

logger = logging.getLogger(__name__)


def configure_sentry() -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        return

    import sentry_sdk
    from sentry_sdk.integrations.litellm import LiteLLMIntegration

    send_pii = settings.sentry_send_default_pii and settings.sentry_environment != "production"

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=send_pii,
        max_request_body_size="never",
        enable_logs=settings.sentry_enable_logs,
        stream_gen_ai_spans=True,
        integrations=[LiteLLMIntegration()],
    )

    logger.info(
        "sentry initialized (env=%s, logs=%s, llm_pii=%s)",
        settings.sentry_environment,
        settings.sentry_enable_logs,
        send_pii,
    )


def set_llm_conversation(conversation_id: str) -> None:
    """Group this request's gen-AI spans under one Sentry conversation thread.

    Scope-local (call once per request, before the LLM calls); a no-op when
    Sentry is not initialized.
    """
    import sentry_sdk.ai

    sentry_sdk.ai.set_conversation_id(conversation_id)
