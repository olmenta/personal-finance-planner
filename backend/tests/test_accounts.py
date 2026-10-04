"""Accounts API (spec: accounts-api): CRUD, derived balances, opening
balance semantics, main-account default."""

from app.clock import current_month


def create(client, **body):
    return client.post("/accounts", json={"type": "bank", **body})


def accounts(client) -> dict[str, dict]:
    return {a["name"]: a for a in client.get("/accounts").json()}


def budget(client) -> dict:
    return client.get(f"/budget/{current_month()}").json()


def test_seeded_account_is_main(client):
    listed = client.get("/accounts").json()
    assert [a["name"] for a in listed] == ["Efectivo"]
    assert listed[0]["is_main"] is True
    assert listed[0]["balance_cents"] == 0


def test_create_bank_account(client):
    response = create(client, name="Banco B", institution="Sabadell")
    assert response.status_code == 201
    body = response.json()
    assert body["balance_cents"] == 0
    assert body["is_main"] is False
    assert body["payment_day"] is None and body["uncovered_debt_cents"] is None
    assert accounts(client)["Banco B"]["institution"] == "Sabadell"


def test_duplicate_active_name_409(client):
    create(client, name="Banco B")
    response = create(client, name="banco b ")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "account_exists"


def test_unknown_account_404(client):
    response = client.patch("/accounts/nope", json={"name": "X"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "account_not_found"


def test_rename_and_archive_keep_balance(client, category_ids):
    account_id = create(client, name="Banco B").json()["id"]
    client.post(
        "/transactions",
        json={"amount_cents": 5000, "category_id": category_ids["Ocio"], "account_id": account_id},
    )
    summary_before = client.get(f"/summary/{current_month()}").json()

    renamed = client.patch(f"/accounts/{account_id}", json={"name": "Banco Bis"}).json()
    assert renamed["name"] == "Banco Bis"
    archived = client.patch(f"/accounts/{account_id}", json={"archived": True}).json()
    assert archived["archived"] is True
    assert archived["balance_cents"] == -5000
    assert client.get(f"/summary/{current_month()}").json() == summary_before
    # Archived accounts free their name for a new active one.
    assert create(client, name="Banco Bis").status_code == 201


def test_derived_balance_follows_confirmed_transactions(client, category_ids):
    account_id = create(client, name="Banco B").json()["id"]
    client.post(
        "/transactions", json={"amount_cents": 200000, "kind": "income", "account_id": account_id}
    )
    client.post(
        "/transactions",
        json={"amount_cents": 35000, "category_id": category_ids["Alquiler"], "account_id": account_id},
    )
    assert accounts(client)["Banco B"]["balance_cents"] == 165000


def test_positive_opening_balance_is_income(client):
    before = budget(client)
    create(client, name="Banco B", opening_balance_cents=50000)
    after = budget(client)
    assert accounts(client)["Banco B"]["balance_cents"] == 50000
    assert after["income_cents"] == before["income_cents"] + 50000
    assert after["to_be_assigned_cents"] == before["to_be_assigned_cents"] + 50000


def test_credit_opening_debt_leaves_tba_unchanged(client):
    before = budget(client)
    response = create(client, name="Tarjeta Visa", type="credit", opening_balance_cents=-34000)
    assert response.status_code == 201
    card = response.json()
    after = budget(client)
    assert card["balance_cents"] == -34000
    assert card["payment_available_cents"] == 0
    assert card["uncovered_debt_cents"] == 34000
    assert after["to_be_assigned_cents"] == before["to_be_assigned_cents"]
    assert after["income_cents"] == before["income_cents"]
    summary = client.get(f"/summary/{current_month()}").json()
    assert summary["expense_cents"] == 0  # pre-existing debt is not spending


def test_omitted_account_lands_in_main(client, category_ids):
    create(client, name="Banco B")
    txn = client.post(
        "/transactions", json={"amount_cents": 1249, "category_id": category_ids["Ocio"]}
    ).json()
    main = next(a for a in client.get("/accounts").json() if a["is_main"])
    assert txn["account_id"] == main["id"] and main["name"] == "Efectivo"


def test_foreign_account_on_transaction_404(client, category_ids):
    response = client.post(
        "/transactions",
        json={"amount_cents": 100, "category_id": category_ids["Ocio"], "account_id": "nope"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "account_not_found"


def test_patch_moves_row_between_accounts(client, category_ids):
    account_id = create(client, name="Banco B").json()["id"]
    txn = client.post(
        "/transactions", json={"amount_cents": 3000, "category_id": category_ids["Ocio"]}
    ).json()
    moved = client.patch(f"/transactions/{txn['id']}", json={"account_id": account_id})
    assert moved.status_code == 200
    listed = accounts(client)
    assert listed["Banco B"]["balance_cents"] == -3000
    assert listed["Efectivo"]["balance_cents"] == 0


def test_payment_day_only_for_credit(client):
    response = create(client, name="Banco B", payment_day=10)
    assert response.status_code == 422
    card = create(client, name="Visa", type="credit", payment_day=10).json()
    assert card["payment_day"] == 10
    cleared = client.patch(f"/accounts/{card['id']}", json={"payment_day": None}).json()
    assert cleared["payment_day"] is None
