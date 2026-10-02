"""Budget rules: To Be Assigned carry-over, overspending reset, moves, cover
suggestions (openspec change budget-rules)."""

import random
import uuid
from datetime import date

from sqlalchemy import func, select

from app.models import Account, BudgetMonth, Transaction
from app.services.budget_view import month_bounds


def view(client, month: str) -> dict:
    return client.get(f"/budget/{month}").json()


def cat(v: dict, category_id: str) -> dict:
    return next(c for g in v["groups"] for c in g["categories"] if c["id"] == category_id)


def assign(client, month: str, category_id: str, cents: int) -> dict:
    return client.put(
        f"/budget/{month}/assignments/{category_id}", json={"amount_cents": cents}
    ).json()


def income(client, cents: int, day: str) -> None:
    client.post("/transactions", json={"amount_cents": cents, "kind": "income", "date": day})


def expense(client, category_id: str, cents: int, day: str) -> None:
    client.post("/transactions", json={"amount_cents": cents, "category_id": category_id, "date": day})


def move(client, month: str, source: str | None, target: str, cents: int):
    return client.post(
        f"/budget/{month}/moves",
        json={"from_category_id": source, "to_category_id": target, "amount_cents": cents},
    )


def clear_drafts(client, month: str) -> None:
    """New months draft the previous month's assignments; zero them out."""
    for g in view(client, month)["groups"]:
        for c in g["categories"]:
            if c["assigned_cents"]:
                assign(client, month, c["id"], 0)


# ---- To Be Assigned carry-over ------------------------------------------------


def test_unassigned_money_carries_to_next_month(client, category_ids):
    view(client, "2026-09")
    income(client, 470000, "2026-09-02")
    assign(client, "2026-09", category_ids["Alquiler"], 440000)
    assert view(client, "2026-09")["to_be_assigned_cents"] == 30000

    clear_drafts(client, "2026-10")
    october = view(client, "2026-10")
    assert october["carried_in_cents"] == 30000
    assert october["to_be_assigned_cents"] == 30000


def test_late_salary_funds_next_month(client):
    view(client, "2026-09")
    income(client, 350000, "2026-09-27")
    assert view(client, "2026-09")["to_be_assigned_cents"] == 350000
    october = view(client, "2026-10")
    assert october["carried_in_cents"] == 350000
    assert october["to_be_assigned_cents"] == 350000


def test_over_assigned_month_carries_the_negative(client, category_ids):
    view(client, "2026-09")
    income(client, 10000, "2026-09-01")
    assign(client, "2026-09", category_ids["Ocio"], 18500)
    assert view(client, "2026-09")["to_be_assigned_cents"] == -8500
    assert view(client, "2026-10")["carried_in_cents"] == -8500


def test_history_before_the_budget_seeds_to_be_assigned(client, category_ids):
    income(client, 60000, "2026-06-05")
    expense(client, category_ids["Supermercado"], 10000, "2026-06-10")
    july = view(client, "2026-07")  # first budget month
    assert july["carried_in_cents"] == 50000
    assert july["to_be_assigned_cents"] == 50000


# ---- Overspending ---------------------------------------------------------------


def test_uncovered_overspending_resets_category_and_hits_tba(client, category_ids):
    supermercado = category_ids["Supermercado"]
    view(client, "2026-09")
    income(client, 20000, "2026-09-01")
    assign(client, "2026-09", supermercado, 10000)
    expense(client, supermercado, 15000, "2026-09-12")

    september = view(client, "2026-09")
    assert cat(september, supermercado)["available_cents"] == -5000
    assert cat(september, supermercado)["overspent_cents"] == 5000
    assert september["to_be_assigned_cents"] == 10000  # deduction happens next month

    clear_drafts(client, "2026-10")
    october = view(client, "2026-10")
    assert cat(october, supermercado)["rollover_cents"] == 0
    assert cat(october, supermercado)["rollover_reset_cents"] == 5000
    assert october["overspent_deducted_cents"] == 5000
    assert october["carried_in_cents"] == 10000
    assert october["to_be_assigned_cents"] == 5000


def test_overspending_covered_in_month_is_not_deducted(client, category_ids):
    supermercado, ocio = category_ids["Supermercado"], category_ids["Ocio"]
    view(client, "2026-09")
    income(client, 20000, "2026-09-01")
    assign(client, "2026-09", supermercado, 10000)
    assign(client, "2026-09", ocio, 8000)
    expense(client, supermercado, 15000, "2026-09-12")
    assert move(client, "2026-09", ocio, supermercado, 5000).status_code == 200

    october = view(client, "2026-10")
    assert october["overspent_deducted_cents"] == 0
    assert cat(october, supermercado)["rollover_cents"] == 0
    assert cat(october, ocio)["rollover_cents"] == 3000


def test_chain_crosses_an_unopened_month(client, db, user, category_ids):
    ocio = category_ids["Ocio"]
    view(client, "2026-09")
    income(client, 10000, "2026-09-01")
    assign(client, "2026-09", ocio, 10000)
    expense(client, ocio, 3000, "2026-10-10")  # October is never opened

    november = view(client, "2026-11")
    assert cat(november, ocio)["rollover_cents"] == 7000
    october_rows = db.scalar(
        select(func.count()).where(BudgetMonth.user_id == user.id, BudgetMonth.month == "2026-10")
    )
    assert october_rows == 0


def test_budget_identity_holds_for_generated_histories(client, db, user, category_ids):
    """TBA + Σ available == Σ confirmed activity up to month end, every month."""
    rng = random.Random(20261001)
    account_id = db.scalar(select(Account.id).where(Account.user_id == user.id))
    cats = list(category_ids.values())
    months = ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    opened = ["2026-06", "2026-07", "2026-09"]  # August stays unopened while writing

    for month in months:
        if month in opened:
            view(client, month)
        year, mon = (int(p) for p in month.split("-"))
        for _ in range(rng.randint(3, 7)):
            day = f"{month}-{rng.randint(1, 28):02d}"
            roll = rng.random()
            if roll < 0.25:
                income(client, rng.randint(10000, 300000), day)
            elif roll < 0.75:
                expense(client, rng.choice(cats), rng.randint(500, 60000), day)
            elif roll < 0.9:  # categorized refund
                client.post(
                    "/transactions",
                    json={
                        "amount_cents": rng.randint(100, 5000),
                        "kind": "income",
                        "category_id": rng.choice(cats),
                        "date": day,
                    },
                )
            else:  # uncategorized outflow (import row confirmed without category)
                db.add(
                    Transaction(
                        user_id=user.id,
                        account_id=account_id,
                        date=date(year, mon, rng.randint(1, 28)),
                        amount_cents=-rng.randint(100, 20000),
                        status="confirmed",
                        dedupe_hash=f"uncat-{uuid.uuid4()}",
                    )
                )
                db.flush()
        if month in opened:
            for category_id in rng.sample(cats, 4):
                assign(client, month, category_id, rng.randint(0, 80000))
            v = view(client, month)
            donors = [c for g in v["groups"] for c in g["categories"] if c["available_cents"] > 0]
            if donors:
                source = rng.choice(donors)
                target = rng.choice([c for c in cats if c != source["id"]])
                move(client, month, source["id"], target, rng.randint(1, source["available_cents"]))

    for month in months:
        v = view(client, month)
        _, end = month_bounds(month)
        activity = db.scalar(
            select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                Transaction.user_id == user.id,
                Transaction.status == "confirmed",
                Transaction.date < end,
            )
        )
        available = sum(c["available_cents"] for g in v["groups"] for c in g["categories"])
        assert v["to_be_assigned_cents"] + available == activity, month


# ---- Moves ------------------------------------------------------------------------


def test_move_covers_overspending_from_another_category(client, category_ids):
    supermercado, restaurantes = category_ids["Supermercado"], category_ids["Restaurantes"]
    view(client, "2026-10")
    income(client, 20000, "2026-10-01")
    assign(client, "2026-10", supermercado, 10000)
    assign(client, "2026-10", restaurantes, 12000)
    expense(client, supermercado, 15000, "2026-10-05")
    before = view(client, "2026-10")["to_be_assigned_cents"]

    response = move(client, "2026-10", restaurantes, supermercado, 5000)
    assert response.status_code == 200
    after = response.json()
    assert cat(after, supermercado)["available_cents"] == 0
    assert cat(after, restaurantes)["available_cents"] == 7000
    assert cat(after, supermercado)["suggestion_state"] == "edited"
    assert cat(after, restaurantes)["suggestion_state"] == "edited"
    assert after["to_be_assigned_cents"] == before


def test_move_from_to_be_assigned(client, category_ids):
    supermercado = category_ids["Supermercado"]
    view(client, "2026-10")
    income(client, 8000, "2026-10-01")
    after = move(client, "2026-10", None, supermercado, 5000).json()
    assert cat(after, supermercado)["assigned_cents"] == 5000
    assert after["to_be_assigned_cents"] == 3000


def test_move_rejects_money_that_is_not_there(client, category_ids):
    ocio, supermercado = category_ids["Ocio"], category_ids["Supermercado"]
    view(client, "2026-10")
    income(client, 12000, "2026-10-01")
    assign(client, "2026-10", ocio, 12000)

    response = move(client, "2026-10", ocio, supermercado, 20000)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "insufficient_available"
    assert cat(view(client, "2026-10"), ocio)["assigned_cents"] == 12000

    response = move(client, "2026-10", None, supermercado, 100)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "insufficient_to_be_assigned"


def test_move_validation_codes(client, category_ids):
    ocio = category_ids["Ocio"]
    view(client, "2026-10")
    same = move(client, "2026-10", ocio, ocio, 100)
    assert same.status_code == 422 and same.json()["detail"]["code"] == "same_category"
    foreign = move(client, "2026-10", ocio, str(uuid.uuid4()), 100)
    assert foreign.status_code == 404 and foreign.json()["detail"]["code"] == "category_not_found"
    zero = move(client, "2026-10", None, ocio, 0)
    assert zero.status_code == 422


def test_move_from_rollover_makes_the_assignment_negative(client, category_ids):
    ahorro, ocio = category_ids["Ahorro"], category_ids["Ocio"]
    view(client, "2026-09")
    income(client, 60000, "2026-09-01")
    assign(client, "2026-09", ahorro, 60000)
    clear_drafts(client, "2026-10")

    after = move(client, "2026-10", ahorro, ocio, 10000).json()
    assert cat(after, ahorro)["assigned_cents"] == -10000
    assert cat(after, ahorro)["available_cents"] == 50000


# ---- Cover suggestions -------------------------------------------------------------


def test_cover_suggestion_prefers_to_be_assigned(client, category_ids):
    supermercado, restaurantes = category_ids["Supermercado"], category_ids["Restaurantes"]
    view(client, "2026-10")
    income(client, 15000, "2026-10-01")
    assign(client, "2026-10", restaurantes, 12000)  # leaves 3000 unassigned
    expense(client, supermercado, 5000, "2026-10-05")

    v = view(client, "2026-10")
    assert cat(v, supermercado)["cover_suggestion"] == {"source_category_id": None, "amount_cents": 3000}
    assert cat(v, restaurantes)["cover_suggestion"] is None


def test_cover_suggestion_uses_largest_available(client, category_ids):
    supermercado = category_ids["Supermercado"]
    restaurantes, ocio = category_ids["Restaurantes"], category_ids["Ocio"]
    view(client, "2026-10")
    income(client, 16000, "2026-10-01")
    assign(client, "2026-10", restaurantes, 12000)
    assign(client, "2026-10", ocio, 4000)
    expense(client, supermercado, 5000, "2026-10-05")

    suggestion = cat(view(client, "2026-10"), supermercado)["cover_suggestion"]
    assert suggestion == {"source_category_id": restaurantes, "amount_cents": 5000}


def test_cover_suggestions_never_share_the_same_euros(client, category_ids):
    supermercado, gasolina = category_ids["Supermercado"], category_ids["Gasolina"]
    restaurantes = category_ids["Restaurantes"]
    view(client, "2026-10")
    income(client, 6000, "2026-10-01")
    assign(client, "2026-10", restaurantes, 6000)
    expense(client, supermercado, 5000, "2026-10-05")
    expense(client, gasolina, 2000, "2026-10-06")

    v = view(client, "2026-10")
    assert cat(v, supermercado)["cover_suggestion"] == {"source_category_id": restaurantes, "amount_cents": 5000}
    assert cat(v, gasolina)["cover_suggestion"] == {"source_category_id": restaurantes, "amount_cents": 1000}
