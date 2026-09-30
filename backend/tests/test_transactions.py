from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.exc import IntegrityError

from fixtures import bbva_xlsx
from app.models import Account, Payee, Transaction, User


def test_minimal_entry_defaults(client, category_ids):
    response = client.post(
        "/transactions",
        json={"amount_cents": 1249, "category_id": category_ids["Restaurantes"]},
    )
    assert response.status_code == 201
    body = response.json()
    today_madrid = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
    assert body["date"] == today_madrid
    assert body["amount_cents"] == -1249  # expense stored signed
    assert body["source"] == "manual"
    assert body["status"] == "confirmed"
    assert body["currency"] == "EUR"


def test_income_kind_stored_positive(client, category_ids):
    response = client.post(
        "/transactions",
        json={"amount_cents": 235000, "category_id": category_ids["Ahorro"], "kind": "income"},
    )
    assert response.status_code == 201
    assert response.json()["amount_cents"] == 235000


def test_income_without_category_allowed(client):
    response = client.post(
        "/transactions", json={"amount_cents": 240000, "kind": "income"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["amount_cents"] == 240000
    assert body["category_id"] is None


def test_expense_without_category_rejected(client):
    response = client.post("/transactions", json={"amount_cents": 1200})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "category_required"


@pytest.mark.parametrize("amount", [0, -5])
def test_invalid_amount_rejected(client, category_ids, amount):
    response = client.post(
        "/transactions",
        json={"amount_cents": amount, "category_id": category_ids["Restaurantes"]},
    )
    assert response.status_code == 422


def test_unknown_category_404(client):
    response = client.post(
        "/transactions", json={"amount_cents": 100, "category_id": "nope"}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "category_not_found"


def test_month_filter_newest_first(client, category_ids):
    cat = category_ids["Supermercado"]
    client.post("/transactions", json={"amount_cents": 100, "category_id": cat, "date": "2026-05-31"})
    client.post("/transactions", json={"amount_cents": 200, "category_id": cat, "date": "2026-06-01"})
    client.post("/transactions", json={"amount_cents": 300, "category_id": cat, "date": "2026-06-15"})

    body = client.get("/transactions", params={"month": "2026-06"}).json()
    assert [t["amount_cents"] for t in body] == [-300, -200]


def test_manual_same_day_duplicates_allowed(client, category_ids):
    payload = {"amount_cents": 250, "category_id": category_ids["Restaurantes"]}
    assert client.post("/transactions", json=payload).status_code == 201
    assert client.post("/transactions", json=payload).status_code == 201  # salt allows it


def test_dedupe_constraint_rejects_identical_hash(db, user, client, category_ids):
    first = db.query(Transaction).first()
    assert first is None
    client.post(
        "/transactions",
        json={"amount_cents": 100, "category_id": category_ids["Gasolina"], "date": "2026-06-02"},
    )
    existing = db.query(Transaction).first()
    clone = Transaction(
        user_id=existing.user_id,
        account_id=existing.account_id,
        category_id=existing.category_id,
        date=existing.date,
        amount_cents=existing.amount_cents,
        dedupe_hash=existing.dedupe_hash,  # same hash, same account → must fail
    )
    db.add(clone)
    with pytest.raises(IntegrityError):
        db.flush()


# ---- PATCH /transactions/{id} ------------------------------------------------


def create_expense(client, category_id, amount=1249, **extra):
    payload = {"amount_cents": amount, "category_id": category_id, **extra}
    response = client.post("/transactions", json=payload)
    assert response.status_code == 201
    return response.json()


def budget_spent(client, month, category_name):
    view = client.get(f"/budget/{month}").json()
    for group in view["groups"]:
        for cat in group["categories"]:
            if cat["name"] == category_name:
                return cat["spent_cents"]
    raise AssertionError(f"category {category_name} not in budget view")


def test_patch_partial_amount_and_category(client, category_ids):
    txn = create_expense(client, category_ids["Restaurantes"], date="2026-06-05")
    response = client.patch(
        f"/transactions/{txn['id']}",
        json={"amount_cents": 1499, "category_id": category_ids["Supermercado"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["amount_cents"] == -1499  # sign kept without kind
    assert body["category_id"] == category_ids["Supermercado"]
    assert body["date"] == "2026-06-05"  # omitted fields unchanged


def test_patch_direction_flip(client, category_ids):
    txn = create_expense(client, category_ids["Ahorro"])
    body = client.patch(
        f"/transactions/{txn['id']}", json={"amount_cents": 5000, "kind": "income"}
    ).json()
    assert body["amount_cents"] == 5000


def test_patch_kind_alone_resigns_current_magnitude(client, category_ids):
    txn = create_expense(client, category_ids["Ahorro"], amount=700)
    body = client.patch(f"/transactions/{txn['id']}", json={"kind": "income"}).json()
    assert body["amount_cents"] == 700


def test_patch_category_null_clears_it(client, category_ids):
    """Un-marking a refund: explicit null clears, absent leaves untouched."""
    txn = client.post(
        "/transactions",
        json={
            "amount_cents": 1250,
            "category_id": category_ids["Supermercado"],
            "kind": "income",
        },
    ).json()
    untouched = client.patch(f"/transactions/{txn['id']}", json={"note": "x"}).json()
    assert untouched["category_id"] == category_ids["Supermercado"]
    cleared = client.patch(
        f"/transactions/{txn['id']}", json={"category_id": None}
    ).json()
    assert cleared["category_id"] is None


def test_patch_note_null_clears_description(client, category_ids):
    txn = create_expense(client, category_ids["Restaurantes"], note="typo here")
    body = client.patch(f"/transactions/{txn['id']}", json={"note": None}).json()
    assert body["description"] is None


def test_patch_payee_set_and_cleared(client, db, user, category_ids):
    txn = create_expense(client, category_ids["Supermercado"])
    body = client.patch(f"/transactions/{txn['id']}", json={"payee": "Mercadona"}).json()
    assert body["payee_name"] == "Mercadona"
    # Empty string clears the payee; the payee entity itself survives.
    body = client.patch(f"/transactions/{txn['id']}", json={"payee": ""}).json()
    assert body["payee_id"] is None
    assert db.query(Payee).filter_by(user_id=user.id).count() == 1


def test_patch_unknown_id_404(client):
    response = client.patch("/transactions/nope", json={"amount_cents": 100})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "transaction_not_found"


def test_patch_foreign_row_404(client, db, category_ids):
    other = User(email="other@example.com")
    db.add(other)
    db.flush()
    account = Account(user_id=other.id, name="Otra cuenta")
    db.add(account)
    db.flush()
    foreign = Transaction(
        user_id=other.id,
        account_id=account.id,
        date=datetime(2026, 6, 1).date(),
        amount_cents=-500,
        dedupe_hash="foreign-hash",
    )
    db.add(foreign)
    db.flush()
    response = client.patch(f"/transactions/{foreign.id}", json={"amount_cents": 1})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "transaction_not_found"


def test_patch_staged_row_404(client):
    upload = client.post(
        "/imports",
        files={"file": ("export.xlsx", bbva_xlsx(), "application/octet-stream")},
        data={"bank": "bbva"},
    ).json()
    staged_id = upload["transactions"][0]["id"]
    response = client.patch(f"/transactions/{staged_id}", json={"amount_cents": 1})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "transaction_not_found"


def test_patch_unknown_category_404_row_unchanged(client, category_ids):
    txn = create_expense(client, category_ids["Restaurantes"])
    response = client.patch(
        f"/transactions/{txn['id']}",
        json={"amount_cents": 9999, "category_id": "nope"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "category_not_found"
    rows = client.get("/transactions").json()
    assert rows[0]["amount_cents"] == -1249  # nothing applied


def test_patch_and_delete_reflected_in_budget_spent(client, category_ids):
    txn = create_expense(
        client, category_ids["Supermercado"], amount=1000, date="2026-06-05"
    )
    assert budget_spent(client, "2026-06", "Supermercado") == 1000
    client.patch(f"/transactions/{txn['id']}", json={"amount_cents": 2500})
    assert budget_spent(client, "2026-06", "Supermercado") == 2500
    assert client.delete(f"/transactions/{txn['id']}").status_code == 204
    assert budget_spent(client, "2026-06", "Supermercado") == 0


# ---- DELETE /transactions/{id} -----------------------------------------------


def test_delete_removes_row(client, category_ids):
    txn = create_expense(client, category_ids["Restaurantes"], date="2026-06-05")
    assert client.delete(f"/transactions/{txn['id']}").status_code == 204
    assert client.get("/transactions", params={"month": "2026-06"}).json() == []
    # Idempotence from the client's view: second delete is a 404.
    assert client.delete(f"/transactions/{txn['id']}").status_code == 404


def test_delete_staged_row_404(client):
    upload = client.post(
        "/imports",
        files={"file": ("export.xlsx", bbva_xlsx(), "application/octet-stream")},
        data={"bank": "bbva"},
    ).json()
    staged_id = upload["transactions"][0]["id"]
    assert client.delete(f"/transactions/{staged_id}").status_code == 404


# ---- Re-import interplay (design D2) ------------------------------------------


def confirm_bbva_import(client):
    upload = client.post(
        "/imports",
        files={"file": ("export.xlsx", bbva_xlsx(), "application/octet-stream")},
        data={"bank": "bbva"},
    ).json()
    confirmed = client.post(f"/imports/{upload['id']}/confirm", json={"overrides": {}})
    assert confirmed.status_code == 200
    return upload


def test_edited_imported_row_skipped_on_reimport(client, category_ids):
    confirm_bbva_import(client)
    rows = client.get("/transactions").json()
    target = next(r for r in rows if r["source"] == "import_bbva")
    client.patch(
        f"/transactions/{target['id']}",
        json={"category_id": category_ids["Ocio"], "note": "edited note"},
    )

    again = client.post(
        "/imports",
        files={"file": ("export.xlsx", bbva_xlsx(), "application/octet-stream")},
        data={"bank": "bbva"},
    ).json()
    assert again["row_count"] == 0
    assert again["skipped_duplicates"] == 6  # edit kept the dedupe identity

    # The edit survived the re-import attempt.
    refreshed = next(
        r for r in client.get("/transactions").json() if r["id"] == target["id"]
    )
    assert refreshed["description"] == "edited note"


def test_deleted_imported_row_staged_again_on_reimport(client):
    confirm_bbva_import(client)
    rows = [r for r in client.get("/transactions").json() if r["source"] == "import_bbva"]
    deleted = rows[0]
    assert client.delete(f"/transactions/{deleted['id']}").status_code == 204

    again = client.post(
        "/imports",
        files={"file": ("export.xlsx", bbva_xlsx(), "application/octet-stream")},
        data={"bank": "bbva"},
    ).json()
    assert again["row_count"] == 1  # the deleted row comes back for review
    assert again["skipped_duplicates"] == 5
