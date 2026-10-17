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
CASH = re.compile(r"pagu[eé]\s+(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?)?\s+en\s+efectivo\s+en\s+(.+)", re.IGNORECASE)
BUDGET = re.compile(r"^pon\s+(.+)$", re.IGNORECASE)
BUDGET_ITEM = re.compile(r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?)?\s+en\s+(?:el\s+|la\s+)?(.+)", re.IGNORECASE)
ARTICLE = re.compile(r"^(el|la|los|las)\s+", re.IGNORECASE)
PAYMENT = re.compile(r"^el\s+(.+?)\s+son\s+(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?)?\s+al\s+mes(?:,?\s+el\s+d[ií]a\s+(\d+))?", re.IGNORECASE)
RAISE = re.compile(r"^el\s+(.+?)\s+sube\s+a\s+(\d+(?:[.,]\d{1,2})?)", re.IGNORECASE)
INCOME = re.compile(r"^cobro\s+(\d+(?:[.,]\d{1,2})?)(?:\s*(?:€|euros?))?(?:\s+al\s+mes)?(?:,?\s+el\s+d[ií]a\s+(\d+))?", re.IGNORECASE)
SALARY_RAISE = re.compile(r"^mi\s+sueldo\s+sube\s+a\s+(\d+(?:[.,]\d{1,2})?)", re.IGNORECASE)
# Meaning-based matches a real model would add (e2e only).
MEANING = {"veterinario": ["Mascotas"]}


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

    if match := (CASH.search(prompt) or EXPENSE.search(prompt)):
        amount, payee = match.group(1), match.group(2).strip(" .")
        name = ARTICLE.sub("", payee)
        title = name[:1].upper() + name[1:]
        account = {"account": "efectivo"} if CASH.search(prompt) else {}
        if not returns:
            return call("propose_transaction", {"amount": amount, "payee": payee, **account})
        tool = returns[-1].tool_name
        if "ref" in last:
            if last["ref"].startswith("choice:"):
                return reply("Elige una categoría parecida o crea la nueva.", [("category_choice", last["ref"])])
            return reply("Te lo dejo listo: revísalo y confírmalo.", [("action_preview", last["ref"])])
        if tool == "propose_transaction" and "Which category" in str(last.get("error", "")):
            return call("find_categories", {"name": name})
        if tool == "find_categories":
            return call("propose_category", {
                "name": title, "group": last.get("suggested_group"), "similar": MEANING.get(_fold(name), []),
                "for_transaction": {"amount": amount, "payee": title, **account},
            })
        if tool == "propose_category" and last.get("existing"):
            return call("propose_transaction", {"amount": amount, "payee": payee, "category": last["existing"], **account})
        return refused(last)

    if match := INCOME.search(prompt.strip()):
        if not returns:
            args = {"name": "Nómina", "amount": match.group(1), "pattern": "monthly"}
            if match.group(2):
                args["day"] = int(match.group(2))
            return call("propose_income", args)
        if "ref" in last:
            return reply("Así quedaría tu ingreso esperado. Confírmalo si es correcto.", [("action_preview", last["ref"])])
        return refused(last)

    if match := SALARY_RAISE.search(prompt.strip()):
        if not returns:
            return call("get_income", {})
        if returns[-1].tool_name == "get_income":
            payments = last.get("payments") or []
            if not payments:
                return reply("Todavía no tienes ingresos esperados.")
            return call("propose_income_change", {"income": payments[0]["name"], "amount": match.group(1)})
        if "ref" in last:
            return reply("Te dejo el cambio listo para confirmar.", [("action_preview", last["ref"])])
        return refused(last)

    if match := PAYMENT.search(prompt.strip()):
        name = match.group(1)[:1].upper() + match.group(1)[1:]
        if not returns:
            args = {"category": name, "name": name, "amount": match.group(2), "pattern": "monthly"}
            if match.group(3):
                args["day"] = int(match.group(3))
            return call("propose_payment", args)
        if "ref" in last:
            return reply("Así quedaría el pago. Confírmalo si es correcto.", [("action_preview", last["ref"])])
        return refused(last)

    if match := RAISE.search(prompt.strip()):
        if not returns:
            return call("propose_payment_change", {"payment": match.group(1), "amount": match.group(2)})
        if "ref" in last:
            return reply("Te dejo el cambio listo para confirmar.", [("action_preview", last["ref"])])
        return refused(last)

    if match := BUDGET.search(prompt.strip()):
        if not returns:
            parts = re.split(r",\s*|\s+y\s+", match.group(1))
            items = [{"amount": m.group(1), "category": m.group(2).strip(" .")}
                     for m in (BUDGET_ITEM.search(p) for p in parts) if m]
            return call("propose_budget", {"items": items})
        if "ref" in last:
            return reply("Así quedaría tu presupuesto. Confírmalo si te parece bien.", [("action_preview", last["ref"])])
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
