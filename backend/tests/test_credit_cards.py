"""Credit cards, YNAB model (spec: credit-cards, budget-api deltas)."""

import random

from sqlalchemy import func, select

from app.models import Account, Transaction
from app.services.budget_view import CardSetup, MonthActivity, month_bounds, month_math

# ---- Pure month math (no database) ------------------------------------------

CARDS = CardSetup(order=["visa", "amex"], payment_category={"visa": "pago-visa", "amex": "pago-amex"})


def test_budgeted_card_purchase_moves_to_payment_category():
    act = MonthActivity(card_spend={"super": {"visa": 20000}})
    result = month_math({"super": 40000}, {}, act, CARDS)
    assert result.spent["super"] == 20000
    assert result.available["super"] == 20000
    assert result.available["pago-visa"] == 20000
    assert result.credit_overspent == {}


def test_card_overspending_is_not_moved():
    act = MonthActivity(card_spend={"super": {"visa": 20000}})
    result = month_math({"super": 15000}, {}, act, CARDS)
    assert result.available["pago-visa"] == 15000
    assert result.credit_overspent["super"] == 5000
    assert result.available["super"] == -5000


def test_cash_spending_applies_first():
    act = MonthActivity(cash_net={"super": -6000}, card_spend={"super": {"visa": 6000}})
    result = month_math({"super": 10000}, {}, act, CARDS)
    assert result.available["pago-visa"] == 4000
    assert result.credit_overspent["super"] == 2000
    assert result.available["super"] == -2000


def test_card_refund_moves_back():
    act = MonthActivity(card_refund={"super": {"visa": 1250}})
    result = month_math({"super": 40000}, {}, act, CARDS)
    assert result.available["super"] == 41250
    assert result.available["pago-visa"] == -1250


def test_payments_consume_payment_category():
    act = MonthActivity(card_spend={"super": {"visa": 20000}}, payments={"visa": 20000})
    result = month_math({"super": 40000}, {}, act, CARDS)
    assert result.available["pago-visa"] == 0
    assert result.spent["pago-visa"] == 20000
    assert result.available["super"] == 20000


def test_pool_funds_cards_in_creation_order():
    act = MonthActivity(card_spend={"super": {"amex": 3000, "visa": 3000}})
    result = month_math({"super": 4000}, {}, act, CARDS)
    assert result.available["pago-visa"] == 3000
    assert result.available["pago-amex"] == 1000
    assert result.credit_overspent["super"] == 2000


# ---- API ------------------------------------------------------------------------


def view(client, month: str) -> dict:
    return client.get(f"/budget/{month}").json()


def cat(v: dict, category_id: str) -> dict:
    return next(c for g in v["groups"] for c in g["categories"] if c["id"] == category_id)


def assign(client, month: str, category_id: str, cents: int) -> None:
    client.put(f"/budget/{month}/assignments/{category_id}", json={"amount_cents": cents})


def make_card(client, name: str = "Visa BBVA", **extra) -> dict:
    return client.post("/accounts", json={"name": name, "type": "credit", **extra}).json()


def card_purchase(client, card_id: str, category_id: str, cents: int, day: str, kind="expense"):
    return client.post(
        "/transactions",
        json={
            "amount_cents": cents,
            "category_id": category_id,
            "kind": kind,
            "account_id": card_id,
            "date": day,
        },
    )


def main_id(client) -> str:
    return next(a["id"] for a in client.get("/accounts").json() if a["is_main"])


def pay(client, card_id: str, cents: int, day: str):
    return client.post(
        "/transfers",
        json={"from_account_id": main_id(client), "to_account_id": card_id, "amount_cents": cents, "date": day},
    )


def account(client, account_id: str) -> dict:
    return next(a for a in client.get("/accounts").json() if a["id"] == account_id)


def test_card_creation_brings_locked_payment_category(client):
    card = make_card(client)
    june = view(client, "2026-06")
    group = next(g for g in june["groups"] if g["name"] == "Tarjetas de crédito")
    payment = group["categories"][0]
    assert payment["name"] == "Pago Visa BBVA"
    assert payment["kind"] == "credit_payment"
    assert payment["payment_account_id"] == card["id"]
    assert payment["assigned_cents"] == 0 and payment["available_cents"] == 0

    groups = client.get("/categories").json()
    system = next(g for g in groups if g["system"])
    other = next(g for g in groups if not g["system"])
    for body in ({"group_id": other["id"]}, {"archived": True}):
        response = client.patch(f"/categories/{payment['id']}", json=body)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "payment_category_locked"
    assert client.delete(f"/categories/groups/{system['id']}").status_code == 409
    response = client.post(
        "/categories", json={"name": "Otra", "group_id": system["id"]}
    )
    assert response.status_code == 409


def test_payment_category_follows_rename_and_archive(client):
    card = make_card(client)
    client.patch(f"/accounts/{card['id']}", json={"name": "Visa Oro"})
    names = [c["name"] for g in client.get("/categories").json() for c in g["categories"]]
    assert "Pago Visa Oro" in names
    client.patch(f"/accounts/{card['id']}", json={"archived": True})
    payment = next(
        c for g in client.get("/categories").json() for c in g["categories"] if c["name"] == "Pago Visa Oro"
    )
    assert payment["archived"] is True


def test_purchase_moves_money_and_payment_consumes_it(client, category_ids):
    supermercado = category_ids["Supermercado"]
    card = make_card(client)
    view(client, "2026-06")
    client.post("/transactions", json={"amount_cents": 100000, "kind": "income", "date": "2026-06-01"})
    assign(client, "2026-06", supermercado, 40000)
    tba_before = view(client, "2026-06")["to_be_assigned_cents"]

    card_purchase(client, card["id"], supermercado, 20000, "2026-06-05")
    june = view(client, "2026-06")
    payment_id = account(client, card["id"])["payment_category_id"]
    assert cat(june, supermercado)["spent_cents"] == 20000
    assert cat(june, supermercado)["available_cents"] == 20000
    assert cat(june, payment_id)["available_cents"] == 20000
    assert june["to_be_assigned_cents"] == tba_before

    pay(client, card["id"], 20000, "2026-06-10")
    june = view(client, "2026-06")
    assert cat(june, payment_id)["available_cents"] == 0
    assert cat(june, payment_id)["spent_cents"] == 20000
    assert cat(june, supermercado)["available_cents"] == 20000
    assert june["to_be_assigned_cents"] == tba_before
    assert account(client, card["id"])["balance_cents"] == 0

    card_purchase(client, card["id"], supermercado, 1250, "2026-06-12", kind="income")
    june = view(client, "2026-06")
    assert cat(june, supermercado)["available_cents"] == 21250
    assert cat(june, payment_id)["available_cents"] == -1250


def test_credit_overspending_becomes_uncovered_debt(client, category_ids):
    supermercado, restaurantes = category_ids["Supermercado"], category_ids["Restaurantes"]
    card = make_card(client)
    view(client, "2026-06")
    client.post("/transactions", json={"amount_cents": 100000, "kind": "income", "date": "2026-06-01"})
    assign(client, "2026-06", supermercado, 15000)
    assign(client, "2026-06", restaurantes, 10000)
    card_purchase(client, card["id"], supermercado, 20000, "2026-06-05")
    payment_id = account(client, card["id"])["payment_category_id"]

    june = view(client, "2026-06")
    assert cat(june, supermercado)["credit_overspent_cents"] == 5000
    assert cat(june, payment_id)["available_cents"] == 15000
    # Uncovered at the current month: the debt stays, the category resets.
    assert account(client, card["id"])["uncovered_debt_cents"] == 5000

    july = view(client, "2026-07")
    assert cat(july, supermercado)["rollover_cents"] == 0
    assert cat(july, supermercado)["rollover_reset_cents"] == 5000
    assert july["overspent_deducted_cents"] == 0
    assert cat(july, payment_id)["rollover_cents"] == 15000

    # Covering it in the month funds the card instead.
    client.post(
        "/budget/2026-06/moves",
        json={"from_category_id": restaurantes, "to_category_id": supermercado, "amount_cents": 5000},
    )
    june = view(client, "2026-06")
    assert cat(june, supermercado)["credit_overspent_cents"] == 0
    assert cat(june, payment_id)["available_cents"] == 20000


def test_cash_part_of_overspending_still_hits_tba(client, category_ids):
    supermercado = category_ids["Supermercado"]
    card = make_card(client)
    view(client, "2026-06")
    client.post("/transactions", json={"amount_cents": 100000, "kind": "income", "date": "2026-06-01"})
    assign(client, "2026-06", supermercado, 10000)
    client.post(
        "/transactions",
        json={"amount_cents": 12000, "category_id": supermercado, "date": "2026-06-03"},
    )
    card_purchase(client, card["id"], supermercado, 3000, "2026-06-05")
    june = view(client, "2026-06")
    assert cat(june, supermercado)["available_cents"] == -5000
    assert cat(june, supermercado)["credit_overspent_cents"] == 3000
    july = view(client, "2026-07")
    assert july["overspent_deducted_cents"] == 2000


def test_suggested_payment_day(client):
    card = make_card(client)
    pay(client, card["id"], 10000, "2026-08-10")
    assert account(client, card["id"])["suggested_payment_day"] is None
    pay(client, card["id"], 12000, "2026-09-11")
    listed = account(client, card["id"])
    assert listed["suggested_payment_day"] == 10
    assert listed["payment_day"] is None
    client.patch(f"/accounts/{card['id']}", json={"payment_day": 10})
    assert account(client, card["id"])["suggested_payment_day"] is None


def test_identity_holds_with_cards_and_transfers(client, db, user, category_ids):
    """TBA + Σ available + Σ credit_overspent == Σ cash/bank activity."""
    rng = random.Random(20261004)
    cats = list(category_ids.values())
    visa = make_card(client, "Visa", opening_balance_cents=-30000)["id"]
    amex = make_card(client, "Amex")["id"]
    bank = client.post("/accounts", json={"name": "Banco", "type": "bank"}).json()["id"]
    cash = main_id(client)
    months = ["2026-06", "2026-07", "2026-08", "2026-09"]
    opened = ["2026-06", "2026-07", "2026-09"]

    for month in months:
        if month in opened:
            view(client, month)
        for _ in range(rng.randint(5, 10)):
            day = f"{month}-{rng.randint(1, 28):02d}"
            roll = rng.random()
            if roll < 0.2:
                client.post("/transactions", json={"amount_cents": rng.randint(50000, 300000), "kind": "income", "date": day, "account_id": rng.choice([cash, bank])})
            elif roll < 0.5:
                client.post("/transactions", json={"amount_cents": rng.randint(500, 40000), "category_id": rng.choice(cats), "date": day, "account_id": rng.choice([cash, bank])})
            elif roll < 0.75:
                card_purchase(client, rng.choice([visa, amex]), rng.choice(cats), rng.randint(500, 40000), day)
            elif roll < 0.8:
                card_purchase(client, rng.choice([visa, amex]), rng.choice(cats), rng.randint(100, 3000), day, kind="income")
            elif roll < 0.92:
                client.post("/transfers", json={"from_account_id": rng.choice([cash, bank]), "to_account_id": rng.choice([visa, amex]), "amount_cents": rng.randint(1000, 30000), "date": day})
            else:
                client.post("/transfers", json={"from_account_id": cash, "to_account_id": bank, "amount_cents": rng.randint(1000, 30000), "date": day})
        if month in opened:
            for category_id in rng.sample(cats, 4):
                assign(client, month, category_id, rng.randint(0, 60000))

    credit_ids = set(db.scalars(select(Account.id).where(Account.user_id == user.id, Account.type == "credit")))
    for month in months:
        v = view(client, month)
        _, end = month_bounds(month)
        activity = db.scalar(
            select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                Transaction.user_id == user.id,
                Transaction.status == "confirmed",
                Transaction.date < end,
                Transaction.account_id.not_in(credit_ids),
            )
        )
        categories = [c for g in v["groups"] for c in g["categories"]]
        total = (
            v["to_be_assigned_cents"]
            + sum(c["available_cents"] for c in categories)
            + sum(c["credit_overspent_cents"] for c in categories)
        )
        assert total == activity, month
