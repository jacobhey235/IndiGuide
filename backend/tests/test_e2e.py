"""E2E tests: 15 user scenarios from registration to account deletion."""

import pytest
from httpx import AsyncClient


# ── 1. Создание нового пользователя ───────────────────────────────────────────

async def test_create_user(client: AsyncClient):
    r = await client.post(
        "/api/auth/register",
        json={"email": "new@test.com", "username": "newuser", "password": "password123"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@test.com"
    assert body["username"] == "newuser"
    assert "id" in body
    assert "hashed_password" not in body


# ── 2. Вход в аккаунт ─────────────────────────────────────────────────────────

async def test_login(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "login@test.com", "username": "loginuser", "password": "password123"},
    )
    r = await client.post(
        "/api/auth/login",
        json={"email": "login@test.com", "password": "password123"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


# ── 3. Смена пароля ───────────────────────────────────────────────────────────

async def test_change_password(client: AsyncClient, auth1: dict):
    r = await client.patch(
        "/api/auth/password",
        headers=auth1,
        json={"current_password": "password123", "new_password": "newpassword456"},
    )
    assert r.status_code == 200

    r = await client.post(
        "/api/auth/login",
        json={"email": "user1@test.com", "password": "password123"},
    )
    assert r.status_code == 401

    r = await client.post(
        "/api/auth/login",
        json={"email": "user1@test.com", "password": "newpassword456"},
    )
    assert r.status_code == 200


# ── 4. Генерация нового маршрута ──────────────────────────────────────────────

async def test_generate_route(client: AsyncClient, auth1: dict, mock_external):
    r = await client.post(
        "/api/routes/generate",
        headers=auth1,
        json={
            "start_lat": 55.755,
            "start_lon": 37.617,
            "distance_m": 2000,
            "num_pois": 2,
            "selected_categories": ["museums"],
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "draft"
    assert not body["is_saved"]
    assert not body["is_published"]
    assert len(body["waypoints"]) == 2
    assert body["total_distance_m"] == pytest.approx(1800.0)


# ── 5. Прохождение маршрута ───────────────────────────────────────────────────

async def test_walk_route(client: AsyncClient, auth1: dict, route: dict):
    rid = route["id"]
    wps = route["waypoints"]

    r = await client.post(f"/api/routes/{rid}/start", headers=auth1)
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    r = await client.get(
        f"/api/routes/{rid}/navigate",
        headers=auth1,
        params={"waypoint_id": wps[0]["id"], "current_lat": 55.755, "current_lon": 37.617},
    )
    assert r.status_code == 200
    assert "geometry" in r.json()

    for wp in wps:
        r = await client.post(
            f"/api/routes/{rid}/waypoints/{wp['id']}/visit",
            headers=auth1,
        )
        assert r.status_code == 200

    r = await client.post(f"/api/routes/{rid}/end", headers=auth1)
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


# ── 6. Оставление отзывов на точки ───────────────────────────────────────────

async def test_rate_waypoint(client: AsyncClient, auth1: dict, route: dict):
    rid = route["id"]
    wp = route["waypoints"][0]

    await client.post(f"/api/routes/{rid}/start", headers=auth1)
    await client.post(f"/api/routes/{rid}/waypoints/{wp['id']}/visit", headers=auth1)

    r = await client.post(
        f"/api/routes/{rid}/waypoints/{wp['id']}/rate",
        headers=auth1,
        json={"rating": 5},
    )
    assert r.status_code == 204


# ── 7. Сохранение маршрута в профиль ─────────────────────────────────────────

async def test_save_route(client: AsyncClient, auth1: dict, route: dict):
    rid = route["id"]
    r = await client.put(f"/api/routes/{rid}", headers=auth1, json={"is_saved": True})
    assert r.status_code == 200
    assert r.json()["is_saved"] is True

    r = await client.get("/api/routes/", headers=auth1)
    assert any(rt["id"] == rid for rt in r.json())


# ── 8. Публикация маршрута ────────────────────────────────────────────────────

async def test_publish_route(client: AsyncClient, auth1: dict, route: dict):
    rid = route["id"]
    await client.put(f"/api/routes/{rid}", headers=auth1, json={"is_saved": True})

    r = await client.put(f"/api/routes/{rid}", headers=auth1, json={"is_published": True})
    assert r.status_code == 200
    assert r.json()["is_published"] is True

    r = await client.get("/api/routes/explore", headers=auth1)
    assert any(rt["id"] == rid for rt in r.json())


# ── 9. Снятие маршрута с публикации ──────────────────────────────────────────

async def test_unpublish_route(client: AsyncClient, auth1: dict, route: dict):
    rid = route["id"]
    await client.put(f"/api/routes/{rid}", headers=auth1, json={"is_saved": True})
    await client.put(f"/api/routes/{rid}", headers=auth1, json={"is_published": True})

    r = await client.put(f"/api/routes/{rid}", headers=auth1, json={"is_published": False})
    assert r.status_code == 200
    assert r.json()["is_published"] is False

    r = await client.get("/api/routes/explore", headers=auth1)
    assert not any(rt["id"] == rid for rt in r.json())


# ── 10. Удаление маршрута ─────────────────────────────────────────────────────

async def test_delete_route(client: AsyncClient, auth1: dict, route: dict):
    rid = route["id"]
    r = await client.delete(f"/api/routes/{rid}", headers=auth1)
    assert r.status_code == 204

    r = await client.get("/api/routes/", headers=auth1)
    assert not any(rt["id"] == rid for rt in r.json())


# ── 11. Сохранение чужого маршрута в профиль ─────────────────────────────────

async def test_clone_foreign_route(
    client: AsyncClient,
    auth1: dict,
    auth2: dict,
    published_route: dict,
):
    r = await client.post(
        f"/api/routes/explore/{published_route['id']}/clone",
        headers=auth2,
    )
    assert r.status_code == 201
    clone = r.json()
    assert clone["id"] != published_route["id"]
    assert len(clone["waypoints"]) == len(published_route["waypoints"])

    r = await client.put(
        f"/api/routes/{clone['id']}",
        headers=auth2,
        json={"is_saved": True},
    )
    assert r.status_code == 200
    assert r.json()["is_saved"] is True


# ── 12. Редактирование чужого маршрута ───────────────────────────────────────

async def test_edit_foreign_route(
    client: AsyncClient,
    auth1: dict,
    auth2: dict,
    published_route: dict,
    mock_external,
):
    r = await client.post(
        f"/api/routes/explore/{published_route['id']}/clone",
        headers=auth2,
    )
    assert r.status_code == 201
    clone = r.json()
    assert len(clone["waypoints"]) == 3

    poi_to_remove = clone["waypoints"][0]["poi_xid"]
    r = await client.put(
        f"/api/routes/{clone['id']}",
        headers=auth2,
        json={"remove_poi_xids": [poi_to_remove]},
    )
    assert r.status_code == 200
    assert len(r.json()["waypoints"]) == 2


# ── 13. Прохождение сохранённого чужого маршрута ──────────────────────────────

async def test_walk_foreign_route(
    client: AsyncClient,
    auth1: dict,
    auth2: dict,
    published_route: dict,
    mock_external,
):
    r = await client.post(
        f"/api/routes/explore/{published_route['id']}/clone",
        headers=auth2,
    )
    clone = r.json()
    rid = clone["id"]
    wps = clone["waypoints"]

    await client.post(f"/api/routes/{rid}/start", headers=auth2)

    r = await client.get(
        f"/api/routes/{rid}/navigate",
        headers=auth2,
        params={"waypoint_id": wps[0]["id"], "current_lat": 55.755, "current_lon": 37.617},
    )
    assert r.status_code == 200

    for wp in wps:
        await client.post(f"/api/routes/{rid}/waypoints/{wp['id']}/visit", headers=auth2)

    r = await client.post(f"/api/routes/{rid}/end", headers=auth2)
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


# ── 14. Удаление сохранённого чужого маршрута из профиля ─────────────────────

async def test_delete_foreign_route(
    client: AsyncClient,
    auth1: dict,
    auth2: dict,
    published_route: dict,
):
    r = await client.post(
        f"/api/routes/explore/{published_route['id']}/clone",
        headers=auth2,
    )
    clone = r.json()

    r = await client.delete(f"/api/routes/{clone['id']}", headers=auth2)
    assert r.status_code == 204

    r = await client.get(f"/api/routes/explore/{published_route['id']}", headers=auth2)
    assert r.status_code == 200


# ── 15. Удаление созданного профиля пользователя ─────────────────────────────

async def test_delete_account(client: AsyncClient, auth1: dict):
    r = await client.delete("/api/auth/me", headers=auth1)
    assert r.status_code == 204

    r = await client.get("/api/auth/me", headers=auth1)
    assert r.status_code == 401
