"""Debts from the conversation: add, change, remove, extra, convert, with
previews and undo (openspec change coach-debts-setup). Scripted models only."""

import itertools
from datetime import date

import pytest
from pydantic_ai import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app import clock
from app.llm import override_route
from app.llm.fakes import _current_run

_ids = itertools.count()


@pytest.fixture(autouse=True)
def mid_october(monkeypatch):
    today = date(2026, 10, 14)
    monkeypatch.setattr(clock, "today_madrid", lambda: today)
    monkeypatch.setattr("app.routers.accounts.today_madrid", lambda: today)
    monkeypatch.setattr("app.services.overview.today_madrid", lambda: today)
    monkeypatch.setattr("app.services.entries.today_madrid", lambda: today)


def run_tool(client, name: str, args: dict) -> tuple[dict, dict]:
    seen = []

    def model(messages, info: AgentInfo) -> ModelResponse:
        _, returns = _current_run(messages)
        if not returns:
            return ModelResponse(parts=[ToolCallPart(name, args)])
        seen.append(returns[0].content)
        ref = returns[0].content.get("ref")
        out = {"text": "Mira.", "widgets": [{"type": "action_preview", "ref": ref}] if ref else []}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, out)])

    with override_route("coach", FunctionModel(model)):
        response = client.post("/coach/messages", json={"text": "hola", "client_message_id": f"debt-{next(_ids):06d}"})
    assert response.status_code == 200, response.text
    return seen[0], response.json()["reply"]


def action_of(reply: dict) -> dict:
    [w] = [w for w in reply["widgets"] if w["type"] == "action_preview"]
    return w["data"]["action"]


def ok(response) -> dict:
    assert response.status_code in (200, 201), response.text
    return response.json()


def commit(client, action: dict):
    return client.post(f"/coach/actions/{action['id']}/commit",
                       json={"revision": action["revision"], "idempotency_key": f"key-{next(_ids):08d}"})


def card(client, name="Visa", owed=63462) -> str:
    return ok(client.post("/accounts", json={"name": name, "type": "credit", "opening_balance_cents": -owed}))["id"]


def debts(client) -> dict:
    return ok(client.get("/debts"))


VISA = {"kind": "card", "account": "visa", "plan_monthly": 200, "rate_percent": 1.5, "rate_per": "month"}


def visa_debt(client) -> str:
    """A Visa card debt with a 200,00 € plan, through the API."""
    view = ok(client.post("/debts", json={"kind": "card", "account_id": card(client), "plan_monthly_cents": 20000,
                                          "rate_bp": 150, "rate_period": "month"}))
    return view["debts"][0]["id"]


def test_a_card_with_a_plan(client):
    card(client)
    client.get("/budget/2026-10")
    _, reply = run_tool(client, "propose_debt", VISA)
    action = action_of(reply)
    d = action["preview"]["debt"]
    assert action["kind"] == "debt" and action["title"] == "Add debt: Visa"
    assert d["after"]["position"] == 1 and d["after"]["end_month"] == "2027-01"
    assert d["after"]["text"] == "200,00 € a month · done in January 2027"
    assert d["debt_free_after"] == "2027-01"
    assert action["preview"]["categories"][0]["assigned_after_cents"] == 20000
    assert debts(client)["debts"] == []
    ok(commit(client, action))
    assert debts(client)["debts"][0]["plan_monthly_cents"] == 20000


def test_a_card_by_target_month(client):
    card(client)
    _, reply = run_tool(client, "propose_debt", {"kind": "card", "account": "Visa", "target_month": "2027-01"})
    assert action_of(reply)["preview"]["debt"]["after"]["text"] == "158,66 € a month · done in January 2027"


def test_a_loan_from_fields(client):
    _, reply = run_tool(client, "propose_debt", {"kind": "loan", "name": "Préstamo coche", "installment": "290,17",
                                                 "installments_left": 34, "next_month": "2026-11", "day": 2})
    text = action_of(reply)["preview"]["debt"]["after"]["text"]
    assert text.startswith("290,17 € × 34 from November 2026, day 2")


def test_a_personal_debt_without_a_date_never_ends(client):
    _, reply = run_tool(client, "propose_debt", {"kind": "personal", "name": "Hermano", "owed": 670,
                                                 "lender": "Juan"})
    d = action_of(reply)["preview"]["debt"]
    assert d["after"]["text"] == "670,00 €, no date, to Juan"
    assert d["debt_free_after"] is None


def test_a_card_without_a_minimum(client):
    card(client)
    _, reply = run_tool(client, "propose_debt", VISA)
    assert action_of(reply)["preview"]["debt"]["after"]["below_minimum"] is None


def test_a_second_debt_on_the_same_card_is_refused(client):
    visa_debt(client)
    result, _ = run_tool(client, "propose_debt", VISA)
    assert result["error"] == "debt_exists"


def test_what_if_extra_with_the_cushion_note(client):
    visa_debt(client)
    ok(client.post("/debts", json={"kind": "loan", "name": "Ikea", "installment_cents": 4500,
                                   "installments_left": 10, "next_month": "2026-10"}))
    _, reply = run_tool(client, "propose_debt_extra", {"amount": 100})
    action = action_of(reply)
    d = action["preview"]["debt"]
    assert action["title"] == "Pay 100,00 € extra a month on debts"
    assert d["debt_free_after"] < d["debt_free_before"]
    assert d["extra_target"] == "Visa" and d["cushion_note"] is True
    ok(client.post(f"/coach/actions/{action['id']}/cancel"))
    assert debts(client)["extra_monthly_cents"] == 0


def test_change_and_undo(client):
    visa_debt(client)
    _, reply = run_tool(client, "propose_debt_change", {"debt": "visa", "plan_monthly": 250})
    change = action_of(reply)
    assert change["preview"]["debt"]["before"]["text"].startswith("200,00 € a month")
    assert change["preview"]["debt"]["after"]["text"].startswith("250,00 € a month")
    ok(commit(client, change))
    assert debts(client)["debts"][0]["plan_monthly_cents"] == 25000
    assert ok(client.post(f"/coach/actions/{change['id']}/undo"))["status"] == "undone"
    assert debts(client)["debts"][0]["plan_monthly_cents"] == 20000


def test_removal_and_undo(client):
    visa_debt(client)
    _, reply = run_tool(client, "propose_debt_removal", {"debt": "Visa"})
    removal = action_of(reply)
    assert removal["title"] == "Remove the plan of Visa"
    ok(commit(client, removal))
    assert debts(client)["debts"] == []
    ok(client.post(f"/coach/actions/{removal['id']}/undo"))
    [back] = debts(client)["debts"]
    assert (back["name"], back["plan_monthly_cents"], back["rate_bp"]) == ("Visa", 20000, 150)


def test_extra_and_undo(client):
    visa_debt(client)
    _, reply = run_tool(client, "propose_debt_extra", {"amount": 100})
    extra = action_of(reply)
    ok(commit(client, extra))
    assert debts(client)["extra_monthly_cents"] == 10000
    ok(client.post(f"/coach/actions/{extra['id']}/undo"))
    assert debts(client)["extra_monthly_cents"] == 0


def test_conversion_is_not_undoable(client):
    card(client, name="Sabadell - Prestamo", owed=970983)
    _, reply = run_tool(client, "propose_debt_conversion", {
        "account": "sabadell", "installment": "290,17", "installments_left": 34, "next_month": "2026-11", "day": 2})
    conversion = action_of(reply)
    assert conversion["title"] == "Turn Sabadell - Prestamo into a loan"
    body = ok(commit(client, conversion))
    assert body["action"]["can_undo"] is False
    assert debts(client)["debts"][0]["kind"] == "loan"
    response = client.post(f"/coach/actions/{conversion['id']}/undo")
    assert response.status_code == 409


def test_undo_refused_after_an_editor_change(client):
    debt_id = visa_debt(client)
    _, reply = run_tool(client, "propose_debt_change", {"debt": "Visa", "plan_monthly": 250})
    change = action_of(reply)
    ok(commit(client, change))
    ok(client.patch(f"/debts/{debt_id}", json={"plan_monthly_cents": 30000}))
    response = client.post(f"/coach/actions/{change['id']}/undo")
    assert response.status_code == 409 and response.json()["detail"]["code"] == "undo_not_possible"


def test_a_preview_goes_stale_after_a_card_expense(client):
    visa_debt(client)
    _, reply = run_tool(client, "propose_debt_change", {"debt": "Visa", "plan_monthly": 250})
    change = action_of(reply)
    account = next(a["id"] for a in client.get("/accounts").json() if a["name"] == "Visa")
    ocio = next(c["id"] for g in client.get("/categories").json() for c in g["categories"] if c["name"] == "Ocio")
    ok(client.post("/transactions", json={"amount_cents": 5000, "category_id": ocio, "account_id": account,
                                          "date": "2026-10-10"}))
    response = commit(client, change)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "action_stale"


def test_a_new_loan_can_be_confirmed(client):
    _, reply = run_tool(client, "propose_debt", {"kind": "loan", "name": "Ikea", "installment": 45,
                                                 "installments_left": 10, "next_month": "2026-11"})
    ok(commit(client, action_of(reply)))
    assert debts(client)["debts"][0]["name"] == "Ikea"


def test_fake_model_card_and_what_if(client):
    from app.llm.fakes import fake_model

    card(client)

    def say(text):
        with override_route("coach", fake_model("e2e")):
            return ok(client.post("/coach/messages", json={"text": text,
                                                           "client_message_id": f"fake-debt-{next(_ids):04d}"}))["reply"]

    action = action_of(say("la Visa debe 634,62 y puedo pagar 200 al mes"))
    assert action["preview"]["debt"]["after"]["text"].startswith("200,00 € a month")
    ok(commit(client, action))
    assert action_of(say("¿y si pongo 100 más al mes?"))["kind"] == "debt_extra"


def test_get_debts_lists_cards_without_a_plan(client):
    card(client)
    seen = []

    def model(messages, info):
        _, returns = _current_run(messages)
        if not returns:
            return ModelResponse(parts=[ToolCallPart("get_debts", {})])
        seen.append(returns[0].content)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"text": "ok", "widgets": []})])

    with override_route("coach", FunctionModel(model)):
        ok(client.post("/coach/messages", json={"text": "hola", "client_message_id": "debt-cards-0001"}))
    assert seen[0]["cards_without_a_plan"] == [{"account": "Visa", "owed": "634,62 €"}]


def test_the_same_proposal_twice_in_one_reply_is_one_action(client, db, user):
    from sqlalchemy import func, select

    from app.models import CoachAction

    visa_debt(client)

    def model(messages, info):
        _, returns = _current_run(messages)
        if len(returns) < 2:
            return ModelResponse(parts=[ToolCallPart("propose_debt_extra", {"amount": 100})])
        refs = [{"type": "action_preview", "ref": r.content["ref"]} for r in returns]
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"text": "ok", "widgets": refs})])

    with override_route("coach", FunctionModel(model)):
        reply = ok(client.post("/coach/messages", json={"text": "hola", "client_message_id": "debt-dup-0001"}))["reply"]
    assert len([w for w in reply["widgets"] if w["type"] == "action_preview"]) == 1
    assert db.scalar(select(func.count()).select_from(CoachAction).where(CoachAction.user_id == user.id)) == 1
