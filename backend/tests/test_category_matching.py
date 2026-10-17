"""Similar categories and groups (openspec change coach-budget-setup,
spec category-matching)."""

from app.services import category_matching as matching


def names(matches) -> list[str]:
    return [m.name for m in matches]


def test_case_and_accents(db, user):
    [m] = matching.similar_categories(db, user, "transporte publico")
    assert (m.name, m.reason) == ("Transporte público", "same_name")


def test_plural_or_typo(db, user):
    assert "Suscripciones" in names(matching.similar_categories(db, user, "Suscripcion"))
    assert "Supermercado" in names(matching.similar_categories(db, user, "Supermercadp"))


def test_shared_word(db, user, client):
    group = client.get("/categories").json()[0]["id"]
    client.post("/categories", json={"name": "Seguro hogar", "group_id": group})
    match = next(m for m in matching.similar_categories(db, user, "Seguro del coche") if m.name == "Seguro hogar")
    assert match.reason == "shared_word"


def test_unrelated_names(db, user):
    assert matching.similar_categories(db, user, "Veterinario") == []


def test_strongest_first_and_capped(db, user):
    matches = matching.similar_categories(db, user, "Transporte")
    assert matches[0].name == "Transporte público" and len(matches) <= matching.MAX_MATCHES


def test_card_payment_categories_are_not_offered(db, user, client):
    client.post("/accounts", json={"name": "Visa", "type": "credit", "opening_balance_cents": 0})
    assert all("Visa" not in m.name for m in matching.similar_categories(db, user, "Pago Visa"))


def test_suggested_group(db, user, client):
    assert matching.suggest_group(db, user, "Súper").name == "Comida"
    # Shared words with a group's categories, without a similar category.
    group = client.post("/categories/groups", json={"name": "Coche"}).json()["id"]
    client.post("/categories", json={"name": "Taller mecánico", "group_id": group})
    assert matching.suggest_group(db, user, "taller", []).name == "Coche"
    # Nothing in common: the last group, never a system group.
    assert matching.suggest_group(db, user, "Veterinario").name == "Coche"


def test_similar_groups(db, user):
    [m] = matching.similar_groups(db, user, "comidas")
    assert m.name == "Comida"


def test_endpoint(client):
    body = client.get("/categories/similar", params={"name": "super"}).json()
    assert body["matches"][0] == {
        "id": body["matches"][0]["id"], "name": "Supermercado", "reason": "contains",
        "group_id": body["matches"][0]["group_id"], "group_name": "Comida",
    }
    assert body["suggested_group"]["name"] == "Comida"
    groups = client.get("/categories/similar", params={"name": "Comida", "kind": "group"}).json()
    assert groups["matches"][0]["reason"] == "same_name" and groups["suggested_group"] is None
    assert client.get("/categories/similar", params={"name": "  "}).status_code == 422
