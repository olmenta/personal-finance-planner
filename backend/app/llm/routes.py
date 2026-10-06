"""Logical routes -> model + settings (llm-layer design D1).

Adding a route means adding it here and calling it from a service. The model
of any route can be overridden with LLM_ROUTE_<ROUTE>_MODEL, from the
environment or backend/.env (e.g. LLM_ROUTE_ONBOARDING_MODEL=anthropic:claude-sonnet-4-6).
"""

import os
from dataclasses import dataclass, replace
from typing import Literal

from ..config import get_settings


@dataclass(frozen=True)
class RouteConfig:
    model: str  # "<provider>:<model id>", e.g. "anthropic:claude-haiku-4-5"
    max_tokens: int
    # tool: structured output through a tool call (works on every model);
    # native: provider-side JSON schema output where supported.
    output_mode: Literal["tool", "native"] = "tool"
    cache_instructions: bool = True
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None


ROUTES: dict[str, RouteConfig] = {
    # A bad onboarding loses the user; low volume, once per user.
    "onboarding": RouteConfig(model="anthropic:claude-sonnet-5", max_tokens=16000),
    # High volume classification with few-shot history; the user is waiting.
    "category_suggestions": RouteConfig(
        model="anthropic:claude-haiku-4-5", max_tokens=16000, cache_instructions=False
    ),
    # Offline LLM-as-judge for the eval suites.
    "judge": RouteConfig(model="anthropic:claude-opus-5", max_tokens=8000),
}


def route_config(route: str) -> RouteConfig:
    config = ROUTES[route]
    key = f"LLM_ROUTE_{route.upper()}_MODEL"
    extra = get_settings().model_extra or {}
    override = os.environ.get(key) or extra.get(key.lower()) or extra.get(key)
    return replace(config, model=override) if override else config
