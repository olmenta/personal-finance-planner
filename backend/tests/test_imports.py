"""Import batch API tests — no live Anthropic calls (no key in test env →
the suggestion service fails open to all-null; explicit mock where a
suggestion is asserted)."""

from unittest.mock import patch

from fixtures import bbva_xlsx, sabadell_xls


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

    def fake_suggest(categories, rows):
        return {i: (target if "Supermercado" in r.description else None) for i, r in enumerate(rows)}

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
