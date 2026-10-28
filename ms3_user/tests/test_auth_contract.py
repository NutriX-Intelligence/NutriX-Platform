"""
Integration contract tests for the stitched MS3: token shape, authentication on every route family,
ownership (user A can never touch user B), legacy vs /api/v1 path parity, and the new dashboard routes.
"""
import jwt
import pytest
from fastapi.testclient import TestClient

from ms3_user.main import app
from ms3_user.services.auth_service import ALGORITHM, SECRET_KEY
from ms3_user.tests.conftest import auth_headers

client = TestClient(app)


def _register(email: str, name: str = "Test User") -> dict:
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "secret123", "name": name})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture(scope="module")
def alice():
    return _register("alice@example.com", "Alice")


@pytest.fixture(scope="module")
def bob():
    return _register("bob@example.com", "Bob")


def _bearer(account: dict) -> dict:
    return {"Authorization": f"Bearer {account['access_token']}"}


# ── token contract with the gateway ──────────────────────────────────────────
def test_token_subject_is_the_numeric_user_id(alice):
    payload = jwt.decode(alice["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == str(alice["user"]["id"])
    assert payload["email"] == "alice@example.com"


def test_login_returns_a_usable_token(alice):
    r = client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "secret123"})
    assert r.status_code == 200
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "alice@example.com"


def test_legacy_email_subject_token_is_rejected(alice):
    old_style = jwt.encode({"sub": "alice@example.com", "id": alice["user"]["id"]}, SECRET_KEY, algorithm=ALGORITHM)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_style}"})
    assert r.status_code == 401


def test_forwarded_user_id_must_match_the_token(alice, bob):
    headers = {**_bearer(alice), "X-User-ID": str(bob["user"]["id"])}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    headers["X-User-ID"] = str(alice["user"]["id"])
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200


# ── authentication on every route family ─────────────────────────────────────
@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/user/daily-summary"),
    ("GET", "/api/v1/user/history"),
    ("GET", "/api/v1/user/targets"),
    ("GET", "/api/v1/meal-logs/today/1"),
    ("GET", "/api/v1/water-logs/today/1"),
    ("GET", "/api/v1/analytics/1"),
    ("GET", "/api/v1/recipes/top"),
    ("GET", "/api/v1/fast-food/chains"),
    ("GET", "/api/v1/barcode/8901719117972"),
    ("POST", "/api/v1/meal-logs"),
    ("POST", "/api/v1/ai/coach"),
    # the paths the existing app calls
    ("GET", "/api/meal-logs/today/1"),
    ("GET", "/recipes/top"),
    ("GET", "/users/1/targets"),
    ("POST", "/calculate-profile"),
])
def test_routes_require_a_token(method, path):
    assert client.request(method, path).status_code == 401, path


@pytest.mark.parametrize("path", ["/users/alice@example.com", "/recipes/train-ml", "/api/health"])
def test_removed_routes_are_gone(path, alice):
    assert client.request("GET", path, headers=_bearer(alice)).status_code in (404, 405)


def test_health_is_public():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["service"] == "ms3_user"


# ── ownership ────────────────────────────────────────────────────────────────
def test_path_user_id_must_be_the_callers(alice, bob):
    bob_id = bob["user"]["id"]
    for path in (f"/api/v1/water-logs/today/{bob_id}", f"/api/water-logs/today/{bob_id}",
                 f"/api/v1/meal-logs/today/{bob_id}", f"/users/{bob_id}/targets"):
        assert client.get(path, headers=_bearer(alice)).status_code == 403, path


def test_body_user_id_must_be_the_callers(alice, bob):
    body = {"user_id": bob["user"]["id"], "food_name": "Stolen apple", "calories": 52}
    assert client.post("/api/v1/meal-logs", json=body, headers=_bearer(alice)).status_code == 403


def test_calculate_profile_cannot_edit_someone_elses_account(alice):
    body = {"email": "bob@example.com", "name": "Bob", "age": 30, "gender": "male", "height": 175,
            "weight": 80, "activity_level": "sedentary", "goal": "maintenance"}
    assert client.post("/calculate-profile", json=body, headers=_bearer(alice)).status_code == 403
    assert client.post("/api/v1/user/profile", json=body, headers=_bearer(alice)).status_code == 403


def test_cannot_delete_another_users_log(alice, bob):
    created = client.post(
        "/api/v1/meal-logs",
        json={"user_id": bob["user"]["id"], "food_name": "Bob's lunch", "calories": 500},
        headers=_bearer(bob),
    )
    assert created.status_code == 201
    log_id = created.json()["id"]
    assert client.delete(f"/api/v1/meal-logs/{log_id}", headers=_bearer(alice)).status_code == 404
    assert client.delete(f"/api/meal-logs/{log_id}", headers=_bearer(bob)).status_code == 200


# ── legacy vs canonical parity ───────────────────────────────────────────────
def test_legacy_and_canonical_paths_return_the_same_thing(alice):
    uid = alice["user"]["id"]
    new = client.get(f"/api/v1/water-logs/today/{uid}", headers=_bearer(alice))
    old = client.get(f"/api/water-logs/today/{uid}", headers=_bearer(alice))
    assert new.status_code == old.status_code == 200
    assert new.json() == old.json()


def test_legacy_routes_are_hidden_from_openapi():
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/meal-logs" in paths
    assert "/api/meal-logs" not in paths


# ── dashboard routes ─────────────────────────────────────────────────────────
def test_daily_summary_tracks_logs_and_deletes(alice):
    h = _bearer(alice)
    before = client.get("/api/v1/user/daily-summary", headers=h)
    assert before.status_code == 200
    assert before.json()["consumed"]["calories"] == 0 and before.json()["meals_count"] == 0

    a = client.post("/api/v1/meal-logs", json={"user_id": alice["user"]["id"], "food_name": "Apple",
                                               "calories": 95, "protein": 0.5, "carbs": 25, "fat": 0.3,
                                               "weight_g": 180}, headers=h).json()
    client.post("/api/v1/meal-logs", json={"user_id": alice["user"]["id"], "food_name": "Roti", "calories": 120}, headers=h)

    s = client.get("/api/v1/user/daily-summary", headers=h).json()
    assert s["consumed"]["calories"] == 215 and s["meals_count"] == 2 and s["latest_item"] == "Roti"
    assert s["targets"]["calories"] > 0 and 0 < s["percent"]["calories"] < 100
    assert abs(s["remaining"]["calories"] - (s["targets"]["calories"] - 215)) <= 0.11  # targets are rounded to 0.1

    assert client.delete(f"/api/v1/meal-logs/{a['id']}", headers=h).status_code == 200
    after = client.get("/api/v1/user/daily-summary", headers=h).json()
    assert after["consumed"]["calories"] == 120 and after["meals_count"] == 1


def test_history_is_paginated_and_scoped_to_the_caller(alice, bob):
    h = _bearer(alice)
    r = client.get("/api/v1/user/history?page=1&page_size=1", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["page_size"] == 1 and len(body["items"]) <= 1
    assert all("Bob" not in i["food_name"] for i in body["items"])
    assert client.get("/api/v1/user/history?from=not-a-date", headers=h).status_code == 400


def test_manual_logs_record_weight_and_source(alice):
    h = _bearer(alice)
    client.post("/api/v1/meal-logs", json={"user_id": alice["user"]["id"], "food_name": "Pizza slice",
                                           "calories": 285, "weight_g": 107, "source": "fast_food"}, headers=h)
    items = client.get("/api/v1/user/history", headers=h).json()["items"]
    pizza = next(i for i in items if i["food_name"] == "Pizza slice")
    assert pizza["weight_g"] == 107 and pizza["source"] == "fast_food"
    assert next(i for i in items if i["food_name"] == "Roti")["source"] == "manual"


def test_helper_headers_work():
    assert "Bearer " in auth_headers(5)["Authorization"]
