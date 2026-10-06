"""Category targets and annual plan: schedules, monthly amounts, drafting,
month overview, projection, summary (openspec change
category-targets-and-annual-plan)."""

import random

import pytest

from app.models import PaymentSchedule
from app.services import schedules as sched


@pytest.fixture(autouse=True)
def october_2026(monkeypatch):
    monkeypatch.setattr(sched, "current_month", lambda: "2026-10")


def S(**kw) -> PaymentSchedule:
    """Transient schedule for the pure functions."""
    kw.setdefault("name", "x")
    kw.setdefault("estimated", False)
    return PaymentSchedule(**kw)


def tree(client) -> dict:
    groups = client.get("/categories").json()
    return {
        "groups": {g["name"]: g["id"] for g in groups},
        "cats": {c["name"]: c for g in groups for c in g["categories"]},
    }


def new_category(client, name: str, savings: bool = False) -> str:
    group_id = next(iter(tree(client)["groups"].values()))
    response = client.post(
        "/categories", json={"name": name, "group_id": group_id, "savings": savings}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_schedule(client, category_id: str, **body) -> dict:
    body.setdefault("name", "Pago")
    response = client.post(f"/categories/{category_id}/schedules", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def set_income(client, cents: int, **body) -> dict:
    """Expected income as one monthly income schedule (spec: income-schedules)."""
    body = {"name": "Nómina", "amount_cents": cents, "pattern": "monthly", **body}
    response = client.post("/income-schedules", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def cat_view(view: dict, category_id: str) -> dict:
    return next(c for g in view["groups"] for c in g["categories"] if c["id"] == category_id)


COLEGIO = [
    dict(name="Cuota del colegio", amount_cents=63200, pattern="some_months",
         months=[9, 10, 11, 12, 1, 2, 3, 4, 5, 6], day=5),
    dict(name="Libros", amount_cents=22800, pattern="annual", month=9, day=10),
    dict(name="Seguro AMPA", amount_cents=6000, pattern="annual", month=10, day=20),
    dict(name="Reconfirmación", amount_cents=38700, pattern="annual", month=2, day=15),
]


# ---- 5.1 Schedules: occurrences, CRUD, validation ------------------------------------


def test_occurrences_per_pattern():
    school = S(pattern="some_months", months=[9, 10, 11, 12, 1, 2, 3, 4, 5, 6], amount_cents=63200)
    assert sched.occurs(school, "2026-10") and not sched.occurs(school, "2027-07")
    water = S(pattern="every_n", every_n=3, start_month="2026-11", amount_cents=12000)
    assert [m for m in ["2026-10", "2026-11", "2027-02", "2027-03", "2027-05", "2027-08"]
            if sched.occurs(water, m)] == ["2026-11", "2027-02", "2027-05", "2027-08"]
    finite = S(pattern="monthly", count=4, start_month="2026-10", amount_cents=2329)
    assert [sched.occurs(finite, m) for m in ["2026-09", "2026-10", "2027-01", "2027-02"]] == [
        False, True, True, False]
    once = S(pattern="once", once_month="2026-12", amount_cents=100000)
    assert sched.occurs(once, "2026-12") and not sched.occurs(once, "2027-12")
    goal = S(pattern="no_date", amount_cents=400000)
    assert not any(sched.occurs(goal, m) for m in ["2026-10", "2027-03"])


def test_schedule_crud_and_kind_switch(client):
    cid = new_category(client, "Colegio Tomi")
    created = add_schedule(client, cid, **COLEGIO[0])
    assert created["months"] == [1, 2, 3, 4, 5, 6, 9, 10, 11, 12]
    assert tree(client)["cats"]["Colegio Tomi"]["kind"] == "scheduled"

    listed = client.get(f"/categories/{cid}/schedules").json()
    assert [s["id"] for s in listed] == [created["id"]]

    patched = client.patch(f"/schedules/{created['id']}", json={"amount_cents": 65000}).json()
    assert patched["amount_cents"] == 65000 and patched["months"] == created["months"]
    switched = client.patch(
        f"/schedules/{created['id']}", json={"pattern": "annual", "month": 9}
    ).json()
    assert switched["pattern"] == "annual" and switched["months"] is None

    assert client.delete(f"/schedules/{created['id']}").status_code == 204
    assert client.get(f"/categories/{cid}/schedules").json() == []


def test_kind_is_derived_from_payments_and_the_savings_flag(client):
    cid = new_category(client, "Ahorro Tomy", savings=True)
    assert tree(client)["cats"]["Ahorro Tomy"]["kind"] == "savings"
    schedule = add_schedule(client, cid, amount_cents=400000, pattern="no_date")
    assert tree(client)["cats"]["Ahorro Tomy"]["kind"] == "scheduled"  # payments win
    client.delete(f"/schedules/{schedule['id']}")
    assert tree(client)["cats"]["Ahorro Tomy"]["kind"] == "savings"
    client.patch(f"/categories/{cid}", json={"savings": False})
    cat = tree(client)["cats"]["Ahorro Tomy"]
    assert (cat["kind"], cat["savings"]) == ("flexible", False)


@pytest.mark.parametrize(
    "body",
    [
        {"amount_cents": 50000, "pattern": "annual"},  # missing month
        {"amount_cents": 50000, "pattern": "some_months", "months": []},
        {"amount_cents": 50000, "pattern": "some_months", "months": [13]},
        {"amount_cents": 50000, "pattern": "every_n", "every_n": 3},  # missing start
        {"amount_cents": 50000, "pattern": "once"},
        {"amount_cents": 50000, "pattern": "monthly", "count": 4},  # count needs start
        {"amount_cents": 0, "pattern": "monthly"},
        {"amount_cents": 50000, "pattern": "weekly"},
        {"amount_cents": 50000, "pattern": "annual", "month": 3, "months": [3]},  # foreign field
    ],
)
def test_invalid_schedules_rejected(client, body):
    cid = new_category(client, "Seguro coche")
    response = client.post(f"/categories/{cid}/schedules", json={"name": "x", **body})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_schedule"


def test_schedules_404_for_unknown_ids(client):
    assert client.get("/categories/nope/schedules").status_code == 404
    assert client.patch("/schedules/nope", json={"amount_cents": 1}).status_code == 404
    assert client.delete("/schedules/nope").status_code == 404


def test_savings_flag_on_edit(client, category_ids):
    cid = category_ids["Ocio"]
    edited = client.patch(f"/categories/{cid}", json={"savings": True}).json()
    assert (edited["kind"], edited["savings"]) == ("savings", True)
    assert client.patch(f"/categories/{cid}", json={"savings": "maybe"}).status_code == 422


# ---- 5.2 Amounts -------------------------------------------------------------------------


def test_colegio_normal_and_catch_up():
    schedules = [S(**s) for s in COLEGIO]
    normal, catch_up, suggested = sched.amounts(schedules, "2026-10", saved=0)
    assert normal == 58292
    assert catch_up == 72140
    assert suggested == 72140


def test_caught_up_falls_back_to_normal():
    insurance = [S(pattern="annual", month=3, amount_cents=50000)]
    normal, catch_up, suggested = sched.amounts(insurance, "2026-10", saved=25000)
    assert (normal, catch_up, suggested) == (4167, 4167, 4167)


def test_one_off_rounds_up_to_the_cent():
    one_off = [S(pattern="once", once_month="2026-12", amount_cents=100000)]
    assert sched.amounts(one_off, "2026-10", saved=0) == (0, 33334, 33334)


# ---- 5.3 Drafting ----------------------------------------------------------------------


def test_scheduled_category_drafts_its_computed_amount(client, category_ids):
    client.get("/budget/2026-09")
    cid = new_category(client, "Colegio Tomi")
    for s in COLEGIO:
        add_schedule(client, cid, **s)
    client.put(f"/budget/2026-09/assignments/{category_ids['Ocio']}", json={"amount_cents": 5000})

    october = client.get("/budget/2026-10").json()
    row = cat_view(october, cid)
    assert row["assigned_cents"] == 72140 and row["suggestion_state"] == "confirmed"
    assert (row["kind"], row["normal_cents"], row["catch_up_cents"]) == ("scheduled", 58292, 72140)
    assert cat_view(october, category_ids["Ocio"])["assigned_cents"] == 5000  # copied


def test_first_month_drafts_scheduled_categories(client, category_ids):
    add_schedule(client, category_ids["Alquiler"], amount_cents=95200, pattern="monthly", day=1)
    first = client.get("/budget/2026-10").json()
    assert cat_view(first, category_ids["Alquiler"])["assigned_cents"] == 95200
    assert cat_view(first, category_ids["Ocio"])["assigned_cents"] == 0


def test_assignment_of_a_category_with_payments_is_not_typed(client, category_ids):
    luz = category_ids["Suministros"]
    add_schedule(client, luz, name="Luz", amount_cents=4000, pattern="monthly")
    client.get("/budget/2026-10")
    response = client.put(f"/budget/2026-10/assignments/{luz}", json={"amount_cents": 3200})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "assignment_from_payments"
    assert cat_view(client.get("/budget/2026-10").json(), luz)["assigned_cents"] == 4000


def test_adding_a_payment_updates_the_open_month(client, category_ids):
    luz = category_ids["Suministros"]
    client.get("/budget/2026-10")  # opened while still day-to-day
    add_schedule(client, luz, name="Luz", amount_cents=4000, pattern="monthly")
    assert cat_view(client.get("/budget/2026-10").json(), luz)["assigned_cents"] == 4000
    schedule = client.get(f"/categories/{luz}/schedules").json()[0]
    client.patch(f"/schedules/{schedule['id']}", json={"amount_cents": 5000})
    assert cat_view(client.get("/budget/2026-10").json(), luz)["assigned_cents"] == 5000


def test_past_months_keep_their_assignment(client, category_ids):
    luz = category_ids["Suministros"]
    client.get("/budget/2026-09")
    client.put(f"/budget/2026-09/assignments/{luz}", json={"amount_cents": 1000})
    add_schedule(client, luz, name="Luz", amount_cents=4000, pattern="monthly")
    assert cat_view(client.get("/budget/2026-09").json(), luz)["assigned_cents"] == 1000


def test_far_one_off_is_spread_over_every_month_until_it():
    trip = [S(pattern="once", once_month="2028-04", amount_cents=180000)]
    assert sched.amounts(trip, "2026-10", saved=0) == (0, 9474, 9474)  # 19 months


def test_future_payment_counts_its_yearly_share_in_the_plan(client):
    cid = new_category(client, "Coche nuevo")
    add_schedule(client, cid, name="Entrada", amount_cents=240000, pattern="once",
                 once_month="2028-09")  # 24 months from October 2026
    set_income(client, 300000)
    summary = client.get("/plan/summary?from=2026-10").json()
    assert summary["scheduled_cents"] == 0  # not due inside the window
    assert summary["goals_cents"] == 120000  # half of it is set aside this year


# ---- 5.4 Overview ------------------------------------------------------------------------


def overview(client, month="2026-10") -> dict:
    return client.get(f"/overview/{month}").json()


def assert_identity(v: dict):
    total = (v["covered_cents"] + v["left_to_spend"]["total_cents"] + v["saved"]["total_cents"]
             + v["to_be_assigned_cents"] - v["overspent_cents"])
    assert total == v["accounts_cents"]


def test_overview_mid_month_split(client, category_ids):
    alquiler = category_ids["Alquiler"]
    manameli = new_category(client, "Manameli")
    client.get("/budget/2026-10")
    add_schedule(client, alquiler, name="Alquiler", amount_cents=95200, pattern="monthly", day=1)
    add_schedule(client, manameli, name="Última cuota", amount_cents=100000, pattern="once",
                 once_month="2026-10", day=15)
    client.post("/transactions", json={"amount_cents": 300000, "kind": "income", "date": "2026-10-01"})
    # Computed: rent 952 €, Manameli 1.000 €. Moving money out leaves Manameli short.
    move = client.post("/budget/2026-10/moves", json={
        "from_category_id": manameli, "to_category_id": category_ids["Ocio"], "amount_cents": 50200})
    assert move.status_code == 200
    client.post("/transactions", json={"amount_cents": 95200, "category_id": alquiler, "date": "2026-10-01"})

    v = overview(client)
    assert [(p["name"], p["amount_cents"]) for p in v["paid"]["items"]] == [("Alquiler", 95200)]
    [pending] = v["to_pay"]
    assert (pending["name"], pending["covered_cents"], pending["short_cents"]) == (
        "Última cuota", 49800, 50200)
    assert_identity(v)


def test_estimated_bill_counts_as_paid(client, category_ids):
    luz = category_ids["Suministros"]
    client.get("/budget/2026-10")
    add_schedule(client, luz, name="Luz", amount_cents=10000, pattern="monthly", day=12, estimated=True)
    client.post("/transactions", json={"amount_cents": 9430, "category_id": luz, "date": "2026-10-12"})

    v = overview(client)
    assert v["to_pay"] == []
    assert [(p["name"], p["amount_cents"]) for p in v["paid"]["items"]] == [("Luz", 9430)]
    saved = {i["category_id"]: i["amount_cents"] for i in v["saved"]["items"]}
    assert saved[luz] == 570
    assert_identity(v)


def test_overview_identity_over_generated_data(client, category_ids):
    rng = random.Random(7)
    ids = list(category_ids.values())
    client.get("/budget/2026-09")
    for cid in rng.sample(ids, 3):
        add_schedule(client, cid, amount_cents=rng.randint(1000, 90000), pattern="monthly",
                     day=rng.randint(1, 28), estimated=rng.random() < 0.5)
    client.patch(f"/categories/{ids[0]}", json={"savings": True})
    for month in ["2026-09", "2026-10"]:
        client.get(f"/budget/{month}")
        client.post("/transactions", json={"amount_cents": rng.randint(50000, 300000),
                                           "kind": "income", "date": f"{month}-02"})
        for _ in range(8):
            client.post("/transactions", json={
                "amount_cents": rng.randint(500, 60000), "category_id": rng.choice(ids),
                "date": f"{month}-{rng.randint(1, 28):02d}"})
        for cid in rng.sample(ids, 4):
            client.put(f"/budget/{month}/assignments/{cid}", json={"amount_cents": rng.randint(0, 90000)})
        assert_identity(overview(client, month))


# ---- 5.5 / 5.6 Projection and summary on the prototype's real-budget fixture --------------

FLEX = {"Supermercado": 40000, "Restaurantes": 40000, "Gasolina": 8000, "Viajes": 15000,
        "Ropa": 20000, "Regalos": 5000}
SCHEDULED = {
    "Alquiler": [dict(amount_cents=95200, pattern="monthly", day=1)],
    "Luz": [dict(amount_cents=10000, pattern="monthly", day=12, estimated=True)],
    "Gas": [dict(amount_cents=7000, pattern="monthly", day=20, estimated=True)],
    "Agua": [dict(amount_cents=12000, pattern="every_n", every_n=3, start_month="2026-11", day=8)],
    "Seguro casa": [dict(amount_cents=6000, pattern="annual", month=6)],
    "Internet": [dict(amount_cents=3900, pattern="monthly", day=3)],
    "Seguro médico": [dict(amount_cents=13766, pattern="monthly", day=1)],
    "Gimnasio": [dict(amount_cents=8000, pattern="monthly", day=5)],
    "Colegio Tomi": COLEGIO,
    "Fútbol": [dict(amount_cents=51920, pattern="annual", month=9),
               dict(amount_cents=22000, pattern="annual", month=9)],
    "Ropa colegio": [dict(amount_cents=80000, pattern="annual", month=9),
                     dict(amount_cents=21500, pattern="annual", month=9)],
    "Cuota Martina": [dict(amount_cents=27100, pattern="monthly", day=1)],
    "Coche": [dict(amount_cents=50000, pattern="annual", month=3),
              dict(amount_cents=5887, pattern="annual", month=4),
              dict(amount_cents=5400, pattern="annual", month=5)],
    "Sabadell": [dict(amount_cents=29017, pattern="monthly", day=1)],
    "Tarjeta": [dict(amount_cents=23700, pattern="monthly", day=10)],
    "Manameli": [dict(amount_cents=100000, pattern="once", once_month="2026-10", day=15)],
    "Cetelem": [dict(amount_cents=2329, pattern="monthly", count=4, start_month="2026-10"),
                dict(amount_cents=1704, pattern="monthly", count=4, start_month="2026-10")],
    "Suscripciones x": [dict(amount_cents=a, pattern="monthly", day=1)
                        for a in (300, 431, 3022, 2500, 1500, 700, 999, 3222, 2236, 2300, 1800, 4596)],
}
GOALS = {"Vacaciones": 400000, "Cumpleaños": 120000, "Imprevistos coche": 40000}


def build_prototype_budget(client, flex_month: str) -> None:
    """The user's real 2026-27 plan, as used by the approved prototype."""
    client.get(f"/budget/{flex_month}")  # materialize before schedules: no computed drafts
    for name, budget in FLEX.items():
        cid = new_category(client, f"{name} p")
        client.put(f"/budget/{flex_month}/assignments/{cid}", json={"amount_cents": budget})
    for name, items in SCHEDULED.items():
        cid = new_category(client, f"{name} p")
        for i, item in enumerate(items):
            add_schedule(client, cid, **{"name": f"{name} {i}", **item})
    for name, amount in GOALS.items():
        add_schedule(client, new_category(client, f"{name} p"), name=name,
                     amount_cents=amount, pattern="no_date")
    set_income(client, 470000)


def test_projection_matches_the_prototype_october(client):
    build_prototype_budget(client, "2026-09")  # nothing saved, October simulated from zero
    view = client.get("/plan/upcoming?from=2026-09").json()
    assert view["income_known"] is True and len(view["months"]) == 12
    october = view["months"][1]
    assert october["month"] == "2026-10"
    assert october["payments_cents"] == 414522
    assert october["flexible_funded_cents"] == 55478  # of 1.280 € (prototype)
    assert october["flexible_budget_cents"] == 128000
    assert october["set_aside_funded_cents"] == 0
    assert all(o["covered"] for o in october["occurrences"])  # due payments come first


def test_structural_gap_surfaces_as_unfunded_set_asides(client):
    build_prototype_budget(client, "2026-09")
    months = client.get("/plan/upcoming?from=2026-09").json()["months"][1:]
    assert all(m["short_cents"] == 0 for m in months)
    assert any(m["set_aside_funded_cents"] < m["set_aside_wanted_cents"] for m in months)


def test_payment_at_risk_is_flagged(client, category_ids):
    client.get("/budget/2026-10")
    super_ = category_ids["Supermercado"]
    client.put(f"/budget/2026-10/assignments/{super_}", json={"amount_cents": 100000})
    coche = new_category(client, "Coche")
    add_schedule(client, coche, name="Seguro", amount_cents=500000, pattern="annual", month=3)
    set_income(client, 100000, day=1)  # only day-to-day fits

    march = next(m for m in client.get("/plan/upcoming?from=2026-10").json()["months"]
                 if m["month"] == "2027-03")
    [insurance] = march["occurrences"]
    assert insurance["covered"] is False and insurance["short_cents"] > 0


def test_unknown_income_has_no_coverage(client, category_ids):
    add_schedule(client, category_ids["Alquiler"], amount_cents=95200, pattern="monthly")
    view = client.get("/plan/upcoming?from=2026-10").json()
    assert view["income_known"] is False
    assert all(o["covered"] is None for m in view["months"][1:] for o in m["occurrences"])
    assert client.get("/plan/summary?from=2026-10").json()["gap_cents"] is None


def test_summary_gap_on_the_prototype_budget(client):
    build_prototype_budget(client, "2026-10")
    summary = client.get("/plan/summary?from=2026-10").json()
    assert summary["income_cents"] == 5640000
    assert summary["scheduled_cents"] == 4001807
    assert summary["flexible_cents"] == 1536000
    assert summary["goals_cents"] == 560000
    assert summary["gap_cents"] == -457807
    assert summary["gap_monthly_cents"] == -38151


def test_extra_pay_funds_its_month(client):
    set_income(client, 200000, day=27)
    set_income(client, 200000, name="Paga extra", pattern="some_months", months=[6, 12], day=20)
    verano = new_category(client, "Verano")
    add_schedule(client, verano, name="Campamento", amount_cents=350000, pattern="once",
                 once_month="2027-06", day=30)
    months = {m["month"]: m for m in client.get("/plan/upcoming?from=2026-10").json()["months"]}
    assert months["2027-05"]["expected_income_cents"] == 200000
    assert months["2027-06"]["expected_income_cents"] == 400000
    [camp] = months["2027-06"]["occurrences"]
    assert camp["covered"] is True


def test_salary_still_due_carries_into_next_month(client, monkeypatch):
    from datetime import date

    from app import clock

    monkeypatch.setattr(clock, "today_madrid", lambda: date(2026, 10, 14))
    set_income(client, 280000, day=27)  # October's salary hasn't arrived yet
    view = client.get("/plan/upcoming?from=2026-10").json()
    assert view["months"][0]["unassigned_cents"] == 0
    november = view["months"][1]
    assert november["expected_income_cents"] == 280000
    # November's money = its own salary + October's still-expected one.
    assert november["unassigned_cents"] + november["flexible_funded_cents"] == 560000
    assert view["income_cents"] == 280000 * 12


def test_fourteen_pagas_counted_once_each_in_the_summary(client):
    set_income(client, 200000, day=27)
    set_income(client, 200000, name="Paga extra", pattern="some_months", months=[6, 12])
    summary = client.get("/plan/summary?from=2026-10").json()
    assert summary["income_known"] is True
    assert summary["income_cents"] == 2800000


def test_plan_income_endpoints_are_gone(client):
    assert client.get("/plan/income").status_code == 404
