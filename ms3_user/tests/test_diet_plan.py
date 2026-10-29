"""AI diet plan: honours the goal and diet type the app sends; goal wording is normalised; the offline plan respects the diet."""
import pytest
from fastapi.testclient import TestClient

from ms3_user.main import app
from ms3_user.routes import _diet_key
from ms3_user.services import ai_text
from ms3_user.services.nutrition_engine import NutritionEngine, normalize_goal

client = TestClient(app)


@pytest.fixture(scope="module")
def account():
    r = client.post("/api/v1/auth/register", json={"email": "dietplan@example.com", "password": "secret123", "name": "Diet User",
                                                  "age": 28, "gender": "male", "height": 175, "weight": 80,
                                                  "activity_level": "sedentary", "goal": "maintenance"})
    assert r.status_code == 201, r.text
    body = r.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}


@pytest.fixture()
def capture(monkeypatch):
    seen = {}

    def fake(prompt=None, **kwargs):
        seen["prompt"], seen["system"] = prompt, kwargs.get("system")
        return "PLAN", "gemini"

    monkeypatch.setattr(ai_text, "generate_text", fake)
    return seen


def _targets(goal):
    return NutritionEngine.calculate_targets(age=28, gender="male", height=175, weight=80, activity_level="sedentary", goal=goal)


# ── goal wording ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    ("weight loss", "fat loss"), ("Weight Loss", "fat loss"), ("lose weight", "fat loss"), ("fat_loss", "fat loss"),
    ("fat loss", "fat loss"), ("cutting", "fat loss"),
    ("weight gain", "weight gain"), ("gain weight", "weight gain"),
    ("muscle gain", "muscle gain"), ("build muscle", "muscle gain"), ("bulking", "muscle gain"),
    ("maintenance", "maintenance"), ("maintain", "maintenance"), ("", "maintenance"), (None, "maintenance"), ("???", "maintenance"),
])
def test_normalize_goal(raw, expected):
    assert normalize_goal(raw) == expected


def test_weight_loss_now_gets_a_deficit_not_maintenance_calories():
    loss, fat_loss, maint = _targets("weight loss"), _targets("fat loss"), _targets("maintenance")
    assert loss["target_calories"] == fat_loss["target_calories"] < maint["target_calories"]


@pytest.mark.parametrize("raw,expected", [
    ("Vegetarian", "vegetarian"), ("vegan", "vegan"), ("Jain", "jain"), ("Eggetarian", "eggetarian"),
    ("Non-Vegetarian", "non-vegetarian"), ("non veg", "non-vegetarian"), ("pescatarian", "pescatarian"),
    ("all", None), ("", None), (None, None), ("keto", None),
])
def test_diet_key(raw, expected):
    assert _diet_key(raw) == expected


# ── the route ────────────────────────────────────────────────────────────────
def test_goal_and_diet_from_the_app_reach_the_prompt(account, capture):
    uid, headers = account
    r = client.post("/api/v1/ai/diet-plan", json={"user_id": uid, "goal": "weight loss", "diet_type": "Vegetarian"}, headers=headers)
    assert r.status_code == 200 and r.json() == {"plan": "PLAN", "source": "gemini"}   # response shape is unchanged
    prompt = capture["prompt"]
    assert "weight loss" in prompt and "Strictly vegetarian" in prompt and "no meat, poultry, fish or eggs" in prompt
    assert f"Target Calories: {round(_targets('fat loss')['target_calories'])} kcal" in prompt
    assert f"{round(_targets('maintenance')['target_calories'])} kcal" not in prompt


@pytest.mark.parametrize("body", [
    {"diet": "Vegan", "fitness_goal": "build muscle"},
    {"dietType": "Vegan", "goalType": "muscle gain"},
    {"diet_preference": "Vegan", "goal": "Muscle Gain"},
])
def test_alternative_field_names_are_accepted(account, capture, body):
    uid, headers = account
    assert client.post("/api/v1/ai/diet-plan", json={"user_id": uid, **body}, headers=headers).status_code == 200
    assert "Strictly vegan" in capture["prompt"] and "muscle gain" in capture["prompt"]
    assert f"Target Calories: {round(_targets('muscle gain')['target_calories'])} kcal" in capture["prompt"]


def test_without_overrides_the_profile_is_used(account, capture):
    uid, headers = account
    assert client.post("/api/v1/ai/diet-plan", json={"user_id": uid}, headers=headers).status_code == 200
    assert "maintenance" in capture["prompt"] and "No dietary restrictions" in capture["prompt"]


@pytest.mark.parametrize("diet,forbidden,required", [
    ("Vegetarian", ("chicken", "fish", "egg", "mutton"), "Paneer"),
    ("Vegan", ("chicken", "fish", "egg", "paneer", "curd", "yogurt", "milk"), "Tofu"),
    ("Jain", ("chicken", "fish", "egg", "onion", "garlic,", "potato"), "Dal"),
    ("Non-Vegetarian", (), "chicken"),
])
def test_offline_plan_respects_the_diet(account, monkeypatch, diet, forbidden, required):
    uid, headers = account

    def down(*a, **k):
        raise ai_text.AIUnavailable("down")

    monkeypatch.setattr(ai_text, "generate_text", down)
    body = client.post("/api/v1/ai/diet-plan", json={"user_id": uid, "goal": "weight loss", "diet_type": diet}, headers=headers).json()
    assert body["source"] == "offline"
    text = body["plan"].lower()
    assert required.lower() in text
    for word in forbidden:
        assert word not in text.replace("without onion or garlic", ""), f"{word!r} in the {diet} offline plan"
