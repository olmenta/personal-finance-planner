"""Deterministic stand-in models for end-to-end tests (coach-conversation
design D10). `LLM_ROUTE_COACH_MODEL=fake:e2e` makes the Playwright API run
the coach without a provider: a few phrasings map to the real tools, and the
reply only quotes what the tools returned. It only drives the e2e plumbing —
behavior quality is the eval suite's job. Refused in production.
"""

import re
import unicodedata

from pydantic_ai import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel

from ..config import get_settings


class FakeModelRefused(RuntimeError):
    pass


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.strip().casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _current_run(messages: list) -> tuple[str, list[ToolReturnPart]]:
    """The user prompt of this run and the tool results since."""
    start = 0
    prompt = ""
    for index, message in enumerate(messages):
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, UserPromptPart):
                    start, prompt = index, str(part.content)
    returns = [
        part
        for message in messages[start:]
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]
    return prompt, returns


EXPENSE = re.compile(r"gast[eé]\s+(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?)?\s+en\s+(.+)", re.IGNORECASE)


def _e2e(messages: list, info: AgentInfo) -> ModelResponse:
    prompt, returns = _current_run(messages)
    folded = _fold(prompt)
    last = returns[-1].content if returns else None

    def call(tool: str, args: dict) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(tool, args)])

    def reply(text: str, widgets: list[tuple[str, str]] = ()) -> ModelResponse:
        args = {"text": text, "widgets": [{"type": t, "ref": r} for t, r in widgets]}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])

    def refused(result: dict) -> ModelResponse:
        return reply(result.get("message") or result.get("error") or "No puedo hacerlo así.")

    if "simula un fallo" in folded:
        raise RuntimeError("simulated provider failure")

    if match := EXPENSE.search(prompt):
        if not returns:
            return call("propose_transaction", {"amount": match.group(1), "payee": match.group(2).strip(" .")})
        if "ref" in last:
            return reply("Te lo dejo listo: revísalo y confírmalo.", [("action_preview", last["ref"])])
        return refused(last)

    if "cuanto" in folded and "guardar" in folded:
        if not returns:
            return call("get_future_payments", {})
        payments = last.get("payments") or []
        if not payments:
            return reply("No tienes pagos futuros programados.")
        p = payments[0]
        return reply(f"Para {p['name']} necesitas apartar {p['needed_monthly']} al mes.",
                     [("future_payment", p["ref"])])

    if folded.startswith("cubre"):
        if not returns:
            return call("get_month", {})
        if returns[-1].tool_name == "get_month":
            over = next((r for r in last["reasons"] if r["code"] == "overspent_categories"), None)
            if over is None:
                return reply("No tienes categorías en negativo.")
            moves = [{"to": c["name"], "amount": c["amount"]} for c in over["categories"]]
            return call("propose_moves", {"moves": moves})
        if "ref" in last:
            return reply("Así quedarían cubiertas. Confírmalo si te parece bien.", [("action_preview", last["ref"])])
        return refused(last)

    return reply("Puedo ayudarte con tu mes: pregúntame algo o dime un gasto.")


FAKES = {"e2e": _e2e}


def fake_model(name: str) -> Model:
    settings = get_settings()
    if "production" in (settings.sentry_environment, settings.logfire_environment):
        raise FakeModelRefused("fake models are refused in production")
    if name not in FAKES:
        raise FakeModelRefused(f"unknown fake model {name!r}")
    return FunctionModel(FAKES[name], model_name=f"fake:{name}")
