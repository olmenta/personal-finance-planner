"""Payments from the conversation: set up, change, remove, with previews and
undo (openspec change coach-payments-setup). Scripted models only."""

import itertools
from datetime import date

import pytest
from pydantic_ai import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import func, select

from app import clock
from app.llm import override_route
from app.llm.fakes import _current_run
from app.models import CoachAction

MONTH = "2026-10"
_ids = itertools.count()


@pytest.fixture(autouse=True)
def mid_october(monkeypatch):
    today = date(2026, 10, 14)
    monkeypatch.setattr(clock, "today_madrid", lambda: today)
    monkeypatch.setattr("app.services.overview.today_madrid", lambda: today)
    monkeypatch.setattr("app.services.entries.today_madrid", lambda: today)


def run_tool(client, name: str, args: dict) -> tuple[dict, dict]:
    """One tool call through the conversation: (tool result, reply)."""
    seen = []

    def model(messages, info: AgentInfo) -> ModelResponse:
        _, returns = _current_run(messages)
        if not returns:
            return ModelResponse(parts=[ToolCallPart(name, args)])
        seen.append(returns[0].content)
        ref = returns[0].content.get("ref")
        kind = "category_choice" if ref and ref.startswith("choice:") else "action_preview"
        out = {"text": "Mira.", "widgets": [{"type": kind, "ref": ref}] if ref else []}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, out)])

    with override_route("coach", FunctionModel(model)):
        response = client.post("/coach/messages", json={"text": "hola", "client_message_id": f"pay-{next(_ids):06d}"})
    assert response.status_code == 200, response.text
    return seen[0], response.json()["reply"]


def action_of(reply: dict, kind: str = "action_preview") -> dict:
    [w] = [w for w in reply["widgets"] if w["type"] == kind]
    return w["data"]["action"]


def ok(response) -> dict:
    assert response.status_code in (200, 201), response.text
    return response.json()


def commit(client, action: dict, **extra):
    return client.post(f"/coach/actions/{action['id']}/commit",
                       json={"revision": action["revision"], "idempotency_key": f"key-{next(_ids):08d}", **extra})


def cid(client, name: str) -> str:
    return next(c["id"] for g in client.get("/categories").json() for c in g["categories"] if c["name"] == name)


def row(client, name: str) -> dict:
    view = ok(client.get(f"/budget/{MONTH}"))
    return next(c for g in view["groups"] for c in g["categories"] if c["name"] == name)


RENT = {"category": "Alquiler", "name": "Alquiler", "amount": 850, "pattern": "monthly", "day": 1}


def rent(client) -> dict:
    ok(client.get(f"/budget/{MONTH}"))
    _, reply = run_tool(client, "propose_payment", RENT)
    return action_of(reply)


def test_rent_from_a_sentence_is_a_preview_until_confirmed(client):
    tba = ok(client.get(f"/budget/{MONTH}"))["to_be_assigned_cents"]
    action = rent(client)
    p = action["preview"]
    assert action["kind"] == "payment"
    assert action["title"] == "Add payment: Alquiler, 850,00 € every month, day 1"
    assert p["payment"]["sentence_after"] == "850,00 € every month, day 1"
    assert p["payment"]["next_due_month"] == MONTH
    assert (p["amounts"]["normal_before_cents"], p["amounts"]["normal_after_cents"]) == (0, 85000)
    assert p["categories"][0]["assigned_after_cents"] == 85000
    assert p["to_be_assigned_after_cents"] == tba - 85000
    assert client.get(f"/categories/{cid(client, 'Alquiler')}/schedules").json() == []

    ok(commit(client, action))
    assert row(client, "Alquiler")["assigned_cents"] == 85000
    assert len(client.get(f"/categories/{cid(client, 'Alquiler')}/schedules").json()) == 1


def test_annual_payment_with_money_carried_in(client):
    subs = cid(client, "Suscripciones")
    client.get("/budget/2026-09")
    client.put(f"/budget/2026-09/assignments/{subs}", json={"amount_cents": 20000})
    _, reply = run_tool(client, "propose_payment", {
        "category": "Suscripciones", "name": "Seguro del coche", "amount": 600, "pattern": "annual", "month": 2})
    p = action_of(reply)["preview"]
    assert p["payment"]["sentence_after"] == "600,00 € once a year, in February"
    assert (p["amounts"]["normal_after_cents"], p["amounts"]["catch_up_after_cents"]) == (5000, 8000)
    assert p["payment"]["next_due_month"] == "2027-02"


def test_every_n_estimated(client):
    _, reply = run_tool(client, "propose_payment", {
        "category": "Suministros", "name": "Agua", "amount": "120", "pattern": "every_n", "every_n": 3,
        "start_month": "2026-11", "estimated": True})
    p = action_of(reply)["preview"]["payment"]
    assert p["estimated"] is True
    assert p["sentence_after"] == "120,00 € every 3 months from November 2026 (estimated)"


def test_once_beyond_the_horizon_is_refused(client, db, user):
    result, _ = run_tool(client, "propose_payment", {
        "category": "Ocio", "name": "Viaje", "amount": 2000, "pattern": "once", "once_month": "2037-10"})
    assert result["error"] == "outside_planning_horizon"
    assert db.scalar(select(func.count()).select_from(CoachAction).where(CoachAction.user_id == user.id)) == 0


def test_invalid_fields_are_refused(client):
    result, _ = run_tool(client, "propose_payment", {
        "category": "Ocio", "name": "Colegio", "amount": 100, "pattern": "some_months"})
    assert result["error"] == "invalid_schedule"


def test_a_debt_payment_is_refused(client, db, user):
    ok(client.post("/debts", json={"kind": "loan", "name": "Ikea", "installment_cents": 4500,
                                   "installments_left": 10, "next_month": MONTH}))
    result, _ = run_tool(client, "propose_payment_change", {"payment": "Ikea", "amount": 50})
    assert result["error"] == "managed_by_debt" and "What you owe" in result["message"]
    assert db.scalar(select(func.count()).select_from(CoachAction).where(CoachAction.user_id == user.id)) == 0


def test_a_card_plan_category_keeps_one_schedule(client):
    client.post("/accounts", json={"name": "Visa", "type": "credit", "opening_balance_cents": 0})
    card_category = next(c for g in client.get("/categories").json() for c in g["categories"]
                         if c["name"].endswith("Visa"))
    ok(client.post(f"/categories/{card_category['id']}/schedules",
                   json={"name": "Plan", "amount_cents": 10000, "pattern": "monthly"}))
    result, _ = run_tool(client, "propose_payment", {
        "category": card_category["name"], "name": "Otro", "amount": 50, "pattern": "monthly"})
    assert result["error"] == "card_plan_exists"


def test_change_and_undo(client):
    ok(commit(client, rent(client)))
    _, reply = run_tool(client, "propose_payment_change", {"payment": "alquiler", "amount": 900})
    change = action_of(reply)
    assert change["title"] == "Change payment: Alquiler, 900,00 € every month, day 1"
    assert change["preview"]["payment"]["sentence_before"] == "850,00 € every month, day 1"
    ok(commit(client, change))
    assert row(client, "Alquiler")["assigned_cents"] == 90000
    assert ok(client.post(f"/coach/actions/{change['id']}/undo"))["status"] == "undone"
    assert row(client, "Alquiler")["assigned_cents"] == 85000


def test_removal_and_undo(client):
    ok(commit(client, rent(client)))
    _, reply = run_tool(client, "propose_payment_removal", {"payment": "Alquiler"})
    removal = action_of(reply)
    assert removal["title"] == "Remove payment: Alquiler (850,00 € every month, day 1)"
    assert removal["preview"]["payment"]["sentence_after"] is None
    ok(commit(client, removal))
    assert client.get(f"/categories/{cid(client, 'Alquiler')}/schedules").json() == []
    ok(client.post(f"/coach/actions/{removal['id']}/undo"))
    [back] = client.get(f"/categories/{cid(client, 'Alquiler')}/schedules").json()
    assert (back["amount_cents"], back["day"]) == (85000, 1)


def test_undo_refused_after_an_editor_change(client):
    action = rent(client)
    ok(commit(client, action))
    [schedule] = client.get(f"/categories/{cid(client, 'Alquiler')}/schedules").json()
    ok(client.patch(f"/schedules/{schedule['id']}", json={"amount_cents": 87000}))
    response = client.post(f"/coach/actions/{action['id']}/undo")
    assert response.status_code == 409 and response.json()["detail"]["code"] == "undo_not_possible"


def test_a_preview_goes_stale_after_an_editor_change(client):
    ok(commit(client, rent(client)))
    _, reply = run_tool(client, "propose_payment_change", {"payment": "Alquiler", "amount": 900})
    change = action_of(reply)
    [schedule] = client.get(f"/categories/{cid(client, 'Alquiler')}/schedules").json()
    ok(client.patch(f"/schedules/{schedule['id']}", json={"day": 5}))
    response = commit(client, change)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "action_stale"


def test_payment_for_a_new_category_goes_through_the_choice(client, db):
    result, reply = run_tool(client, "propose_category", {
        "name": "Gimnasio", "for_payment": {"name": "Gimnasio", "amount": 35, "pattern": "monthly"}})
    choice = action_of(reply, "category_choice")
    assert choice["preview"]["follow_up_title"] == "Add payment: Gimnasio, 35,00 € every month"
    body = ok(commit(client, choice, group_id=choice["preview"]["suggested_group_id"]))
    follow = body["follow_up"]
    assert follow["kind"] == "payment" and follow["preview"]["payment"]["sentence_after"] == "35,00 € every month"
    ok(commit(client, follow))
    assert row(client, "Gimnasio")["assigned_cents"] == 3500


def test_fake_model_payment_and_change(client):
    from app.llm.fakes import fake_model

    ok(client.get(f"/budget/{MONTH}"))
    with override_route("coach", fake_model("e2e")):
        reply = ok(client.post("/coach/messages", json={
            "text": "el alquiler son 850 al mes, el día 1", "client_message_id": "fake-pay-0001"}))["reply"]
    action = action_of(reply)
    assert action["preview"]["payment"]["sentence_after"] == "850,00 € every month, day 1"
    ok(commit(client, action))
    with override_route("coach", fake_model("e2e")):
        reply = ok(client.post("/coach/messages", json={
            "text": "el alquiler sube a 900", "client_message_id": "fake-pay-0002"}))["reply"]
    assert action_of(reply)["kind"] == "payment_update"
