"""
Barcode "healthier alternatives": category-aware swaps with a buy link, drinks only for drinks, and a real grade letter.
"""
import pytest
from fastapi.testclient import TestClient

from ms3_user.main import app
from ms3_user.services.barcode_service import BarcodeService

client = TestClient(app)
ALT = "/api/v1/barcode/alternatives"

DRINKS = ["Sprite 750ml", "Coca-Cola Original Taste", "Thums Up", "Real Fruit Juice Mango", "Frooti", "Nescafe Cold Coffee",
          "Amul Lassi", "Red Bull Energy Drink", "Limca", "Paper Boat Aamras Drink"]
FOODS = ["Nutella Hazelnut Spread", "Maggi 2-Minute Noodles", "Lays Magic Masala Chips", "Oreo Biscuits", "Cadbury Dairy Milk",
         "Haldiram Bhujia", "Haldiram moong dal", "Kellogg's Corn Flakes"]
DRINK_SWAP_WORDS = ("water", "buttermilk", "chaas", "kombucha", "tea")


def _swaps(name, diet="all"):
    return BarcodeService.get_healthier_alternatives(name, "Snack", {"energy_kcal": 300}, diet_type=diet)


@pytest.mark.parametrize("name", DRINKS)
@pytest.mark.parametrize("diet", ["all", "vegan", "jain", "keto"])
def test_a_drink_only_gets_drinks(name, diet):
    swaps = _swaps(name, diet)
    assert swaps, name
    for s in swaps:
        assert any(w in s["name"].lower() for w in DRINK_SWAP_WORDS), f"{name} ({diet}) got a non-drink: {s['name']}"


@pytest.mark.parametrize("name", FOODS)
@pytest.mark.parametrize("diet", ["all", "vegan", "jain", "keto"])
def test_food_never_gets_a_drink(name, diet):
    for s in _swaps(name, diet):
        assert not any(w in s["name"].lower() for w in DRINK_SWAP_WORDS), f"{name} ({diet}) got a drink: {s['name']}"


@pytest.mark.parametrize("name", DRINKS + FOODS + ["Some Unknown Product"])
def test_every_swap_has_a_working_buy_link_and_a_reason(name):
    swaps = _swaps(name)
    assert swaps
    for s in swaps:
        assert s["link"].startswith("https://") and "?" in s["link"], s
        assert s["reason"] and s["price"] > 0


def test_nutella_gets_sweet_swaps_not_chaas_chana_or_protein_bars():
    names = [s["name"] for s in _swaps("Nutella")]
    assert any("Peanut Butter" in n or "Ragi" in n or "Dates" in n for n in names)
    assert not any(w in n.lower() for n in names for w in ("buttermilk", "chaas", "chana"))


def test_alternatives_endpoint_uses_the_same_category_logic_and_returns_links(monkeypatch):
    reg = client.post("/api/v1/auth/register", json={"email": "alt_user@example.com", "password": "secret123", "name": "Alt"}).json()
    h = {"Authorization": f"Bearer {reg['access_token']}"}

    r = client.post(ALT, headers=h, json={"product_name": "Nutella", "meal_type": "Snack", "protein_g": 6.3,
                                           "energy_kcal": 539, "sugar_g": 56.3, "fat_g": 30.9, "estimated_price": 40})
    assert r.status_code == 200
    swaps = r.json()["alternatives"]
    assert swaps and all(s["link"].startswith("https://") and s["buy_label"] == "View / Buy Online" for s in swaps)
    assert not any("buttermilk" in s["name"].lower() or "chaas" in s["name"].lower() for s in swaps)

    r = client.post(ALT, headers=h, json={"product_name": "Sprite 750ml", "meal_type": "Snack", "protein_g": 0,
                                           "energy_kcal": 40, "sugar_g": 10, "estimated_price": 40})
    names = [s["name"].lower() for s in r.json()["alternatives"]]
    assert names and all(any(w in n for w in DRINK_SWAP_WORDS) for n in names)


def test_diet_from_the_request_is_respected():
    r = client.post(ALT, headers={"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={"email": "alt_user@example.com", "password": "secret123"}).json()["access_token"]},
                    json={"product_name": "Sprite", "meal_type": "Snack", "protein_g": 0, "energy_kcal": 40, "diet_type": "keto"})
    names = [s["name"].lower() for s in r.json()["alternatives"]]
    assert any("green tea" in n or "sparkling" in n for n in names)


@pytest.mark.parametrize("grade,score,expected", [
    ("e", 80, "e"), ("A", 10, "a"), ("unknown", 18.9, "e"), ("u", 29.7, "e"), ("h", 72.9, "b"),
    (None, 90, "a"), ("", 50, "c"), ("m", 35, "d"),
])
def test_grade_is_always_a_nutri_score_letter(grade, score, expected):
    assert BarcodeService.resolve_grade(grade, score) == expected
