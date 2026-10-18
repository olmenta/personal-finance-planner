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


# ---- similar categories first, budgets, accounts by type (coach-budget-setup) ----


def test_near_duplicate_category_is_caught(olmenta, client):
    result = call(olmenta, "create_category", name="Super", group="Comida")
    assert result.startswith("Nothing created") and "Supermercado (Comida)" in result
    assert "confirmed_new=true" in result
    names = [c["name"] for g in client.get("/categories").json() for c in g["categories"]]
    assert "Super" not in names


def test_created_after_the_user_confirms(olmenta, client):
    result = call(olmenta, "create_category", name="Super", group="Comida", confirmed_new=True)
    assert result == "Created category Super in Comida."


def test_group_missing_lists_the_groups(olmenta):
    result = call(olmenta, "create_category", name="Veterinario")
    assert result.startswith("Nothing created") and "suggested" in result and "Comida" in result


def test_exact_name_uses_the_existing_category(olmenta):
    result = call(olmenta, "create_category", name="supermercado", group="Comida", confirmed_new=True)
    assert result == "Nothing created: «Supermercado» already exists in Comida. Use it."


def test_find_categories(olmenta):
    result = call(olmenta, "find_categories", name="transporte")
    assert "Transporte público (Transporte) [contains]" in result and "Suggested group" in result


def test_create_group_with_similarity(olmenta, client):
    assert call(olmenta, "create_group", name="comida").startswith("Nothing created: the group «Comida»")
    assert call(olmenta, "create_group", name="Comidas fuera").startswith("Nothing created. Similar groups")
    assert call(olmenta, "create_group", name="Mascotas") == "Created group Mascotas."


def test_set_budget(olmenta, client):
    client.post("/accounts", json={"name": "Banco", "type": "bank", "opening_balance_cents": 60000})
    result = call(olmenta, "set_budget", items=[
        {"category": "Supermercado", "amount": 300}, {"category": "Gasolina", "amount": "80"}])
    assert result.startswith("Set for") and "Supermercado 300,00 €; Gasolina 80,00 €" in result


def test_set_budget_bad_name_writes_nothing(olmenta, client):
    from mcp_server.money import current_month

    result = call(olmenta, "set_budget", items=[
        {"category": "Supermercado", "amount": 300}, {"category": "Unicornios", "amount": 10}])
    assert result.startswith("Error:")
    budget = client.get(f"/budget/{current_month()}").json()
    assigned = {c["name"]: c["assigned_cents"] for g in budget["groups"] for c in g["categories"]}
    assert assigned["Supermercado"] == 0


def test_set_budget_refuses_categories_with_payments(olmenta, client):
    rent = next(c["id"] for g in client.get("/categories").json() for c in g["categories"] if c["name"] == "Alquiler")
    client.post(f"/categories/{rent}/schedules", json={"name": "Alquiler", "amount_cents": 85000, "pattern": "monthly"})
    result = call(olmenta, "set_budget", items=[{"category": "Supermercado", "amount": 300},
                                               {"category": "Alquiler", "amount": 900}])
    assert result.startswith("Error:") and "Alquiler" in result and "Nothing was set" in result


def test_cash_account_by_type(olmenta, client):
    client.post("/accounts", json={"name": "Banco", "type": "bank", "opening_balance_cents": 0})
    result = call(olmenta, "add_transaction", amount=12, category="Restaurantes", account="efectivo")
    assert "Efectivo" in result


# ---- payments (coach-payments-setup) ------------------------------------------------


def test_add_a_monthly_payment(olmenta, client):
    result = call(olmenta, "add_payment", category="Alquiler", name="Alquiler", amount=850, pattern="monthly", day=1)
    assert result.startswith("Added payment Alquiler: 850,00 € every month, day 1.")
    assert "Alquiler now gets 850,00 €" in result


def test_list_update_and_delete_payments(olmenta, client):
    call(olmenta, "add_payment", category="Suministros", name="Colegio", amount="632", pattern="some_months",
         months=[9, 10, 11, 12, 1, 2, 3, 4, 5, 6], day=5)
    assert "632,00 € from September to June, day 5" in call(olmenta, "list_payments")
    changed = call(olmenta, "update_payment", payment="colegio", amount=650)
    assert "632,00 € from September to June, day 5 → 650,00 € from September to June, day 5" in changed
    assert call(olmenta, "delete_payment", payment="Colegio").startswith("Removed Colegio")
    assert call(olmenta, "list_payments") == "No payments yet."


def test_a_debt_payment_is_refused(olmenta, client):
    client.post("/debts", json={"kind": "loan", "name": "Ikea", "installment_cents": 4500,
                                "installments_left": 10, "next_month": "2026-10"})
    assert "managed in What you owe" in call(olmenta, "list_payments")
    result = call(olmenta, "update_payment", payment="Ikea", amount=50)
    assert result.startswith("Error:") and "What you owe" in result


def test_unknown_category_points_to_find_categories(olmenta):
    result = call(olmenta, "add_payment", category="Gimnasio", name="Gimnasio", amount=35, pattern="monthly")
    assert result.startswith("Error:") and "find_categories" in result


def test_horizon_refusal(olmenta):
    result = call(olmenta, "add_payment", category="Ocio", name="Viaje", amount=2000, pattern="once",
                  once_month="2045-01")
    assert result.startswith("Error:") and "planning horizon" in result


# ---- expected income (coach-income-setup) -----------------------------------------


def test_add_a_salary(olmenta):
    result = call(olmenta, "add_income", name="Nómina", amount=2100, pattern="monthly", day=28, payer="Acme")
    assert result.startswith("Added expected income Nómina: 2.100,00 € every month, day 28, from Acme.")
    assert "Expected over the next 12 months: 25.200,00 €" in result


def test_update_list_and_delete_income(olmenta):
    call(olmenta, "add_income", name="Nómina", amount=2100, pattern="monthly", payer="Acme")
    assert "→ 2.200,00 € every month, from Acme" in call(olmenta, "update_income", income="acme", amount=2200)
    assert "Nómina: 2.200,00 € every month, from Acme" in call(olmenta, "list_income")
    assert call(olmenta, "delete_income", income="Nómina").startswith("Removed Nómina")
    assert call(olmenta, "list_income").startswith("No expected income yet")


def test_no_date_income_is_refused(olmenta):
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        call(olmenta, "add_income", name="Bonus", amount=1000, pattern="no_date")


def test_unknown_income_lists_candidates(olmenta):
    call(olmenta, "add_income", name="Nómina", amount=2100, pattern="monthly")
    result = call(olmenta, "update_income", income="pensión", amount=10)
    assert result.startswith("Error:") and "Nómina" in result


# ---- debts (coach-debts-setup) ---------------------------------------------------


def test_add_a_loan(olmenta):
    result = call(olmenta, "add_debt", kind="loan", name="Ikea", installment=45, installments_left=10,
                  next_month="2026-11")
    assert result.startswith("Added: 1. Ikea (loan): owes 450,00 €; 45,00 € × 10 installments")
    assert "Total owed 450,00 €" in result


def test_a_card_by_type_with_a_plan(olmenta, client):
    client.post("/accounts", json={"name": "Visa", "type": "credit", "opening_balance_cents": -63462})
    result = call(olmenta, "add_debt", kind="card", account="tarjeta", plan_monthly=200, rate_percent=1.5,
                  rate_per="month")
    assert "Visa (card): owes 634,62 €; 200,00 € a month; 1,50 % a month" in result


def test_update_delete_and_extra(olmenta, client):
    call(olmenta, "add_debt", kind="loan", name="Ikea", installment=45, installments_left=10, next_month="2026-11")
    assert "45,00 € × 8 installments" in call(olmenta, "update_debt", debt="ikea", installments_left=8)
    assert "It goes to Ikea first." in call(olmenta, "set_debt_extra", amount=50)
    assert call(olmenta, "delete_debt", debt="Ikea").startswith("Removed the plan of Ikea")
    assert call(olmenta, "list_debts") == "No debts yet."


def test_a_second_debt_on_a_card_is_refused(olmenta, client):
    client.post("/accounts", json={"name": "Visa", "type": "credit", "opening_balance_cents": -63462})
    call(olmenta, "add_debt", kind="card", account="Visa", plan_monthly=200)
    result = call(olmenta, "add_debt", kind="card", account="Visa", plan_monthly=100)
    assert result.startswith("Error:") and "update_debt" in result
