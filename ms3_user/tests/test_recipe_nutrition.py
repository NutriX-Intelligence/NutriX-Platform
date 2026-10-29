"""AI recipe generator: structured name + per-serving macros so the app can log the meal without guessing from prose."""
import json

import pytest
from fastapi.testclient import TestClient

from ms3_user.main import app
from ms3_user.services import ai_text, recipe_nutrition
from ms3_user.services.recipe_nutrition import extract

client = TestClient(app)

RECIPE = """**Recipe Name: Paneer Tikka Power Bowl**

**Difficulty:** Easy | **Time:** 25 mins

1. Marinate the paneer.
2. Grill and serve over rice.
"""


def _block(**per):
    data = {"name": "Paneer Tikka Power Bowl", "servings": 2,
            "per_serving": {"calories": 610, "protein_g": 32, "carbs_g": 60, "fat_g": 26, **per}}
    return "\n```json\n" + json.dumps(data) + "\n```"


# ── the structured block ─────────────────────────────────────────────────────
def test_block_gives_name_servings_and_macros_and_is_hidden_from_the_text():
    out = extract(RECIPE + _block())
    assert out["name"] == "Paneer Tikka Power Bowl" and out["servings"] == 2
    assert out["nutrition"] == {"calories": 610.0, "protein_g": 32.0, "carbs_g": 60.0, "fat_g": 26.0,
                                "per": "serving", "basis": "ai_block", "consistent": True}
    assert "```" not in out["recipe"] and "per_serving" not in out["recipe"] and "Marinate the paneer" in out["recipe"]


def test_block_without_a_json_fence_label_and_with_flat_numbers():
    text = RECIPE + '\n```\n{"name": "Flat", "calories": 300, "protein_g": 20, "carbs_g": 30, "fat_g": 10}\n```'
    out = extract(text)
    assert out["name"] == "Flat" and out["nutrition"]["calories"] == 300.0 and out["nutrition"]["basis"] == "ai_block"


def test_an_all_zero_template_block_is_not_trusted_and_the_text_is_used():
    text = RECIPE + "\n**Total Calories:** 540 kcal\n**Protein:** 30g | **Carbs:** 50g | **Fat:** 22g" + _block(
        calories=0, protein_g=0, carbs_g=0, fat_g=0)
    out = extract(text)
    assert out["nutrition"]["basis"] == "parsed_text" and out["nutrition"]["calories"] == 540.0
    assert (out["nutrition"]["protein_g"], out["nutrition"]["carbs_g"], out["nutrition"]["fat_g"]) == (30.0, 50.0, 22.0)


def test_invalid_json_block_falls_back_to_the_text():
    out = extract(RECIPE + "\nCalories: 450 kcal\nProtein: 25g\nCarbs: 40g\nFat: 20g\n```json\n{broken\n```")
    assert out["nutrition"]["basis"] == "parsed_text" and out["nutrition"]["calories"] == 450.0


def test_a_broken_or_truncated_block_is_removed_from_the_visible_text():
    broken = extract(RECIPE + "\nCalories: 450 kcal\n```json\n{broken\n```")
    cut_off = extract(RECIPE + '\n```json\n{"name": "X", "per_serv')
    for out in (broken, cut_off):
        assert "```" not in out["recipe"] and "{" not in out["recipe"] and "Marinate the paneer" in out["recipe"]


# ── the figures written in prose (no block) ──────────────────────────────────
def test_macros_are_read_from_prose_and_the_closing_total_wins():
    text = (RECIPE + "- Paneer (200g): Protein 36g, Fat 40g\n\n### Nutrition (per serving)\n"
            "* **Total Calories:** ~610 kcal\n* **Protein:** 35 g\n* **Carbs:** 62 g\n* **Fat:** 24 g\n")
    n = extract(text)["nutrition"]
    assert (n["calories"], n["protein_g"], n["carbs_g"], n["fat_g"]) == (610.0, 35.0, 62.0, 24.0)


def test_only_calories_found_leaves_the_rest_empty_not_zero():
    """The reported case: calories 610 and every macro 0. Missing macros must be None (an empty field), never 0."""
    n = extract(RECIPE + "\nTotal Calories: 610 kcal\n")["nutrition"]
    assert n["calories"] == 610.0 and n["protein_g"] is None and n["carbs_g"] is None and n["fat_g"] is None
    assert n["consistent"] is None


def test_no_figures_at_all_means_no_nutrition_object():
    assert extract("Just boil the pasta and add salt.")["nutrition"] is None
    assert extract("")["nutrition"] is None


# ── sanity checks ────────────────────────────────────────────────────────────
def test_absurd_values_are_dropped():
    assert extract(RECIPE + _block(calories=99999))["nutrition"] is None
    assert extract(RECIPE + _block(protein_g=900, carbs_g=900))["nutrition"] is None


def test_inconsistent_calories_are_flagged_not_silently_changed():
    n = extract(RECIPE + _block(calories=200, protein_g=40, carbs_g=80, fat_g=30))["nutrition"]
    assert n["calories"] == 200.0 and n["consistent"] is False


def test_negative_numbers_are_ignored():
    n = extract(RECIPE + _block(fat_g=-5))["nutrition"]
    assert n["fat_g"] is None and n["calories"] == 610.0


# ── name ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("Recipe Name: Dal Tadka\nsteps", "Dal Tadka"),
    ("**Recipe Name:** Veg Pulao\nsteps", "Veg Pulao"),
    ("# \U0001f35b Chole Masala\n1. cook", "Chole Masala"),
    ("1. just steps\n2. more", None),
])
def test_name_extraction(text, expected):
    assert extract(text)["name"] == expected


# ── the endpoint ─────────────────────────────────────────────────────────────
def test_endpoint_returns_structured_fields_and_hides_the_block(monkeypatch):
    seen = {}

    def fake(prompt=None, **kw):
        seen["prompt"] = prompt
        return RECIPE + _block(), "gemini"

    monkeypatch.setattr(ai_text, "generate_text", fake)
    r = client.post("/api/v1/ai/recipe-generator", json={"ingredients": "paneer, capsicum", "diet": "Vegetarian"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "gemini" and body["name"] == "Paneer Tikka Power Bowl" and body["servings"] == 2
    assert body["nutrition"]["calories"] == 610.0 and body["nutrition"]["protein_g"] == 32.0
    assert "```" not in body["recipe"]
    assert "paneer, capsicum" in seen["prompt"] and "Strictly vegetarian" in seen["prompt"]
    assert recipe_nutrition.MACHINE_BLOCK_INSTRUCTION.strip().splitlines()[0] in seen["prompt"]


def test_endpoint_old_clients_still_get_recipe_and_source(monkeypatch):
    monkeypatch.setattr(ai_text, "generate_text", lambda *a, **k: ("plain text recipe, no numbers", "local"))
    body = client.post("/api/v1/ai/recipe-generator", json={"ingredients": "egg"}).json()
    assert body["recipe"].strip() == "plain text recipe, no numbers" and body["source"] == "local"
    assert body["nutrition"] is None and body["name"] is None


def test_endpoint_offline_has_no_fake_macros(monkeypatch):
    def down(*a, **k):
        raise ai_text.AIUnavailable("down")

    monkeypatch.setattr(ai_text, "generate_text", down)
    body = client.post("/api/v1/ai/recipe-generator", json={"ingredients": "egg"}).json()
    assert body["source"] == "offline" and body["nutrition"] is None and body["name"]
