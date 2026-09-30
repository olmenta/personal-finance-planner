from datetime import date

from app.models import Transaction


def get_category(view: dict, name: str) -> dict:
    for group in view["groups"]:
        for category in group["categories"]:
            if category["name"] == name:
                return category
    raise AssertionError(f"category {name} not in view")


def test_first_month_empty(client):
    view = client.get("/budget/2026-05").json()
    assert view["income_cents"] == 0
    assert view["to_be_assigned_cents"] == 0
    for group in view["groups"]:
        for category in group["categories"]:
            assert category["assigned_cents"] == 0
            assert category["suggestion_state"] != "draft"


def test_new_month_drafts_from_previous(client, category_ids):
    client.get("/budget/2026-05")
    client.put(
        f"/budget/2026-05/assignments/{category_ids['Supermercado']}",
        json={"amount_cents": 40000},
    )
    june = client.get("/budget/2026-06").json()
    cat = get_category(june, "Supermercado")
    assert cat["assigned_cents"] == 40000
    assert cat["suggestion_cents"] == 40000
    assert cat["suggestion_state"] == "draft"


def test_row_math_spec_scenario(client, category_ids):
    """rollover 32 € + assigned 120 € − spent 138 € = 14 € available."""
    suministros = category_ids["Suministros"]
    client.get("/budget/2026-05")
    client.put(f"/budget/2026-05/assignments/{suministros}", json={"amount_cents": 3200})
    # June: draft becomes 3200; rollover from May = 3200 (nothing spent in May)
    client.get("/budget/2026-06")
    client.put(f"/budget/2026-06/assignments/{suministros}", json={"amount_cents": 12000})
    client.post(
        "/transactions",
        json={"amount_cents": 13800, "category_id": suministros, "date": "2026-06-09"},
    )
    june = client.get("/budget/2026-06").json()
    cat = get_category(june, "Suministros")
    assert cat["rollover_cents"] == 3200
    assert cat["spent_cents"] == 13800
    assert cat["available_cents"] == 1400


def test_staged_transactions_excluded_from_spent(client, db, user, category_ids):
    ocio = category_ids["Ocio"]
    client.post(
        "/transactions", json={"amount_cents": 4500, "category_id": ocio, "date": "2026-06-03"}
    )
    account_id = db.query(Transaction).first().account_id
    db.add(
        Transaction(
            user_id=user.id,
            account_id=account_id,
            category_id=ocio,
            date=date(2026, 6, 4),
            amount_cents=-5000,
            status="staged",
            dedupe_hash="staged-1",
        )
    )
    db.flush()
    view = client.get("/budget/2026-06").json()
    assert get_category(view, "Ocio")["spent_cents"] == 4500


def test_categorized_refund_restores_category_not_income(client, category_ids):
    """Spec scenario: refund nets spent and stays out of income."""
    supermercado = category_ids["Supermercado"]
    client.post(
        "/transactions",
        json={"amount_cents": 13800, "category_id": supermercado, "date": "2026-06-05"},
    )
    client.post(
        "/transactions",
        json={
            "amount_cents": 1250,
            "category_id": supermercado,
            "kind": "income",
            "date": "2026-06-07",
        },
    )
    view = client.get("/budget/2026-06").json()
    assert get_category(view, "Supermercado")["spent_cents"] == 12550
    assert view["income_cents"] == 0


def test_uncategorized_inflow_is_income(client, category_ids):
    client.post(
        "/transactions",
        json={"amount_cents": 235000, "kind": "income", "date": "2026-06-01"},
    )
    view = client.get("/budget/2026-06").json()
    assert view["income_cents"] == 235000
    for group in view["groups"]:
        for cat in group["categories"]:
            assert cat["spent_cents"] == 0


def test_assignment_recalculates_to_be_assigned(client, category_ids):
    client.post(
        "/transactions",
        json={"amount_cents": 235000, "kind": "income", "date": "2026-06-01"},
    )
    client.get("/budget/2026-06")
    client.put(
        f"/budget/2026-06/assignments/{category_ids['Alquiler']}",
        json={"amount_cents": 193800},
    )
    response = client.put(
        f"/budget/2026-06/assignments/{category_ids['Supermercado']}",
        json={"amount_cents": 41200},
    ).json()
    assert response["to_be_assigned_cents"] == 0
    assert response["suggestion_state"] == "edited"


def test_first_month_quickfill_null(client):
    view = client.get("/budget/2026-05").json()
    for group in view["groups"]:
        for category in group["categories"]:
            assert category["last_month_assigned_cents"] is None
            assert category["avg_3m_cents"] is None
            assert category["last_month_spent_cents"] is None


def test_quickfill_from_history(client, category_ids):
    """Spec: May assigned 120 € with 119 € spent → June quick-fill fields."""
    suministros = category_ids["Suministros"]
    client.get("/budget/2026-05")
    client.put(f"/budget/2026-05/assignments/{suministros}", json={"amount_cents": 12000})
    client.post(
        "/transactions",
        json={"amount_cents": 11900, "category_id": suministros, "date": "2026-05-12"},
    )
    june = client.get("/budget/2026-06").json()
    cat = get_category(june, "Suministros")
    assert cat["last_month_assigned_cents"] == 12000
    assert cat["last_month_spent_cents"] == 11900
    # Single previous month: average equals May's spend, whole euros.
    assert cat["avg_3m_cents"] == 11900


def test_confirm_preserves_edits(client, category_ids):
    client.get("/budget/2026-05")
    for name in ("Supermercado", "Restaurantes"):
        client.put(
            f"/budget/2026-05/assignments/{category_ids[name]}", json={"amount_cents": 10000}
        )
    june = client.get("/budget/2026-06").json()
    assert get_category(june, "Supermercado")["suggestion_state"] == "draft"

    # Edit one drafted category, then confirm everything.
    client.put(
        f"/budget/2026-06/assignments/{category_ids['Restaurantes']}",
        json={"amount_cents": 18000},
    )
    all_ids = [c["id"] for g in june["groups"] for c in g["categories"]]
    confirmed = client.post(
        "/budget/2026-06/confirm-suggestions", json={"category_ids": all_ids}
    ).json()

    assert get_category(confirmed, "Supermercado")["suggestion_state"] == "confirmed"
    edited = get_category(confirmed, "Restaurantes")
    assert edited["suggestion_state"] == "edited"
    assert edited["assigned_cents"] == 18000
