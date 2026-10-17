"""Building the budget from the conversation: categories with a choice,
several amounts at once, any account (openspec change coach-budget-setup).
The coach runs on scripted models, never a live provider."""

import itertools
from datetime import date

import pytest
from pydantic_ai import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import func, select

from app import clock
from app.llm import override_route
from app.llm.fakes import _current_run
from app.models import Category, CategoryGroup, CoachAction, Transaction
from app.services.names import UnknownName, resolve_account

MONTH = "2026-10"
_ids = itertools.count()


@pytest.fixture(autouse=True)
def mid_october(monkeypatch):
    today = date(2026, 10, 14)
    monkeypatch.setattr(clock, "today_madrid", lambda: today)
    monkeypatch.setattr("app.services.overview.today_madrid", lambda: today)
    monkeypatch.setattr("app.services.entries.today_madrid", lambda: today)


def scripted(calls: list, widget: str | None = None) -> FunctionModel:
    """Play `calls` in order, then reply attaching the last result's ref."""

    def model(messages, info: AgentInfo) -> ModelResponse:
        _, returns = _current_run(messages)
        results = [r.content for r in returns]
        if len(results) < len(calls):
            name, args = calls[len(results)]
            return ModelResponse(parts=[ToolCallPart(name, args)])
        ref = (results[-1] or {}).get("ref") if results else None
        widgets = [{"type": widget, "ref": ref}] if widget and ref else []
        out = {"text": "Mira esto.", "widgets": widgets}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, out)])

    return FunctionModel(model)


def ask(client, model: FunctionModel, text: str = "hola") -> dict:
    with override_route("coach", model):
        response = client.post("/coach/messages", json={"text": text, "client_message_id": f"msg-{next(_ids):06d}"})
    assert response.status_code == 200, response.text
    return response.json()["reply"]


def ok(response) -> dict:
    assert response.status_code in (200, 201), response.text
    return response.json()


def widget(reply: dict, kind: str) -> dict:
    [found] = [w for w in reply["widgets"] if w["type"] == kind]
    return found["data"]["action"]


def groups(client) -> dict[str, str]:
    return {g["name"]: g["id"] for g in client.get("/categories").json()}


def mascotas(client) -> str:
    return ok(client.post("/categories", json={"name": "Mascotas", "group_id": groups(client)["Estilo de vida"]}))["id"]


VET = ("propose_category", {
    "name": "Veterinario", "group": "Estilo de vida", "similar": ["Mascotas", "Unicornios"],
    "for_transaction": {"amount": 15, "payee": "Clínica Vet"},
})


def vet_choice(client) -> dict:
    reply = ask(client, scripted([("find_categories", {"name": "Veterinario"}), VET], "category_choice"),
                "gasté 15 en el veterinario")
    return widget(reply, "category_choice")


def commit(client, action: dict, **choice):
    return client.post(f"/coach/actions/{action['id']}/commit",
                       json={"revision": action["revision"], "idempotency_key": f"key-{next(_ids):08d}", **choice})


def count(db, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where))


# ---- categories with a choice -------------------------------------------------------------


def test_a_similar_category_is_offered_and_nothing_is_created(client, db, user):
    mascotas(client)
    choice = vet_choice(client)
    p = choice["preview"]
    assert choice["kind"] == "category" and choice["status"] == "proposed"
    assert [s["name"] for s in p["similar"]] == ["Mascotas"]  # an invented name is dropped
    assert p["similar"][0]["reason"] == "meaning"
    assert next(g["name"] for g in p["groups"] if g["id"] == p["suggested_group_id"]) == "Estilo de vida"
    assert p["follow_up_title"] == "Record 15,00 € at Clínica Vet in Veterinario"
    assert count(db, Category, Category.user_id == user.id, Category.name == "Veterinario") == 0
    assert count(db, Transaction, Transaction.user_id == user.id) == 0


def test_using_the_existing_one_proposes_the_expense_there(client, db, user):
    mascotas_id = mascotas(client)
    choice = vet_choice(client)
    body = ok(client.post(f"/coach/actions/{choice['id']}/resolve", json={"category_id": mascotas_id}))
    assert body["action"]["status"] == "resolved" and body["action"]["can_undo"] is False
    follow = body["follow_up"]
    assert follow["kind"] == "transaction" and follow["status"] == "proposed"
    assert follow["preview"]["transaction"]["category_name"] == "Mascotas"
    assert follow["preview"]["transaction"]["amount_cents"] == 1500
    message = ok(client.get("/coach/conversation"))["messages"][-1]
    assert [w["type"] for w in message["widgets"]] == ["category_choice", "action_preview"]
    assert count(db, Category, Category.user_id == user.id, Category.name == "Veterinario") == 0


def test_creating_it_in_the_suggested_group(client, db, user):
    choice = vet_choice(client)
    body = ok(commit(client, choice, group_id=choice["preview"]["suggested_group_id"]))
    assert body["message"] is None and body["action"]["status"] == "applied"
    created = db.get(Category, body["action"]["result"]["category_id"])
    assert created.name == "Veterinario" and created.group.name == "Estilo de vida"
    assert body["follow_up"]["preview"]["transaction"]["category_name"] == "Veterinario"
    assert count(db, Transaction, Transaction.user_id == user.id) == 0  # still waiting for Confirm


def test_creating_it_in_a_new_group(client, db, user):
    choice = vet_choice(client)
    body = ok(commit(client, choice, new_group_name="Animales"))
    assert body["action"]["result"]["created_group"] is True
    assert db.get(Category, body["action"]["result"]["category_id"]).group.name == "Animales"


def test_a_new_group_with_an_existing_name_is_reused(client, db, user):
    choice = vet_choice(client)
    body = ok(commit(client, choice, new_group_name="comida"))
    assert body["action"]["result"]["created_group"] is False
    assert db.get(Category, body["action"]["result"]["category_id"]).group.name == "Comida"


def test_the_same_name_returns_the_existing_category(client, db, user):
    seen = []

    def model(messages, info):
        _, returns = _current_run(messages)
        if not returns:
            return ModelResponse(parts=[ToolCallPart("propose_category", {"name": "supermercado"})])
        seen.append(returns[0].content)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"text": "Usa Supermercado.", "widgets": []})])

    ask(client, FunctionModel(model))
    assert seen[0]["existing"] == "Supermercado"
    assert count(db, CoachAction, CoachAction.user_id == user.id) == 0


def test_a_choice_goes_stale_when_a_similar_category_appears(client, db, user):
    choice = vet_choice(client)
    client.post("/categories", json={"name": "Veterinaria", "group_id": groups(client)["Estilo de vida"]})
    response = commit(client, choice, group_id=choice["preview"]["suggested_group_id"])
    assert response.status_code == 409 and response.json()["detail"]["code"] == "action_stale"
    fresh = response.json()["detail"]["action"]
    assert "Veterinaria" in [s["name"] for s in fresh["preview"]["similar"]]
    assert count(db, Category, Category.user_id == user.id, Category.name == "Veterinario") == 0


def test_undo_removes_an_unused_category_and_its_new_group(client, db, user):
    choice = vet_choice(client)
    body = ok(commit(client, choice, new_group_name="Animales"))
    assert body["action"]["can_undo"] is True
    undone = ok(client.post(f"/coach/actions/{choice['id']}/undo"))
    assert undone["status"] == "undone"
    assert count(db, Category, Category.user_id == user.id, Category.name == "Veterinario") == 0
    assert count(db, CategoryGroup, CategoryGroup.user_id == user.id, CategoryGroup.name == "Animales") == 0
    assert db.get(CoachAction, body["follow_up"]["id"]).status == "cancelled"


def test_undo_is_refused_once_the_category_is_used(client, db, user):
    choice = vet_choice(client)
    body = ok(commit(client, choice, group_id=choice["preview"]["suggested_group_id"]))
    follow = body["follow_up"]
    ok(commit(client, follow))  # the expense is recorded in the new category
    response = client.post(f"/coach/actions/{choice['id']}/undo")
    assert response.status_code == 409 and response.json()["detail"]["code"] == "undo_not_possible"


# ---- several amounts at once ------------------------------------------------------------


BUDGET = ("propose_budget", {"items": [
    {"category": "Supermercado", "amount": 300}, {"category": "gasolina", "amount": "80"},
    {"category": "Ocio", "amount": "50,00"},
]})


def test_a_budget_of_three_categories_applies_and_undoes_together(client):
    client.post("/accounts", json={"name": "Banco", "type": "bank", "opening_balance_cents": 60000})
    tba = ok(client.get(f"/budget/{MONTH}"))["to_be_assigned_cents"]
    action = widget(ask(client, scripted([BUDGET], "action_preview")), "action_preview")
    assert action["kind"] == "assignments"
    assert action["title"] == "Set 3 categories: Supermercado 300,00 €, Gasolina 80,00 €, Ocio 50,00 €"
    assert len(action["preview"]["categories"]) == 3
    assert action["preview"]["to_be_assigned_after_cents"] == tba - 43000
    ok(commit(client, action))
    view = ok(client.get(f"/budget/{MONTH}"))
    assigned = {c["name"]: c["assigned_cents"] for g in view["groups"] for c in g["categories"]}
    assert (assigned["Supermercado"], assigned["Gasolina"], assigned["Ocio"]) == (30000, 8000, 5000)
    assert view["to_be_assigned_cents"] == tba - 43000
    ok(client.post(f"/coach/actions/{action['id']}/undo"))
    assert ok(client.get(f"/budget/{MONTH}"))["to_be_assigned_cents"] == tba


def test_a_category_with_payments_is_refused_in_a_budget(client, db, user):
    rent = next(c["id"] for g in client.get("/categories").json() for c in g["categories"] if c["name"] == "Alquiler")
    client.post(f"/categories/{rent}/schedules", json={"name": "Alquiler", "amount_cents": 85000, "pattern": "monthly"})
    seen = []

    def model(messages, info):
        _, returns = _current_run(messages)
        if not returns:
            return ModelResponse(parts=[ToolCallPart("propose_budget", {"items": [
                {"category": "Supermercado", "amount": 300}, {"category": "Alquiler", "amount": 850}]})])
        seen.append(returns[0].content)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"text": "ok", "widgets": []})])

    ask(client, FunctionModel(model))
    assert seen[0]["error"] == "assignment_from_payments" and "Alquiler" in seen[0]["message"]
    assert count(db, CoachAction, CoachAction.user_id == user.id) == 0


# ---- any account ------------------------------------------------------------------------


def test_a_cash_expense_by_account_type(client):
    client.post("/accounts", json={"name": "Banco", "type": "bank", "opening_balance_cents": 10000})
    call = ("propose_transaction", {"amount": 12, "payee": "Bar Pepe", "category": "Restaurantes",
                                    "account": "en metálico"})
    action = widget(ask(client, scripted([call], "action_preview"), "pagué 12 en efectivo en el bar"), "action_preview")
    assert action["preview"]["transaction"]["account_name"] == "Efectivo"
    ok(commit(client, action))
    [txn] = [t for t in client.get("/transactions").json() if t["amount_cents"] == -1200]
    cash = next(a["id"] for a in client.get("/accounts").json() if a["name"] == "Efectivo")
    assert txn["account_id"] == cash


def test_several_accounts_of_a_type_must_be_named():
    accounts = [("Monedero", "a", "cash"), ("Hucha", "b", "cash"), ("BBVA", "c", "bank")]
    assert resolve_account("banco", accounts) == "c"
    with pytest.raises(UnknownName, match="several cash accounts: Hucha, Monedero"):
        resolve_account("efectivo", accounts)
    assert resolve_account("hucha", accounts) == "b"


# ---- the e2e fake drives the same flows ------------------------------------------------


def test_fake_model_category_choice_and_budget(client):
    from app.llm.fakes import fake_model

    mascotas(client)
    client.post("/accounts", json={"name": "Banco", "type": "bank", "opening_balance_cents": 60000})
    choice = widget(ask(client, fake_model("e2e"), "gasté 15 en el veterinario"), "category_choice")
    assert [s["name"] for s in choice["preview"]["similar"]] == ["Mascotas"]
    assert choice["preview"]["follow_up_title"] == "Record 15,00 € at Veterinario in Veterinario"
    budget = widget(ask(client, fake_model("e2e"), "pon 300 en el súper, 80 en gasolina y 50 en ocio"),
                    "action_preview")
    assert budget["kind"] == "assignments" and len(budget["preview"]["categories"]) == 3
    cash = widget(ask(client, fake_model("e2e"), "pagué 12 en efectivo en el veterinario"), "category_choice")
    assert cash["command"]["for"]["account_name"] == "Efectivo"


def test_find_categories_lists_every_category_by_group(client):
    mascotas(client)
    seen = []

    def model(messages, info):
        _, returns = _current_run(messages)
        if not returns:
            return ModelResponse(parts=[ToolCallPart("find_categories", {"name": "Veterinario"})])
        seen.append(returns[0].content)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"text": "ok", "widgets": []})])

    ask(client, FunctionModel(model))
    found = seen[0]
    assert found["similar"] == [] and found["suggested_group"]
    assert "Mascotas" in found["categories_by_group"]["Estilo de vida"]
    assert "Supermercado" in found["categories_by_group"]["Comida"]

