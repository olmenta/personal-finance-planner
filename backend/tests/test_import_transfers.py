"""Import-side transfers (spec: statement-import deltas): chosen account,
transfer marking at review, twin matching on the counterpart import."""

from fixtures import bbva_xlsx, sabadell_xls
from sqlalchemy import select

from app.models import Transaction

# BBVA outflow that is really a transfer to Banco B.
BBVA_TRANSFER = [
    ("10/06/2026", "10/06/2026", "Traspaso a cuenta B", "Transferencia", -200.00, 400.00, "TRASPASO"),
    ("09/06/2026", "09/06/2026", "Cafetería central", "Pago con tarjeta", -1.50, 600.00, "CAFE"),
]
# Banco B's own statement: the counterpart inflow two days later.
SABADELL_COUNTERPART = [
    ("12/06/2026", "TRANSFERENCIA RECIBIDA", "12/06/2026", 200.00, 700.00, "", ""),
    ("11/06/2026", "RECIBO LUZ COMPAÑÍA", "11/06/2026", -58.37, 500.00, "", ""),
]


def upload(client, blob: bytes, bank: str, account_id: str | None = None):
    data = {"bank": bank}
    if account_id:
        data["account_id"] = account_id
    return client.post(
        "/imports", files={"file": ("export.xlsx", blob, "application/octet-stream")}, data=data
    )


def make_banks(client) -> tuple[str, str]:
    a = client.post("/accounts", json={"name": "BBVA", "type": "bank"}).json()["id"]
    b = client.post("/accounts", json={"name": "Banco B", "type": "bank"}).json()["id"]
    return a, b


def row(body: dict, description: str) -> dict:
    # BBVA descriptions carry the movement type ("<concepto> — <movimiento>").
    return next(t for t in body["transactions"] if t["description"].startswith(description))


def test_upload_into_chosen_account(client):
    a, _ = make_banks(client)
    body = upload(client, bbva_xlsx(), "bbva", a).json()
    assert body["account_id"] == a
    assert all(t["account_id"] == a for t in body["transactions"])


def test_upload_defaults_to_main_and_rejects_foreign(client):
    body = upload(client, bbva_xlsx(), "bbva").json()
    main = next(x for x in client.get("/accounts").json() if x["is_main"])
    assert body["account_id"] == main["id"]
    client.delete(f"/imports/{body['id']}")
    response = upload(client, bbva_xlsx(), "bbva", "nope")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "account_not_found"


def test_marked_transfer_creates_twin_on_confirm(client, db):
    a, b = make_banks(client)
    budget_before = client.get("/budget/2026-06").json()
    body = upload(client, bbva_xlsx(BBVA_TRANSFER), "bbva", a).json()
    staged = row(body, "Traspaso a cuenta B")
    cafe = row(body, "Cafetería central")
    confirmed = client.post(
        f"/imports/{body['id']}/confirm",
        json={"transfer_overrides": {staged["id"]: b}},
    )
    assert confirmed.status_code == 200

    near = db.get(Transaction, staged["id"])
    assert near.status == "confirmed" and near.transfer_pair_id is not None
    twin = db.scalar(
        select(Transaction).where(
            Transaction.transfer_pair_id == near.transfer_pair_id, Transaction.id != near.id
        )
    )
    assert twin.account_id == b and twin.amount_cents == 20000 and twin.status == "confirmed"
    assert twin.category_id is None and near.category_id is None and near.payee_id is None

    budget_after = client.get("/budget/2026-06").json()
    assert budget_after["income_cents"] == budget_before["income_cents"]
    # Only the coffee is spending; the transfer is not.
    summary = client.get("/summary/2026-06").json()
    assert summary["expense_cents"] == -cafe["amount_cents"]


def test_counterpart_import_suggests_match_and_accept_adopts(client, db):
    a, b = make_banks(client)
    first = upload(client, bbva_xlsx(BBVA_TRANSFER), "bbva", a).json()
    client.post(
        f"/imports/{first['id']}/confirm",
        json={"transfer_overrides": {row(first, "Traspaso a cuenta B")["id"]: b}},
    )

    second = upload(client, sabadell_xls(SABADELL_COUNTERPART), "sabadell", b).json()
    inflow = row(second, "TRANSFERENCIA RECIBIDA")
    assert inflow["match"] is not None
    assert inflow["match"]["other_account_id"] == a
    assert row(second, "RECIBO LUZ COMPAÑÍA")["match"] is None
    # A suggestion links nothing by itself.
    assert db.get(Transaction, inflow["id"]).transfer_pair_id is None

    client.post(f"/imports/{second['id']}/confirm", json={"accept_matches": [inflow["id"]]})
    in_b = list(
        db.scalars(
            select(Transaction).where(Transaction.account_id == b, Transaction.amount_cents == 20000)
        )
    )
    assert len(in_b) == 1 and in_b[0].transfer_pair_id is not None
    assert db.get(Transaction, inflow["id"]) is None

    # Re-importing B's statement collides with the adopted twin.
    again = upload(client, sabadell_xls(SABADELL_COUNTERPART), "sabadell", b).json()
    assert again["row_count"] == 0


def test_ignored_match_confirms_normal_row(client, db):
    a, b = make_banks(client)
    client.post(
        "/transfers",
        json={"from_account_id": a, "to_account_id": b, "amount_cents": 20000, "date": "2026-06-10"},
    )
    body = upload(client, sabadell_xls(SABADELL_COUNTERPART), "sabadell", b).json()
    inflow = row(body, "TRANSFERENCIA RECIBIDA")
    assert inflow["match"] is not None
    client.post(f"/imports/{body['id']}/confirm", json={})
    confirmed = db.get(Transaction, inflow["id"])
    assert confirmed.status == "confirmed" and confirmed.transfer_pair_id is None
    in_b = db.scalars(
        select(Transaction).where(Transaction.account_id == b, Transaction.amount_cents == 20000)
    ).all()
    assert len(in_b) == 2  # existing twin untouched, staged row kept


def test_no_match_outside_window(client):
    a, b = make_banks(client)
    client.post(
        "/transfers",
        json={"from_account_id": a, "to_account_id": b, "amount_cents": 20000, "date": "2026-06-01"},
    )
    body = upload(client, sabadell_xls(SABADELL_COUNTERPART), "sabadell", b).json()
    assert row(body, "TRANSFERENCIA RECIBIDA")["match"] is None


def test_marked_transfer_twin_carries_note(client, db):
    a, b = make_banks(client)
    body = upload(client, bbva_xlsx(BBVA_TRANSFER), "bbva", a).json()
    staged = row(body, "Traspaso a cuenta B")
    client.post(
        f"/imports/{body['id']}/confirm",
        json={
            "transfer_overrides": {staged["id"]: b},
            "note_overrides": {staged["id"]: "Ahorro de junio"},
        },
    )
    near = db.get(Transaction, staged["id"])
    twin = db.scalar(
        select(Transaction).where(
            Transaction.transfer_pair_id == near.transfer_pair_id, Transaction.id != near.id
        )
    )
    assert near.description == twin.description == "Ahorro de junio"
