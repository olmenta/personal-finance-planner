"""Dev MCP server (spec: dev-mcp-server). Unit tests need no network; the
integration tests run each tool against the FastAPI app on the test DB,
with the TestClient as the HTTP client."""

import json
from datetime import date

import pytest

from app.models import Transaction
from mcp_server import server as mcp_server_module
from mcp_server.client import OlmentaClient, ToolError, _message, is_loopback
from mcp_server.money import AmountError, eur, parse_euros
from mcp_server.resolve import NameError_, resolve
from mcp_server.server import _mcp_function
from mcp_server.tools import TOOLS, run_tool

SPECS = {spec.name: spec for spec in TOOLS}

# ---- unit -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "cents"),
    [(40, 4000), (12.5, 1250), ("12,49", 1249), ("1.234,56", 123456), ("1234.56", 123456),
     ("1.234", 123400), ("12 €", 1200), ("+3,50", 350)],
)
def test_parse_euros(value, cents):
    assert parse_euros(value) == cents


def test_parse_euros_rejects_text():
    with pytest.raises(AmountError):
        parse_euros("doce")


def test_eur_es_format():
    assert eur(123456) == "1.234,56 €"
    assert eur(-1249) == "−12,49 €"
    assert eur(5) == "0,05 €"


def test_resolve_exact_partial_and_accents():
    options = [("Supermercado", "s"), ("Transporte público", "t"), ("Transferencias", "x")]
    assert resolve("supermercado", options, "category") == "s"
    assert resolve("super", options, "category") == "s"
    assert resolve("transporte publico", options, "category") == "t"


def test_resolve_ambiguous_lists_candidates():
    options = [("Transporte público", "t"), ("Transferencias", "x")]
    with pytest.raises(NameError_) as error:
        resolve("trans", options, "category")
    assert "Transporte público" in str(error.value) and "Transferencias" in str(error.value)


def test_resolve_unknown_never_guesses():
    with pytest.raises(NameError_) as error:
        resolve("Mascotas", [("Supermercado", "s")], "category")
    assert "Don't invent" in str(error.value)


@pytest.mark.parametrize(
    ("url", "ok"),
    [("http://127.0.0.1:8000", True), ("http://localhost:8000", True), ("http://[::1]:8000", True),
     ("https://api.example.com", False), ("http://10.0.0.5:8000", False)],
)
def test_loopback_only(url, ok):
    assert is_loopback(url) is ok


def test_error_messages_are_actionable():
    assert _message(422, {"code": "insufficient_to_be_assigned", "available_cents": 3000}) == (
        "To Be Assigned only holds 30,00 €."
    )
    assert "category" in _message(422, {"code": "category_required"})


# ---- integration (FastAPI app on the test DB) ---------------------------------


@pytest.fixture
def olmenta(client):
    return OlmentaClient(client)


def call(olmenta, tool_name, /, **arguments):
    return run_tool(SPECS[tool_name], olmenta, arguments)


def test_add_expense_from_a_sentence(olmenta, client):
    result = call(olmenta, "add_transaction", amount=40, category="Supermercado", payee="Mercadona")
    assert result.startswith("Added −40,00 € · Supermercado")
    [row] = [t for t in client.get("/transactions").json() if t["payee_name"] == "Mercadona"]
    assert row["amount_cents"] == -4000


def test_euro_string_amount(olmenta, client):
    call(olmenta, "add_transaction", amount="12,49", category="Ocio")
    assert any(t["amount_cents"] == -1249 for t in client.get("/transactions").json())


def test_ambiguous_category_writes_nothing(olmenta, client):
    assert call(olmenta, "create_category", name="Transferencias", group="Transporte") == (
        "Created category Transferencias in Transporte."
    )
    before = len(client.get("/transactions").json())
    result = call(olmenta, "add_transaction", amount=5, category="Trans")
    assert result.startswith("Error:") and "Transporte público" in result
    assert len(client.get("/transactions").json()) == before


def test_move_money_from_to_be_assigned(olmenta):
    call(olmenta, "add_transaction", amount=1000, kind="income")
    result = call(olmenta, "move_money", amount=50, to_category="Restaurantes")
    assert "Moved 50,00 € from To Be Assigned to Restaurantes" in result
    assert "Restaurantes now has 50,00 € available" in result


def test_move_money_beyond_to_be_assigned_is_explained(olmenta):
    result = call(olmenta, "move_money", amount=999999, to_category="Restaurantes")
    assert result.startswith("Error: To Be Assigned only holds")


def test_budget_and_accounts_read(olmenta):
    call(olmenta, "add_transaction", amount=200, kind="income")
    assert "To Be Assigned: 200,00 €" in call(olmenta, "get_budget")
    assert "(cash, main)" in call(olmenta, "list_accounts")
    assert "## Comida" in call(olmenta, "list_categories")


def test_transfer_between_accounts(olmenta, client):
    client.post("/accounts", json={"name": "Banco B", "type": "bank"})
    result = call(olmenta, "create_transfer", amount=100, from_account="Efectivo", to_account="Banco B")
    assert result.startswith("Transferred 100,00 € from Efectivo to Banco B")


def test_review_and_apply(olmenta, client, db, user):
    account_id = next(a["id"] for a in client.get("/accounts").json() if a["is_main"])
    row = Transaction(
        user_id=user.id, account_id=account_id, category_id=None, date=date(2026, 6, 10),
        amount_cents=-4520, status="confirmed", source="import_custom",
        description="MERCADONA 123", dedupe_hash="mcp-review-1",
    )
    db.add(row)
    db.flush()

    listing = call(olmenta, "review_uncategorized")
    assert f"id {row.id}" in listing and "«MERCADONA 123»" in listing

    result = call(
        olmenta, "apply_review",
        items=[{"transaction_id": row.id, "category": "Supermercado", "note": "Compra semanal"}],
    )
    assert result == "Applied 1 of 1."
    db.refresh(row)
    assert row.description == "Compra semanal" and row.category_id is not None


def test_calls_logged_locally(olmenta, tmp_path, monkeypatch):
    log = tmp_path / "calls.jsonl"
    monkeypatch.setattr(mcp_server_module, "LOG_PATH", log)
    fn = _mcp_function(SPECS["list_categories"], olmenta)
    assert "## Comida" in fn()
    entry = json.loads(log.read_text().strip())
    assert entry["tool"] == "list_categories" and entry["ok"] is True and "ms" in entry


def test_api_down_gives_start_instructions():
    import httpx

    down = OlmentaClient(httpx.Client(base_url="http://127.0.0.1:9", timeout=1))
    assert "uv run uvicorn app.main:app" in call(down, "get_budget")
    with pytest.raises(ToolError):
        down.budget("2026-10")
