"""Expected income from the conversation: set up, change, remove, link
(openspec change coach-income-setup). Scripted models only."""

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


def run_tools(client, turns: list) -> tuple[list, dict]:
    """Model turns of tool calls through the conversation (a turn is one call
    or a list run together), then a reply attaching every proposal: (all tool
    results, reply)."""
    batches = [t if isinstance(t, list) else [t] for t in turns]
    seen: list = []

    def model(messages, info: AgentInfo) -> ModelResponse:
        _, returns = _current_run(messages)
        done, sizes = len(returns), [0]
        for batch in batches:
            sizes.append(sizes[-1] + len(batch))
        if done in sizes[:-1]:
            batch = batches[sizes.index(done)]
            return ModelResponse(parts=[ToolCallPart(n, a) for n, a in batch])
        seen.extend(r.content for r in returns)
        refs = [r.content["ref"] for r in returns if isinstance(r.content, dict) and r.content.get("ref")]
        out = {"text": "Mira.", "widgets": [{"type": "action_preview", "ref": ref} for ref in refs
                                             if ref.startswith("action:")]}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, out)])

    with override_route("coach", FunctionModel(model)):
        response = client.post("/coach/messages", json={"text": "hola", "client_message_id": f"inc-{next(_ids):06d}"})
    assert response.status_code == 200, response.text
    return seen, response.json()["reply"]


def actions(reply: dict) -> list[dict]:
    return [w["data"]["action"] for w in reply["widgets"] if w["type"] == "action_preview"]


def ok(response) -> dict:
    assert response.status_code in (200, 201), response.text
    return response.json()


def commit(client, action: dict):
    return client.post(f"/coach/actions/{action['id']}/commit",
                       json={"revision": action["revision"], "idempotency_key": f"key-{next(_ids):08d}"})


SALARY = {"name": "Nómina", "amount": 2100, "pattern": "monthly", "day": 28, "payer": "Acme"}


def salary(client) -> dict:
    _, reply = run_tools(client, [("propose_income", SALARY)])
    [action] = actions(reply)
    return action


def test_a_salary_from_a_sentence(client):
    client.post("/accounts", json={"name": "Banco", "type": "bank", "opening_balance_cents": 100000})
    tba = ok(client.get(f"/budget/{MONTH}"))["to_be_assigned_cents"]
    action = salary(client)
    p = action["preview"]
    assert action["kind"] == "income"
    assert action["title"] == "Add income: Nómina, 2.100,00 € every month, day 28, from Acme"
    assert p["income"]["sentence_after"] == "2.100,00 € every month, day 28, from Acme"
    assert (p["plan"]["month_expected_before_cents"], p["plan"]["month_expected_after_cents"]) == (0, 210000)
    assert p["plan"]["year_expected_after_cents"] == 12 * 210000
    assert (p["plan"]["income_known_before"], p["plan"]["income_known_after"]) == (False, True)
    assert p["plan"]["gap_before_cents"] is None and p["plan"]["gap_after_cents"] is not None
    assert p["to_be_assigned_unchanged"] is True
    assert client.get("/income-schedules").json() == []

    ok(commit(client, action))
    [saved] = client.get("/income-schedules").json()
    assert (saved["amount_cents"], saved["day"], saved["payer"]) == (210000, 28, "Acme")
    assert ok(client.get(f"/budget/{MONTH}"))["to_be_assigned_cents"] == tba


def test_fourteen_pagas_are_two_proposals(client):
    _, reply = run_tools(client, [[
        ("propose_income", {"name": "Nómina", "amount": 1800, "pattern": "monthly"}),
        ("propose_income", {"name": "Pagas extra", "amount": 1800, "pattern": "some_months", "months": [6, 12]}),
    ]])
    titles = sorted(a["title"] for a in actions(reply))
    assert titles == ["Add income: Nómina, 1.800,00 € every month",
                      "Add income: Pagas extra, 1.800,00 € in Jun, Dec"]


def test_estimated_income(client):
    _, reply = run_tools(client, [("propose_income", {"name": "Clases", "amount": "400", "pattern": "monthly",
                                                      "estimated": True})])
    [action] = actions(reply)
    assert action["preview"]["income"]["estimated"] is True
    assert action["preview"]["income"]["sentence_after"] == "400,00 € every month (estimated)"


def test_no_date_is_not_an_income_pattern():
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    from app.services import coach_tools

    agent = Agent(TestModel(), tools=coach_tools.tools(), deps_type=coach_tools.CoachDeps)
    schema = agent._function_toolset.tools["propose_income"].function_schema.json_schema
    assert "no_date" not in schema["properties"]["pattern"]["enum"]


def test_change_and_undo(client):
    ok(commit(client, salary(client)))
    _, reply = run_tools(client, [("propose_income_change", {"income": "acme", "amount": 2200})])
    [change] = actions(reply)
    assert change["preview"]["income"]["sentence_before"] == "2.100,00 € every month, day 28, from Acme"
    assert change["preview"]["income"]["sentence_after"] == "2.200,00 € every month, day 28, from Acme"
    ok(commit(client, change))
    assert client.get("/income-schedules").json()[0]["amount_cents"] == 220000
    assert ok(client.post(f"/coach/actions/{change['id']}/undo"))["status"] == "undone"
    [back] = client.get("/income-schedules").json()
    assert (back["amount_cents"], back["payer"]) == (210000, "Acme")


def test_removal_and_undo(client):
    ok(commit(client, salary(client)))
    _, reply = run_tools(client, [("propose_income_removal", {"income": "Nómina"})])
    [removal] = actions(reply)
    assert removal["title"] == "Remove income: Nómina (2.100,00 € every month, day 28, from Acme)"
    ok(commit(client, removal))
    assert client.get("/income-schedules").json() == []
    ok(client.post(f"/coach/actions/{removal['id']}/undo"))
    [back] = client.get("/income-schedules").json()
    assert (back["amount_cents"], back["day"], back["payer"]) == (210000, 28, "Acme")


def test_undo_refused_after_an_editor_edit(client):
    action = salary(client)
    ok(commit(client, action))
    [saved] = client.get("/income-schedules").json()
    ok(client.patch(f"/income-schedules/{saved['id']}", json={"day": 27}))
    response = client.post(f"/coach/actions/{action['id']}/undo")
    assert response.status_code == 409 and response.json()["detail"]["code"] == "undo_not_possible"


def test_a_preview_goes_stale_after_an_editor_edit(client):
    ok(commit(client, salary(client)))
    _, reply = run_tools(client, [("propose_income_change", {"income": "Nómina", "amount": 2200})])
    [change] = actions(reply)
    [saved] = client.get("/income-schedules").json()
    ok(client.patch(f"/income-schedules/{saved['id']}", json={"day": 27}))
    response = commit(client, change)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "action_stale"


def test_link_a_late_salary_and_undo(client, db, user):
    ok(client.post("/income-schedules", json={"name": "Nómina", "amount_cents": 210000, "pattern": "monthly",
                                               "day": 1, "payer": "Acme"}))
    txn = client.post("/transactions", json={"amount_cents": 208000, "kind": "income", "date": "2026-10-02"}).json()
    seen, _ = run_tools(client, [("get_income", {})])
    ref = seen[0]["unplanned"][0]["ref"]
    assert ref == f"transaction:{txn['id']}"
    _, reply = run_tools(client, [("propose_income_link", {"transaction": ref, "income": "Nómina"})])
    [link] = actions(reply)
    assert link["title"] == "Link 2.080,00 € to Nómina"
    lp = link["preview"]["link"]
    assert (lp["occurrence_before"]["status"], lp["occurrence_after"]["status"]) == ("late", "received")
    assert (lp["unplanned_before"], lp["unplanned_after"]) == (True, False)
    ok(commit(client, link))
    assert client.get(f"/income/{MONTH}").json()["occurrences"][0]["status"] == "received"
    ok(client.post(f"/coach/actions/{link['id']}/undo"))
    view = client.get(f"/income/{MONTH}").json()
    assert view["occurrences"][0]["status"] == "late" and len(view["unplanned"]) == 1


def test_an_unknown_income_lists_candidates(client, db, user):
    ok(commit(client, salary(client)))
    seen, _ = run_tools(client, [("propose_income_change", {"income": "pensión", "amount": 10})])
    assert "error" in seen[0] and "Nómina" in seen[0]["error"]
    assert db.scalar(select(func.count()).select_from(CoachAction).where(
        CoachAction.user_id == user.id, CoachAction.kind == "income_update")) == 0


def test_fake_model_income_and_raise(client):
    from app.llm.fakes import fake_model

    def say(text):
        with override_route("coach", fake_model("e2e")):
            return ok(client.post("/coach/messages", json={"text": text,
                                                           "client_message_id": f"fake-inc-{next(_ids):04d}"}))["reply"]

    [action] = actions(say("cobro 2100 el día 28"))
    assert action["preview"]["income"]["sentence_after"] == "2.100,00 € every month, day 28"
    ok(commit(client, action))
    [change] = actions(say("mi sueldo sube a 2200"))
    assert change["kind"] == "income_update"
