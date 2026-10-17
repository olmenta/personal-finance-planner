"""Linking an inflow to its expected income in one step (openspec change
coach-income-setup, income-schedules "One shared income operation")."""

from datetime import date

import pytest

from app import clock

MONTH = "2026-10"


@pytest.fixture(autouse=True)
def mid_october(monkeypatch):
    today = date(2026, 10, 14)
    monkeypatch.setattr(clock, "today_madrid", lambda: today)
    monkeypatch.setattr("app.services.overview.today_madrid", lambda: today)


def schedule(client, **extra) -> dict:
    body = {"name": "Nómina", "amount_cents": 210000, "pattern": "monthly", "day": 1, **extra}
    response = client.post("/income-schedules", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def inflow(client, cents: int = 208000, payee: str | None = None) -> dict:
    body = {"amount_cents": cents, "kind": "income", "date": "2026-10-02"}
    if payee:
        body["payee"] = payee
    return client.post("/transactions", json=body).json()


def link(client, txn: dict, sched: dict):
    return client.post("/income/link", json={"transaction_id": txn["id"], "schedule_id": sched["id"]})


def test_the_schedules_payer_goes_to_the_inflow(client):
    sched = schedule(client, payer="Acme")
    txn = inflow(client)
    before = client.get(f"/income/{MONTH}").json()
    assert [u["transaction_id"] for u in before["unplanned"]] == [txn["id"]]
    view = link(client, txn, sched).json()
    [occ] = view["occurrences"]
    assert occ["status"] == "received" and occ["received_cents"] == 208000
    assert view["unplanned"] == []
    assert next(t for t in client.get("/transactions").json() if t["id"] == txn["id"])["payee_name"] == "Acme"


def test_the_inflows_payer_goes_to_the_schedule(client):
    sched = schedule(client, amount_cents=50000)  # amounts far apart: no amount match
    txn = inflow(client, 208000, payee="Acme")
    link(client, txn, sched)
    assert client.get("/income-schedules").json()[0]["payer"] == "Acme"


def test_neither_has_a_payer(client):
    sched = schedule(client, name="Clases", amount_cents=40000)
    txn = inflow(client, 90000)
    view = link(client, txn, sched).json()
    assert view["occurrences"][0]["status"] == "received"
    assert client.get("/income-schedules").json()[0]["payer"] == "Clases"


def test_unknown_ids_are_404(client):
    sched = schedule(client)
    expense = client.post("/transactions", json={"amount_cents": 1000, "category_id": None, "kind": "income",
                                                 "date": "2026-10-02"}).json()
    response = client.post("/income/link", json={"transaction_id": "nope", "schedule_id": sched["id"]})
    assert response.status_code == 404 and response.json()["detail"]["code"] == "transaction_not_found"
    response = client.post("/income/link", json={"transaction_id": expense["id"], "schedule_id": "nope"})
    assert response.status_code == 404 and response.json()["detail"]["code"] == "income_schedule_not_found"
