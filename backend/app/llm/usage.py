"""Per-call usage and cost (llm-layer design D3). Content-free; a failure to
record never fails the user's request."""

import logging
from dataclasses import dataclass

from pydantic_ai import RunUsage
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import LlmUsage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UsageContext:
    """Where to record a run: the request's session and the user it ran for."""

    db: Session
    user_id: str | None


def cost_micro_eur(usage: RunUsage | None) -> int:
    """Pydantic AI prices the run (genai-prices) in USD; store micro-euros."""
    if usage is None or usage.cost is None:
        return 0
    return int(float(usage.cost) * get_settings().llm_usd_eur_rate * 1_000_000)


def record(
    ctx: UsageContext | None,
    *,
    route: str,
    model: str,
    usage: RunUsage | None,
    latency_ms: int,
    outcome: str,
) -> None:
    if ctx is None:
        return
    try:
        # Savepoint: a failed insert must not poison the request's transaction.
        with ctx.db.begin_nested():
            ctx.db.add(
                LlmUsage(
                    user_id=ctx.user_id,
                    route=route,
                    model=model,
                    input_tokens=usage.input_tokens if usage else 0,
                    output_tokens=usage.output_tokens if usage else 0,
                    cache_read_tokens=usage.cache_read_tokens if usage else 0,
                    cache_write_tokens=usage.cache_write_tokens if usage else 0,
                    cost_micro_eur=cost_micro_eur(usage),
                    latency_ms=latency_ms,
                    outcome=outcome,
                )
            )
    except Exception as error:  # never fail the user's request over metering
        logger.warning("llm usage not recorded (%s): %s", route, type(error).__name__)
