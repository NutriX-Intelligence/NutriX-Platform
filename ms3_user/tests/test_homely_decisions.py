"""
Homely meals: the creator keeps the recipe in My Recipes (never in their own Pending), and every other user approves
or rejects it independently. One user's decision must never change what anybody else sees.
"""
import pytest
from fastapi.testclient import TestClient

from ms3_user.main import app

client = TestClient(app)
BASE = "/api/v1/homely-meals"


def _register(email: str) -> dict:
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "secret123", "name": email.split("@")[0]})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"id": body["user"]["id"], "h": {"Authorization": f"Bearer {body['access_token']}"}}


@pytest.fixture(scope="module")
def users():
    return {"a": _register("hd_a@example.com"), "b": _register("hd_b@example.com"), "c": _register("hd_c@example.com")}


def _create(user: dict, name: str, shared: bool = True) -> dict:
    r = client.post(f"{BASE}/create", headers=user["h"], json={
        "name": name, "is_community": shared,
        "ingredients": [{"ingredient_name": "ghee", "amount": 1, "unit": "tsp"}],
    })
    assert r.status_code == 200, r.text
    return r.json()


def _names(user: dict, section: str) -> list:
    path = {"mine": f"/user/{user['id']}", "pending": "/pending", "approved": "/approved", "rejected": "/rejected", "search": "/search"}[section]
    r = client.get(BASE + path, headers=user["h"])
    assert r.status_code == 200, r.text
    return [m["name"] for m in r.json()]


def _decide(user: dict, meal_id: int, decision: str):
    return client.post(f"{BASE}/review/{meal_id}", headers=user["h"], json={"status": decision, "comment": "ok"})


def test_creator_sees_it_in_my_recipes_and_never_in_their_own_pending(users):
    a = users["a"]
    meal = _create(a, "Creator Khichdi")
    assert meal["is_mine"] is True and meal["status"] == "approved"
    assert "Creator Khichdi" in _names(a, "mine")
    assert "Creator Khichdi" not in _names(a, "pending")
    assert "Creator Khichdi" not in _names(a, "approved")


def test_shared_recipe_is_pending_for_every_other_user(users):
    _create(users["a"], "Shared Dal")
    assert "Shared Dal" in _names(users["b"], "pending")
    assert "Shared Dal" in _names(users["c"], "pending")


def test_decisions_are_per_user(users):
    a, b, c = users["a"], users["b"], users["c"]
    meal_id = _create(a, "Per User Paratha")["id"]

    # B approves: Approved for B only, still Pending for C
    r = _decide(b, meal_id, "approved")
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["my_decision"] == "approved"
    assert "Per User Paratha" in _names(b, "approved") and "Per User Paratha" not in _names(b, "pending")
    assert "Per User Paratha" in _names(c, "pending") and "Per User Paratha" not in _names(c, "approved")

    # C rejects: gone from C's pending, recorded as rejected for C only
    r = _decide(c, meal_id, "rejected")
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert "Per User Paratha" not in _names(c, "pending") + _names(c, "approved") + _names(c, "search")
    assert "Per User Paratha" in _names(c, "rejected")

    # ...and nothing changed for B or for the creator
    assert "Per User Paratha" in _names(b, "approved") and "Per User Paratha" not in _names(b, "rejected")
    assert "Per User Paratha" in _names(a, "mine") and "Per User Paratha" not in _names(a, "pending")
    detail = client.get(f"{BASE}/{meal_id}", headers=a["h"]).json()
    assert detail["is_mine"] is True and detail["status"] == "approved"


def test_a_user_can_change_their_mind_without_affecting_others(users):
    b, c = users["b"], users["c"]
    meal_id = _create(users["a"], "Second Thoughts Poha")["id"]
    _decide(c, meal_id, "rejected")
    _decide(b, meal_id, "approved")
    assert _decide(c, meal_id, "approved").status_code == 200
    assert "Second Thoughts Poha" in _names(c, "approved") and "Second Thoughts Poha" not in _names(c, "rejected")
    assert "Second Thoughts Poha" in _names(b, "approved")


def test_creator_cannot_review_their_own_recipe(users):
    meal_id = _create(users["a"], "Own Goal Upma")["id"]
    assert _decide(users["a"], meal_id, "approved").status_code == 403


def test_status_must_be_approved_or_rejected(users):
    meal_id = _create(users["a"], "Odd Status Idli")["id"]
    assert _decide(users["b"], meal_id, "banana").status_code == 400
    assert "Odd Status Idli" in _names(users["b"], "pending")


def test_every_created_recipe_is_shared_even_if_the_client_asks_for_private(users):
    a, b = users["a"], users["b"]
    meal = _create(a, "Always Shared Sabzi", shared=False)  # old clients may still send is_community=false
    assert meal["is_community"] is True
    assert "Always Shared Sabzi" in _names(a, "mine")
    assert "Always Shared Sabzi" in _names(b, "pending")
    assert _decide(b, meal["id"], "approved").status_code == 200


def test_legacy_private_recipe_stays_invisible_to_everyone_else(users):
    """Rows created before sharing became automatic (is_community = false) must stay private to their creator."""
    from shared.db import SessionLocal
    from shared.models import HomelyMeal
    a, b = users["a"], users["b"]
    db = SessionLocal()
    try:
        m = HomelyMeal(name="Legacy Private Sabzi", creator_id=a["id"], is_community=False, status="approved")
        db.add(m)
        db.commit()
        meal_id = m.id
    finally:
        db.close()
    assert "Legacy Private Sabzi" in _names(a, "mine")
    for section in ("pending", "approved", "search"):
        assert "Legacy Private Sabzi" not in _names(b, section)
    assert client.get(f"{BASE}/{meal_id}", headers=b["h"]).status_code == 404
    assert _decide(b, meal_id, "approved").status_code == 404


def test_unknown_meal_is_404(users):
    assert _decide(users["b"], 999999, "approved").status_code == 404


def test_approved_meal_is_offered_by_the_recommender_only_to_who_approved_it(users):
    from shared.db import SessionLocal
    from ms3_user.services.recommendation_engine import RecommendationEngine

    a, b, c = users["a"], users["b"], users["c"]
    meal_id = _create(a, "Recommender Visible Roti")["id"]
    _decide(b, meal_id, "approved")

    def offered(uid):
        db = SessionLocal()
        try:
            recs = RecommendationEngine.get_recommendations(db, uid, limit=2000)
            return any(r["recipe_code"] == f"HOMELY_{meal_id}" for r in recs)
        finally:
            db.close()

    assert offered(b["id"]) is True       # approved it
    assert offered(a["id"]) is True       # created it
    assert offered(c["id"]) is False      # still pending for them
