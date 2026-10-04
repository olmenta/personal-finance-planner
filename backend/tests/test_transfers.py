"""Transfers (spec: transfers): twin rows outside the budget plane."""

from sqlalchemy import select

from app.models import Transaction


def setup_accounts(client) -> tuple[str, str]:
    a = client.post("/accounts", json={"name": "Banco A", "type": "bank"}).json()["id"]
    b = client.post("/accounts", json={"name": "Banco B", "type": "bank"}).json()["id"]
    return a, b


def transfer(client, a: str, b: str, cents: int = 20000, day: str = "2026-06-10", **extra):
    return client.post(
        "/transfers",
        json={"from_account_id": a, "to_account_id": b, "amount_cents": cents, "date": day, **extra},
    )


def balances(client) -> dict[str, int]:
    return {a["id"]: a["balance_cents"] for a in client.get("/accounts").json()}


def test_twin_invariants(client, db, user):
    a, b = setup_accounts(client)
    response = transfer(client, a, b, note="Ahorro")
    assert response.status_code == 201
    body = response.json()
    rows = list(
        db.scalars(select(Transaction).where(Transaction.transfer_pair_id == body["pair_id"]))
    )
    assert sorted(r.amount_cents for r in rows) == [-20000, 20000]
    assert {r.account_id for r in rows} == {a, b}
    assert all(r.category_id is None and r.payee_id is None for r in rows)
    assert all(r.status == "confirmed" for r in rows)
    assert len({r.date for r in rows}) == 1
    assert balances(client)[a] == -20000 and balances(client)[b] == 20000


def test_same_account_422(client):
    a, _ = setup_accounts(client)
    response = transfer(client, a, a)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "same_account"


def test_foreign_account_404(client):
    a, _ = setup_accounts(client)
    assert transfer(client, a, "nope").status_code == 404


def test_budget_and_summary_unchanged_by_transfers(client, category_ids):
    a, b = setup_accounts(client)
    client.post("/transactions", json={"amount_cents": 235000, "kind": "income", "date": "2026-06-02", "account_id": a})
    client.post(
        "/transactions",
        json={"amount_cents": 5000, "category_id": category_ids["Ocio"], "date": "2026-06-05"},
    )
    budget_before = client.get("/budget/2026-06").json()
    summary_before = client.get("/summary/2026-06").json()

    transfer(client, a, b)
    assert client.get("/budget/2026-06").json() == budget_before
    assert client.get("/summary/2026-06").json() == summary_before


def test_mirrored_edit(client, db):
    a, b = setup_accounts(client)
    pair_id = transfer(client, a, b).json()["pair_id"]
    edited = client.patch(
        f"/transfers/{pair_id}", json={"amount_cents": 25000, "date": "2026-06-12", "note": "x"}
    ).json()
    assert edited["amount_cents"] == 25000
    rows = list(db.scalars(select(Transaction).where(Transaction.transfer_pair_id == pair_id)))
    assert sorted(r.amount_cents for r in rows) == [-25000, 25000]
    assert {str(r.date) for r in rows} == {"2026-06-12"}
    assert {r.description for r in rows} == {"x"}


def test_delete_removes_both(client, db):
    a, b = setup_accounts(client)
    pair_id = transfer(client, a, b).json()["pair_id"]
    assert client.delete(f"/transfers/{pair_id}").status_code == 204
    assert db.scalar(select(Transaction).where(Transaction.transfer_pair_id == pair_id)) is None
    assert client.get(f"/transfers/{pair_id}").status_code == 404


def test_transaction_patch_and_delete_rejected_for_transfer_rows(client):
    a, b = setup_accounts(client)
    body = transfer(client, a, b).json()
    for txn_id in (body["out_transaction_id"], body["in_transaction_id"]):
        response = client.patch(f"/transactions/{txn_id}", json={"note": "x"})
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "is_transfer"
        assert client.delete(f"/transactions/{txn_id}").status_code == 409


def test_unlink_reenters_budget_plane(client):
    a, b = setup_accounts(client)
    income_before = client.get("/budget/2026-06").json()["income_cents"]
    pair_id = transfer(client, a, b).json()["pair_id"]
    assert client.post(f"/transfers/{pair_id}/unlink").status_code == 204
    assert client.get("/budget/2026-06").json()["income_cents"] == income_before + 20000
    rows = client.get("/transactions", params={"month": "2026-06"}).json()
    assert all(r["transfer_pair_id"] is None for r in rows)


def test_list_carries_counterpart_account(client):
    a, b = setup_accounts(client)
    transfer(client, a, b)
    rows = {r["account_id"]: r for r in client.get("/transactions", params={"month": "2026-06"}).json()}
    assert rows[a]["transfer_account_id"] == b
    assert rows[b]["transfer_account_id"] == a
