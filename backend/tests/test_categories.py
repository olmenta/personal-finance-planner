"""Category and group management (spec: categories-api)."""

from app.models import Category, CategoryGroup, User


def group_ids(client):
    """name -> id over the seeded groups."""
    return {g["name"]: g["id"] for g in client.get("/categories").json()}


def find_category(client, name):
    for g in client.get("/categories").json():
        for c in g["categories"]:
            if c["name"] == name:
                return g, c
    return None, None


# ---- Categories ----------------------------------------------------------------


def test_create_category_in_group(client):
    gid = group_ids(client)["Estilo de vida"]
    response = client.post(
        "/categories", json={"name": "Mascotas", "icon": "circle", "group_id": gid}
    )
    assert response.status_code == 201
    group, cat = find_category(client, "Mascotas")
    assert group["id"] == gid
    assert cat["archived"] is False


def test_rename_move_and_reicon(client, category_ids):
    target_group = group_ids(client)["Vivienda"]
    cat_id = category_ids["Ocio"]
    response = client.patch(
        f"/categories/{cat_id}",
        json={"name": "Ocio y cultura", "group_id": target_group, "icon": "ticket"},
    )
    assert response.status_code == 200
    group, cat = find_category(client, "Ocio y cultura")
    assert group["id"] == target_group
    assert cat["icon"] == "ticket"
    assert cat["id"] == cat_id  # same row, transactions keep pointing at it


def test_archive_keeps_history_and_unarchive_restores(client, category_ids):
    cat_id = category_ids["Restaurantes"]
    client.post(
        "/transactions",
        json={"amount_cents": 1500, "category_id": cat_id, "date": "2026-06-03"},
    )
    budget_before = client.get("/budget/2026-06").json()

    assert client.patch(f"/categories/{cat_id}", json={"archived": True}).status_code == 200
    _, cat = find_category(client, "Restaurantes")
    assert cat["archived"] is True
    # History intact: the transaction still lists, budget month unchanged.
    rows = client.get("/transactions", params={"month": "2026-06"}).json()
    assert any(r["category_id"] == cat_id for r in rows)
    assert client.get("/budget/2026-06").json() == budget_before

    assert client.patch(f"/categories/{cat_id}", json={"archived": False}).status_code == 200
    _, cat = find_category(client, "Restaurantes")
    assert cat["archived"] is False


def test_duplicate_name_same_group_409(client, category_ids):
    group, _ = find_category(client, "Supermercado")
    response = client.post(
        "/categories", json={"name": "supermercado", "group_id": group["id"]}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "category_exists"


def test_same_name_other_group_allowed(client):
    gids = group_ids(client)
    assert (
        client.post(
            "/categories", json={"name": "Seguro", "group_id": gids["Vivienda"]}
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/categories", json={"name": "Seguro", "group_id": gids["Transporte"]}
        ).status_code
        == 201
    )


def test_rename_collision_409(client, category_ids):
    group, _ = find_category(client, "Supermercado")
    other = client.post(
        "/categories", json={"name": "Carnicería", "group_id": group["id"]}
    ).json()
    response = client.patch(f"/categories/{other['id']}", json={"name": "Supermercado"})
    assert response.status_code == 409


def test_unknown_and_foreign_ids_404(client, db):
    assert client.patch("/categories/nope", json={"name": "x"}).status_code == 404

    other = User(email="other2@example.com")
    db.add(other)
    db.flush()
    foreign_group = CategoryGroup(user_id=other.id, name="Ajeno")
    db.add(foreign_group)
    db.flush()
    foreign_cat = Category(user_id=other.id, group_id=foreign_group.id, name="Ajena")
    db.add(foreign_cat)
    db.flush()

    assert client.patch(f"/categories/{foreign_cat.id}", json={"name": "x"}).status_code == 404
    assert (
        client.post("/categories", json={"name": "x", "group_id": foreign_group.id}).status_code
        == 404
    )
    assert client.delete(f"/categories/groups/{foreign_group.id}").status_code == 404


# ---- Groups --------------------------------------------------------------------


def test_group_created_at_end(client):
    before = client.get("/categories").json()
    response = client.post("/categories/groups", json={"name": "Coche"})
    assert response.status_code == 201
    after = client.get("/categories").json()
    assert after[-1]["name"] == "Coche"
    assert after[-1]["sort_order"] > max(g["sort_order"] for g in before)


def test_group_rename_and_reorder(client):
    group = client.post("/categories/groups", json={"name": "Temporal"}).json()
    response = client.patch(
        f"/categories/groups/{group['id']}", json={"name": "Viajes", "sort_order": 0}
    )
    assert response.status_code == 200
    tree = client.get("/categories").json()
    assert tree[0]["name"] == "Viajes"


def test_duplicate_group_name_409(client):
    response = client.post("/categories/groups", json={"name": "vivienda"})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "group_exists"


def test_delete_empty_group_204(client):
    group = client.post("/categories/groups", json={"name": "Vacía"}).json()
    assert client.delete(f"/categories/groups/{group['id']}").status_code == 204
    assert "Vacía" not in group_ids(client)


def test_delete_non_empty_group_409_even_archived(client):
    group = client.post("/categories/groups", json={"name": "Casi vacía"}).json()
    cat = client.post(
        "/categories", json={"name": "Único", "group_id": group["id"]}
    ).json()
    client.patch(f"/categories/{cat['id']}", json={"archived": True})

    response = client.delete(f"/categories/groups/{group['id']}")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "group_not_empty"
