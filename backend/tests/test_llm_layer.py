"""LLM layer (spec: llm-layer): routes, usage records, and the observability
content policy. No live model calls — TestModel / FunctionModel stand in."""

import json
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from pydantic import BaseModel
from pydantic_ai import Agent, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from sqlalchemy import select

from app.ingestion import NormalizedTransaction
from app.llm import UsageContext, override_route, run_structured
from app.llm import observability, usage as usage_mod
from app.llm.routes import ROUTES, route_config
from app.models import Category, LlmUsage
from app.services import category_suggestions

PLANTED = "planted-bank-text-mercadona"


class Turn(BaseModel):
    message: str


# ---- routes -------------------------------------------------------------------


def test_default_routes():
    assert ROUTES["onboarding"].model == "anthropic:claude-sonnet-5"
    assert ROUTES["category_suggestions"].model == "anthropic:claude-haiku-4-5"


def test_route_model_overridden_from_environment(monkeypatch):
    monkeypatch.setenv("LLM_ROUTE_CATEGORY_SUGGESTIONS_MODEL", "anthropic:claude-sonnet-5")
    assert route_config("category_suggestions").model == "anthropic:claude-sonnet-5"


def test_messages_become_instructions_history_and_prompt():
    seen = {}

    def model(messages, info: AgentInfo) -> ModelResponse:
        seen["instructions"] = info.instructions
        seen["parts"] = [type(p).__name__ for m in messages for p in m.parts]
        args = {"message": "ok"}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])

    with override_route("onboarding", FunctionModel(model)):
        out = run_structured(
            "onboarding",
            Turn,
            [
                {"role": "system", "content": "be kind"},
                {"role": "user", "content": "hola"},
                {"role": "assistant", "content": "¿qué tal?"},
                {"role": "user", "content": "bien"},
            ],
        )
    assert out.message == "ok"
    assert seen["instructions"] == "be kind"
    assert seen["parts"].count("UserPromptPart") == 2 and "TextPart" in seen["parts"]


# ---- usage ----------------------------------------------------------------------


def _suggestion_setup(db, user):
    category = db.scalar(select(Category).where(Category.user_id == user.id, Category.name == "Supermercado"))
    row = NormalizedTransaction(
        date=date(2026, 6, 1), amount_cents=-4520, currency="EUR",
        description=f"COMPRA {PLANTED}", category_hint=None,
    )
    output = {"suggestions": [{"row": 0, "category_id": category.id, "payee": "Mercadona", "confidence": "high"}]}
    return category, row, TestModel(custom_output_args=output)


def test_suggestion_run_records_usage_without_content(db, user, monkeypatch):
    category, row, model = _suggestion_setup(db, user)
    monkeypatch.setattr(category_suggestions, "get_settings", lambda: SimpleNamespace(anthropic_api_key="sk"))
    with override_route("category_suggestions", model):
        result = category_suggestions.suggest([category], [row], usage=UsageContext(db, user.id))
    assert result[0].category_id == category.id

    [record] = db.scalars(select(LlmUsage).where(LlmUsage.user_id == user.id)).all()
    assert record.route == "category_suggestions" and record.outcome == "ok"
    assert record.input_tokens > 0 and record.output_tokens > 0 and record.cost_micro_eur >= 0
    stored = json.dumps({c.name: getattr(record, c.name) for c in LlmUsage.__table__.columns}, default=str)
    assert PLANTED not in stored and "Mercadona" not in stored


def test_recording_failure_is_harmless(db, user, monkeypatch, caplog):
    category, row, model = _suggestion_setup(db, user)
    monkeypatch.setattr(category_suggestions, "get_settings", lambda: SimpleNamespace(anthropic_api_key="sk"))

    def broken(**_):
        raise RuntimeError("db down")

    monkeypatch.setattr(usage_mod, "LlmUsage", broken)
    with override_route("category_suggestions", model):
        result = category_suggestions.suggest([category], [row], usage=UsageContext(db, user.id))
    assert result[0].category_id == category.id
    assert "llm usage not recorded" in caplog.text


def test_cost_converted_to_micro_euros(monkeypatch):
    from decimal import Decimal

    from pydantic_ai import RunUsage

    monkeypatch.setattr(usage_mod, "get_settings", lambda: SimpleNamespace(llm_usd_eur_rate=0.5))
    assert usage_mod.cost_micro_eur(RunUsage(cost=Decimal("0.002"))) == 1000
    assert usage_mod.cost_micro_eur(None) == 0


# ---- observability content policy -------------------------------------------------


@pytest.mark.parametrize(
    ("environment", "flag", "expected"),
    [("production", True, False), ("production", False, False), ("development", False, False),
     ("development", True, True), ("dogfood", True, True), ("evals", False, True)],
)
def test_content_policy(environment, flag, expected):
    assert observability.include_llm_content(environment, flag) is expected


@pytest.fixture
def captured_spans(monkeypatch):
    """Configure Logfire against an in-memory exporter; undo instrumentation after."""
    from logfire.testing import TestExporter

    exporter = TestExporter()

    def configure(environment: str, include_content: bool, app=None):
        monkeypatch.setattr(
            observability,
            "get_settings",
            lambda: SimpleNamespace(
                logfire_token=None, logfire_environment=environment,
                logfire_include_content=include_content,
            ),
        )
        assert observability.configure_logfire(app, additional_span_processors=[SimpleSpanProcessor(exporter)])
        return exporter

    yield configure
    Agent.instrument_all(False)


def _exported_text(exporter) -> str:
    return json.dumps(exporter.exported_spans_as_dict(), default=str)


def _run_with_secret():
    def model(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"message": f"reply {PLANTED}"})])

    with override_route("onboarding", FunctionModel(model)):
        run_structured("onboarding", Turn, [{"role": "user", "content": f"gasté 40 en {PLANTED}"}])


def test_production_never_exports_llm_content(captured_spans):
    exporter = captured_spans("production", include_content=True)
    _run_with_secret()
    text = _exported_text(exporter)
    assert "onboarding" in text  # the run is traced…
    assert PLANTED not in text  # …without prompt or output


def test_dev_exports_content_only_when_enabled(captured_spans):
    exporter = captured_spans("development", include_content=True)
    _run_with_secret()
    assert PLANTED in _exported_text(exporter)  # proves the check above can see content


def test_request_values_never_exported(captured_spans):
    app = FastAPI()

    class Body(BaseModel):
        description: str
        amount_cents: int

    @app.post("/echo")
    def echo(body: Body) -> dict:
        return {"ok": True}

    exporter = captured_spans("development", include_content=True, app=app)
    TestClient(app).post("/echo", json={"description": PLANTED, "amount_cents": 4520})
    text = _exported_text(exporter)
    assert "/echo" in text and PLANTED not in text and "4520" not in text


def test_no_token_no_exporter(monkeypatch):
    monkeypatch.setattr(
        observability, "get_settings",
        lambda: SimpleNamespace(logfire_token=None, logfire_environment="development", logfire_include_content=False),
    )
    assert observability.configure_logfire() is False


def test_text_part_import_kept():  # TextPart used by the layer for history turns
    assert TextPart(content="x").content == "x"
