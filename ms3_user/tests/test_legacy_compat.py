"""
Compatibility suite for the existing app / web dashboard.

Every endpoint the dashboard calls must answer *identically* on its legacy path and on its canonical /api/v1 path:
same status code and (for stateless reads) the same body. State-changing calls are compared on status, and the
create-then-delete flows run as separate tests so each spelling gets its own record.
"""
import io

import pytest
from fastapi.testclient import TestClient

from ms3_user.main import app
from ms3_user.routing import canonical_path

client = TestClient(app)

PASSWORD = "secret123"
EMAIL = "compat@example.com"


@pytest.fixture(scope="module")
def account():
    r = client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "name": "Compat User"})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"uid": body["user"]["id"], "headers": {"Authorization": f"Bearer {body['access_token']}"}}


def _route_exists(resp) -> bool:
    """A 404 produced by the framework (no such route) is not the same as the app answering 404."""
    return not (resp.status_code == 404 and resp.json().get("detail") == "Not Found") and resp.status_code != 405


def _both(account, method, legacy_template, make_kwargs=None, compare_json=False):
    path = legacy_template.format(uid=account["uid"], email=EMAIL)
    legacy_url, new_url = path, canonical_path(legacy_template).format(uid=account["uid"], email=EMAIL)
    assert legacy_url != new_url, f"{legacy_template} has no distinct canonical path"
    out = []
    for url in (legacy_url, new_url):
        kwargs = make_kwargs(account) if make_kwargs else {}
        out.append(client.request(method, url, headers=account["headers"], **kwargs))
    legacy, new = out
    assert _route_exists(legacy), f"legacy route missing: {method} {legacy_url} -> {legacy.status_code}"
    assert _route_exists(new), f"canonical route missing: {method} {new_url} -> {new.status_code}"
    assert legacy.status_code == new.status_code, (
        f"{method} {legacy_url}: legacy {legacy.status_code} {legacy.text[:150]} vs canonical {new.status_code} {new.text[:150]}")
    assert legacy.status_code not in (401, 403), f"{method} {legacy_url} rejected the caller's own token"
    assert legacy.status_code < 500, f"{method} {legacy_url} -> {legacy.status_code}: {legacy.text[:200]}"
    if compare_json and legacy.status_code == 200:
        assert legacy.json() == new.json()
    return legacy, new


def _profile(a):
    return {"json": {"email": EMAIL, "name": "Compat User", "age": 30, "gender": "male", "height": 175,
                     "weight": 72, "activity_level": "sedentary", "goal": "maintenance",
                     "preferences": [{"preference_type": "diet_type", "value": "Vegetarian"}]}}


def _jpeg(a=None):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), (250, 250, 250)).save(buf, format="JPEG")
    return buf.getvalue()


# (method, legacy path template, kwargs factory, compare bodies?)  — the 33 endpoints the dashboard calls
STATELESS_AND_IDEMPOTENT = [
    ("GET", "/api/auth/me", None, True),
    ("POST", "/calculate-profile", _profile, False),
    ("POST", "/recommend-foods", lambda a: {"json": {"user_id": a["uid"], "limit": 5}}, True),
    ("GET", "/users/{uid}/targets", None, True),
    ("GET", "/users/{uid}/weight-history", None, True),
    ("GET", "/users/{uid}/meal-plans", None, True),
    ("POST", "/track-weight", lambda a: {"json": {"user_id": a["uid"], "weight": 71.5}}, False),
    ("POST", "/generate-meal-plan", lambda a: {"json": {"user_id": a["uid"], "preference": "balanced", "tolerance": 0.2}}, False),
    ("POST", "/recipes/recommend", lambda a: {"json": {"ingredients": ["paneer", "tomato"], "top_n": 3}}, False),
    ("POST", "/recipes/filter", lambda a: {"json": {"max_results": 5}}, True),
    ("GET", "/recipes/top?limit=3", None, True),
    ("GET", "/recipes/search?q=dal&max_results=3", None, True),
    ("GET", "/recipes/NOPE-0000", None, True),
    ("GET", "/api/meal-logs/today/{uid}", None, True),
    ("GET", "/api/water-logs/today/{uid}", None, True),
    ("GET", "/api/analytics/{uid}", None, False),
    ("GET", "/api/analytics/{uid}/history?metric_name=weight", None, False),
    ("GET", "/api/homely/builder-defaults", None, True),
    ("POST", "/api/homely-meals/calculate",
     lambda a: {"json": {"ingredients": [{"ingredient_name": "paneer", "amount": 100, "unit": "g"}]}}, True),
    ("GET", "/api/homely-meals/user/{uid}", None, True),
    ("GET", "/api/homely-meals/search?q=paneer", None, True),
    ("GET", "/api/homely-meals/pending", None, True),
    ("GET", "/api/fast-food/chains", None, True),
    ("GET", "/api/fast-food/grouped?brand=dominos", None, True),
    # curated tier-1 code (no network). Not body-compared: the first lookup fills the cache, so the second
    # call truthfully reports `source: cache` instead of `curated_fmcg`.
    ("GET", "/api/barcode/8901058852712", None, False),
    ("POST", "/api/barcode/scan-image", lambda a: {"files": {"file": ("p.jpg", _jpeg(), "image/jpeg")}}, False),
    ("POST", "/api/ocr", lambda a: {"files": {"file": ("l.jpg", _jpeg(), "image/jpeg")}}, False),
    ("POST", "/api/barcode/manual", lambda a: {"json": {
        "barcode": "9990001112223", "product_name": "Compat Biscuit", "energy_kcal": 480, "protein_g": 6,
        "carb_g": 70, "fat_g": 19}}, False),
    ("POST", "/api/classify", lambda a: {"json": {"ingredients": ["paneer", "onion", "garlic"]}}, True),
    ("POST", "/api/classify/substitutions", lambda a: {"json": {"ingredients": ["onion", "garlic"], "target_diet": "jain"}}, True),
]


@pytest.mark.parametrize("method,path,make_kwargs,compare_json", STATELESS_AND_IDEMPOTENT,
                         ids=[f"{m} {p}" for m, p, _, _ in STATELESS_AND_IDEMPOTENT])
def test_endpoint_is_identical_on_legacy_and_canonical_paths(account, method, path, make_kwargs, compare_json):
    _both(account, method, path, make_kwargs, compare_json)


# ── auth endpoints (public) ──────────────────────────────────────────────────
def test_login_and_google_on_both_paths(account):
    for url in ("/api/auth/login", "/api/v1/auth/login"):
        r = client.post(url, json={"email": EMAIL, "password": PASSWORD})
        assert r.status_code == 200 and r.json()["token_type"] == "bearer" and r.json()["user"]["email"] == EMAIL
    for url in ("/api/auth/google", "/api/v1/auth/google"):
        r = client.post(url, json={"id_token": "mock-google-compat2@example.com"})
        assert r.status_code == 200 and "access_token" in r.json(), r.text


def test_register_on_both_paths():
    for i, url in enumerate(("/api/auth/register", "/api/v1/auth/register")):
        r = client.post(url, json={"email": f"reg{i}@example.com", "password": PASSWORD, "name": f"Reg {i}"})
        assert r.status_code == 201 and r.json()["is_new_user"] is True
        assert {"access_token", "token_type", "user"} <= set(r.json())


# ── create-then-delete flows: each spelling gets its own record ──────────────
@pytest.mark.parametrize("kind,create_path,create_body,delete_path", [
    ("meal", "/api/meal-logs", lambda uid: {"user_id": uid, "food_name": "Compat apple", "calories": 52}, "/api/meal-logs/{id}"),
    ("water", "/api/water-logs", lambda uid: {"user_id": uid, "amount_ml": 250}, "/api/water-logs/{id}"),
])
def test_create_and_delete_flows(account, kind, create_path, create_body, delete_path):
    for create_url, delete_template in (
        (create_path, delete_path),
        (canonical_path(create_path), canonical_path(delete_path)),
    ):
        created = client.post(create_url, json=create_body(account["uid"]), headers=account["headers"])
        assert created.status_code == 201, created.text
        log_id = created.json()["id"]
        deleted = client.delete(delete_template.format(id=log_id), headers=account["headers"])
        assert deleted.status_code == 200 and deleted.json()["status"] == "success"
        again = client.delete(delete_template.format(id=log_id), headers=account["headers"])
        assert again.status_code == 404


def test_weight_log_create_and_delete_flow(account):
    for track_url, delete_template in (("/track-weight", "/api/weight-logs/{id}"),
                                       (canonical_path("/track-weight"), canonical_path("/api/weight-logs/{id}"))):
        r = client.post(track_url, json={"user_id": account["uid"], "weight": 70.0}, headers=account["headers"])
        assert r.status_code == 200, r.text
        history = client.get(f"/users/{account['uid']}/weight-history", headers=account["headers"]).json()
        entry_id = history[-1]["id"] if history and "id" in history[-1] else None
        if entry_id is not None:
            assert client.delete(delete_template.format(id=entry_id), headers=account["headers"]).status_code == 200


def test_homely_meal_create_review_flow(account):
    body = {"name": "Compat Dal", "creator_id": account["uid"],
            "ingredients": [{"ingredient_name": "dal", "amount": 100, "unit": "g"}]}
    ids = []
    for url in ("/api/homely-meals/create", canonical_path("/api/homely-meals/create")):
        r = client.post(url, json=body, headers=account["headers"])
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])
    for meal_id, url in zip(ids, ("/api/homely-meals/{id}", canonical_path("/api/homely-meals/{id}"))):
        assert client.get(url.format(id=meal_id), headers=account["headers"]).status_code == 200
    review = {"reviewer_id": account["uid"], "rating": 5, "comment": "good"}
    for meal_id, url in zip(ids, ("/api/homely-meals/{id}/review", canonical_path("/api/homely-meals/{id}/review"))):
        assert client.post(url.format(id=meal_id), json=review, headers=account["headers"]).status_code == 200


def test_settings_and_search_history_on_both_paths(account):
    for prefix in ("/api", "/api/v1"):
        put = client.put(f"{prefix}/settings", json={"key": "theme", "value": "dark"}, headers=account["headers"])
        assert put.status_code == 200, put.text
        assert client.get(f"{prefix}/settings", headers=account["headers"]).status_code == 200
        add = client.post(f"{prefix}/search-history", json={"query": "paneer"}, headers=account["headers"])
        assert add.status_code == 201, add.text
        assert client.get(f"{prefix}/search-history", headers=account["headers"]).status_code == 200
