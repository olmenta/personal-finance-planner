"""Running a route on Pydantic AI (design D1, D2): one structured-output call
(`run_structured`) or an agent run with typed tools (`run_with_tools`).

Services call `run_structured(route, OutputModel, ...)` with OpenAI-style
messages (the shape they already build); this module turns them into
instructions + message history + prompt, picks the route's model and
settings, records usage, and returns the validated output.
"""

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic_ai import (
    Agent,
    ModelRequest,
    ModelResponse,
    NativeOutput,
    TextPart,
    Tool,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.usage import UsageLimits

from ..config import get_settings
from . import usage as usage_mod
from .routes import RouteConfig, route_config

# No promotional banner in API logs (observability is configured separately).
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

OutputT = TypeVar("OutputT", bound=BaseModel)

# Test seam: route -> model used instead of the configured one.
_overrides: dict[str, Model] = {}


class LLMUnavailable(RuntimeError):
    """No provider key configured for the route's model."""


@contextmanager
def override_route(route: str, model: Model) -> Iterator[None]:
    """Run a route on another model (tests: TestModel / FunctionModel)."""
    previous = _overrides.get(route)
    _overrides[route] = model
    try:
        yield
    finally:
        if previous is None:
            _overrides.pop(route, None)
        else:
            _overrides[route] = previous


def _model(route: str, config: RouteConfig) -> Model | str:
    if route in _overrides:
        return _overrides[route]
    provider, _, name = config.model.partition(":")
    if provider == "fake":
        # Deterministic stand-ins for e2e only (design D10); never in production.
        from .fakes import fake_model

        return fake_model(name)
    if provider == "anthropic":
        key = get_settings().anthropic_api_key
        if not key:
            raise LLMUnavailable("ANTHROPIC_API_KEY not set")
        return AnthropicModel(name, provider=AnthropicProvider(api_key=key))
    return config.model  # other providers resolve their keys from the environment


def _model_settings(config: RouteConfig) -> AnthropicModelSettings:
    settings: AnthropicModelSettings = {"max_tokens": config.max_tokens}
    if config.cache_instructions:
        settings["anthropic_cache_instructions"] = True
    if config.effort:
        settings["anthropic_effort"] = config.effort
    if config.timeout_s:
        settings["timeout"] = config.timeout_s
    return settings


def _split(messages: list[dict[str, str]]) -> tuple[str | None, list, str]:
    """[{role, content}] -> (instructions, history, last user prompt)."""
    system = [m["content"] for m in messages if m["role"] == "system"]
    turns = [m for m in messages if m["role"] != "system"]
    if not turns or turns[-1]["role"] != "user":
        raise ValueError("the last message must come from the user")
    history: list = []
    for turn in turns[:-1]:
        if turn["role"] == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=turn["content"])]))
        else:
            history.append(ModelResponse(parts=[TextPart(content=turn["content"])]))
    return ("\n\n".join(system) or None), history, turns[-1]["content"]


def run_structured(
    route: str,
    output_type: type[OutputT],
    messages: list[dict[str, str]],
    *,
    usage: usage_mod.UsageContext | None = None,
    conversation_id: str | None = None,
) -> OutputT:
    """One structured call on `route`. Raises on transport/validation errors;
    the calling service owns its retry and degradation behavior."""
    config = route_config(route)
    model = _model(route, config)
    instructions, history, prompt = _split(messages)
    agent: Agent[None, Any] = Agent(
        model,
        output_type=NativeOutput(output_type) if config.output_mode == "native" else output_type,
        instructions=instructions,
        model_settings=_model_settings(config),
        name=route,
    )
    model_name = config.model if route not in _overrides else f"override:{route}"
    started = time.monotonic()
    try:
        result = agent.run_sync(prompt, message_history=history, conversation_id=conversation_id)
    except Exception:
        usage_mod.record(
            usage,
            route=route,
            model=model_name,
            usage=None,
            latency_ms=round((time.monotonic() - started) * 1000),
            outcome="error",
        )
        raise
    usage_mod.record(
        usage,
        route=route,
        model=model_name,
        usage=result.usage,
        latency_ms=round((time.monotonic() - started) * 1000),
        outcome="ok",
    )
    return result.output


# A tool-using run may loop model → tool → model; bound it (cost and latency).
# Raised from 8: open questions about the month ("me he quedado sin trabajo")
# read several areas (month, income, debts) before answering.
MAX_TOOL_REQUESTS = 12


def run_with_tools(
    route: str,
    output_type: type[OutputT],
    messages: list[dict[str, str]],
    *,
    tools: list[Tool],
    deps: Any,
    usage: usage_mod.UsageContext | None = None,
    conversation_id: str | None = None,
) -> OutputT:
    """An agent run with typed tools on `route` (coach-conversation design D2):
    same model resolution, overrides, settings and usage recording as
    `run_structured`; the tools run in-process with `deps`."""
    config = route_config(route)
    model = _model(route, config)
    instructions, history, prompt = _split(messages)
    agent: Agent[Any, Any] = Agent(
        model,
        output_type=NativeOutput(output_type) if config.output_mode == "native" else output_type,
        instructions=instructions,
        model_settings=_model_settings(config),
        tools=tools,
        deps_type=type(deps),
        name=route,
    )
    model_name = config.model if route not in _overrides else f"override:{route}"
    started = time.monotonic()
    try:
        result = agent.run_sync(
            prompt,
            message_history=history,
            deps=deps,
            conversation_id=conversation_id,
            usage_limits=UsageLimits(request_limit=MAX_TOOL_REQUESTS),
        )
    except Exception:
        usage_mod.record(
            usage,
            route=route,
            model=model_name,
            usage=None,
            latency_ms=round((time.monotonic() - started) * 1000),
            outcome="error",
        )
        raise
    usage_mod.record(
        usage,
        route=route,
        model=model_name,
        usage=result.usage,
        latency_ms=round((time.monotonic() - started) * 1000),
        outcome="ok",
    )
    return result.output
