"""Import batch API tests — no live Anthropic calls (no key in test env →
the suggestion service fails open to all-null; explicit mock where a
suggestion is asserted)."""

from unittest.mock import patch

from fixtures import bbva_xlsx, sabadell_xls

from app.services.category_suggestions import EMPTY, Suggestion


def upload(client, blob: bytes, bank: str, filename: str = "export.xlsx"):
    return client.post(
        "/imports",
        files={"file": (filename, blob, "application/octet-stream")},
        data={"bank": bank},
    )


def test_upload_stages_rows_without_touching_budget(client):
    summary_before = client.get("/summary/2026-06").json()
    response = upload(client, bbva_xlsx(), "bbva")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "staged"
    assert body["source"] == "import_bbva"
    assert body["row_count"] == 6
    assert body["skipped_duplicates"] == 0
    assert len(body["transactions"]) == 6
    assert all(t["status"] == "staged" for t in body["transactions"])
    # Staged rows are invisible to the normal reads until confirmation.
    assert client.get("/transactions", params={"month": "2026-06"}).json() == []
    assert client.get("/summary/2026-06").json() == summary_before


def test_suggestions_attached_to_staged_rows(client, category_ids):
    target = category_ids["Supermercado"]

    def fake_suggest(categories, rows, history=None, usage=None):
        return {
            i: (
                Suggestion(target, "Supermercado Genérico", "high")
                if "Supermercado" in r.description
                else EMPTY
            )
            for i, r in enumerate(rows)
        }

    with patch("app.services.import_batch.category_suggestions.suggest", fake_suggest):
        body = upload(client, bbva_xlsx(), "bbva").json()
    suggested = [t for t in body["transactions"] if t["category_id"] == target]
    assert len(suggested) == 1


def test_unrecognizable_file_422(client):
    response = upload(client, b"definitely not excel", "bbva")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "file_format_unrecognized"


def test_wrong_bank_choice_422(client):
    response = upload(client, sabadell_xls(), "bbva")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "file_format_unrecognized"


def test_oversize_file_413(client):
    blob = b"0" * (2 * 1024 * 1024 + 1)
    assert upload(client, blob, "bbva").status_code == 413


def test_confirm_with_override_updates_budget_and_list(client, category_ids):
    body = upload(client, bbva_xlsx(), "bbva").json()
    coffee = next(t for t in body["transactions"] if "Cafetería" in t["description"])
    response = client.post(
        f"/imports/{body['id']}/confirm",
        json={"overrides": {coffee["id"]: category_ids["Restaurantes"]}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"

    listed = client.get("/transactions", params={"month": "2026-06"}).json()
    assert len(listed) == 6
    overridden = next(t for t in listed if t["id"] == coffee["id"])
    assert overridden["category_id"] == category_ids["Restaurantes"]
    assert all(t["status"] == "confirmed" for t in listed)

    summary = client.get("/summary/2026-06").json()
    assert summary["expense_cents"] > 0


def test_positive_row_categorized_on_confirm_is_refund(client, category_ids):
    """Spec scenario: imported inflow + category override = refund."""
    body = upload(client, bbva_xlsx(), "bbva").json()
    nomina = next(t for t in body["transactions"] if t["amount_cents"] > 0)
    super_id = category_ids["Supermercado"]
    client.post(
        f"/imports/{body['id']}/confirm",
        json={"overrides": {nomina["id"]: super_id}},
    )
    summary = client.get("/summary/2026-06").json()
    assert summary["income_cents"] == 0  # the inflow became category activity
    budget = client.get("/budget/2026-06").json()
    spent = {
        c["name"]: c["spent_cents"] for g in budget["groups"] for c in g["categories"]
    }
    assert spent["Supermercado"] == -nomina["amount_cents"]


def test_positive_row_uncategorized_confirms_as_income(client):
    body = upload(client, bbva_xlsx(), "bbva").json()
    nomina = next(t for t in body["transactions"] if t["amount_cents"] > 0)
    client.post(f"/imports/{body['id']}/confirm", json={"overrides": {}})
    summary = client.get("/summary/2026-06").json()
    assert summary["income_cents"] == nomina["amount_cents"]


def test_reimport_is_idempotent(client):
    first = upload(client, bbva_xlsx(), "bbva").json()
    client.post(f"/imports/{first['id']}/confirm", json={"overrides": {}})

    second = upload(client, bbva_xlsx(), "bbva").json()
    assert second["row_count"] == 0
    assert second["skipped_duplicates"] == 6


def test_in_file_duplicates_collapse(client):
    from fixtures import SABADELL_ROWS

    rows = SABADELL_ROWS + [SABADELL_ROWS[0]]  # byte-identical row incl. balance
    body = upload(client, sabadell_xls(rows), "sabadell", "export.xls").json()
    assert body["row_count"] == 4
    assert body["skipped_duplicates"] == 1


def test_discard_deletes_rows_and_allows_reupload(client):
    first = upload(client, sabadell_xls(), "sabadell", "export.xls").json()
    assert client.delete(f"/imports/{first['id']}").status_code == 204
    assert client.get(f"/imports/{first['id']}").json()["status"] == "discarded"
    assert client.get("/transactions").json() == []

    again = upload(client, sabadell_xls(), "sabadell", "export.xls").json()
    assert again["row_count"] == 4
    assert again["skipped_duplicates"] == 0


def test_double_confirm_409(client):
    body = upload(client, bbva_xlsx(), "bbva").json()
    assert client.post(f"/imports/{body['id']}/confirm", json={"overrides": {}}).status_code == 200
    second = client.post(f"/imports/{body['id']}/confirm", json={"overrides": {}})
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "batch_not_staged"


def test_custom_csv_upload(client):
    csv_blob = (
        "date,amount,description,category\n"
        "15/05/2026,-12.30,Mercadona semanal,Supermercado\n"
        "01/05/2026,1850.00,Nómina mayo,\n"
    ).encode("utf-8")
    body = upload(client, csv_blob, "custom", "my-bank.csv").json()
    assert body["source"] == "import_custom"
    assert body["row_count"] == 2


def test_unknown_batch_404(client):
    assert client.get("/imports/nope").status_code == 404


def test_second_upload_409_while_pending(client):
    first = upload(client, bbva_xlsx(), "bbva").json()
    second = upload(client, sabadell_xls(), "sabadell", "export.xls")
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["code"] == "import_pending"
    assert detail["batch_id"] == first["id"]
    # No second batch staged — the pending view is still the first one.
    assert client.get("/imports/pending").json()["id"] == first["id"]


def test_upload_allowed_after_discard_and_after_confirm(client):
    first = upload(client, bbva_xlsx(), "bbva").json()
    assert client.delete(f"/imports/{first['id']}").status_code == 204
    second = upload(client, bbva_xlsx(), "bbva")
    assert second.status_code == 201

    client.post(f"/imports/{second.json()['id']}/confirm", json={"overrides": {}})
    third = upload(client, sabadell_xls(), "sabadell", "export.xls")
    assert third.status_code == 201


def test_pending_fetch_returns_staged_rows(client):
    body = upload(client, bbva_xlsx(), "bbva").json()
    pending = client.get("/imports/pending")
    assert pending.status_code == 200
    view = pending.json()
    assert view["id"] == body["id"]
    assert view["status"] == "staged"
    assert view["filename"] == "export.xlsx"
    assert len(view["transactions"]) == 6
    assert all(t["status"] == "staged" for t in view["transactions"])


def test_pending_404_when_none(client):
    response = client.get("/imports/pending")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "no_pending_import"

    # Confirming the only batch clears the invariant — pending 404s again.
    body = upload(client, bbva_xlsx(), "bbva").json()
    client.post(f"/imports/{body['id']}/confirm", json={"overrides": {}})
    assert client.get("/imports/pending").status_code == 404


def test_staged_rows_carry_proposed_payee(client, db, user):
    def fake_suggest(categories, rows, history=None, usage=None):
        return {i: Suggestion(None, "Cafetería Central", "medium") for i in range(len(rows))}

    with patch("app.services.import_batch.category_suggestions.suggest", fake_suggest):
        body = upload(client, bbva_xlsx(), "bbva").json()
    assert all(t["payee_name"] == "Cafetería Central" for t in body["transactions"])
    # One payee entity reused across the batch, born at staging.
    from app.models import Payee

    assert db.query(Payee).filter_by(user_id=user.id).count() == 1


def test_discard_removes_orphan_payees(client, db, user, category_ids):
    # A payee with prior history must survive the discard; a batch-only one must not.
    client.post(
        "/transactions",
        json={"amount_cents": 100, "category_id": category_ids["Restaurantes"], "payee": "Cafetería Central"},
    )

    def fake_suggest(categories, rows, history=None, usage=None):
        names = ["Cafetería Central", "Suscripción Música"]
        return {i: Suggestion(None, names[i % 2], "low") for i in range(len(rows))}

    with patch("app.services.import_batch.category_suggestions.suggest", fake_suggest):
        body = upload(client, bbva_xlsx(), "bbva").json()

    assert client.delete(f"/imports/{body['id']}").status_code == 204
    from app.models import Payee

    names = {p.name for p in db.query(Payee).filter_by(user_id=user.id)}
    assert names == {"Cafetería Central"}  # batch-only payee cleaned up


def test_income_rows_stage_uncategorized(client, category_ids):
    # Even if the model proposes a category for an income row, staging nulls
    # it — income lands in "ready to assign", not in a budget envelope.
    target = category_ids["Supermercado"]

    def fake_suggest(categories, rows, history=None, usage=None):
        return {i: Suggestion(target, "Empresa ejemplo", "high") for i in range(len(rows))}

    with patch("app.services.import_batch.category_suggestions.suggest", fake_suggest):
        body = upload(client, bbva_xlsx(), "bbva").json()
    income = next(t for t in body["transactions"] if t["amount_cents"] > 0)
    assert income["category_id"] is None
    assert income["payee_name"] == "Empresa ejemplo"
    expenses = [t for t in body["transactions"] if t["amount_cents"] < 0]
    assert expenses and all(t["category_id"] == target for t in expenses)


def test_confirm_payee_override_replaces_and_cleans(client):
    def fake_suggest(categories, rows, history=None, usage=None):
        return {
            i: (
                Suggestion(None, "Cafetería AI", "medium")
                if "Cafetería" in r.description
                else EMPTY
            )
            for i, r in enumerate(rows)
        }

    with patch("app.services.import_batch.category_suggestions.suggest", fake_suggest):
        body = upload(client, bbva_xlsx(), "bbva").json()
    coffees = [t for t in body["transactions"] if "Cafetería" in t["description"]]
    assert coffees and all(t["payee_name"] == "Cafetería AI" for t in coffees)

    response = client.post(
        f"/imports/{body['id']}/confirm",
        json={
            "overrides": {},
            "payee_overrides": {t["id"]: "Café Central" for t in coffees},
        },
    )
    assert response.status_code == 200

    listed = client.get("/transactions", params={"month": "2026-06"}).json()
    renamed = [t for t in listed if t["id"] in {c["id"] for c in coffees}]
    assert renamed and all(t["payee_name"] == "Café Central" for t in renamed)
    # The replaced AI proposal must not linger in autocomplete.
    names = [p["name"] for p in client.get("/payees").json()]
    assert "Café Central" in names
    assert "Cafetería AI" not in names


def test_confirm_note_override_replaces_description(client):
    body = upload(client, bbva_xlsx(), "bbva").json()
    noted, cleared = body["transactions"][0], body["transactions"][1]

    response = client.post(
        f"/imports/{body['id']}/confirm",
        json={"note_overrides": {noted["id"]: "  Cena con Ana  ", cleared["id"]: ""}},
    )
    assert response.status_code == 200

    listed = {t["id"]: t for t in client.get("/transactions", params={"month": "2026-06"}).json()}
    assert listed[noted["id"]]["description"] == "Cena con Ana"
    assert listed[cleared["id"]]["description"] is None
    # The dedupe hash was fixed at staging: re-importing still skips every row.
    again = upload(client, bbva_xlsx(), "bbva").json()
    assert again["row_count"] == 0
