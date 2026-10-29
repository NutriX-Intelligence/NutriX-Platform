"""Classifier false positives found when retagging the recipe library: cow's milk read as beef, eggs read as poultry."""
import pytest

from ms3_user.services.classification_engine import ClassificationEngine

classify = ClassificationEngine.classify_ingredients


@pytest.mark.parametrize("name", [
    "Milk, whole, Cow", "Milk, Cow", "Cow's milk", "cow milk", "Cow ghee", "Ghee, cow", "Paneer, cow milk", "Curd, cow",
])
def test_cow_dairy_is_vegetarian_dairy_not_beef(name):
    res = classify([name])
    assert res["is_vegetarian"] and not res["is_vegan"] and res["is_jain"], (name, res["dietary_tag"])
    assert res["dietary_tag"] == "Jain"          # dairy is fine for Jain, and nothing else rules it out


@pytest.mark.parametrize("name", ["Egg, poultry, whole, raw", "Egg, poultry, yolk, raw", "Egg, poultry, white, raw", "Poultry egg"])
def test_eggs_are_eggetarian_not_meat(name):
    res = classify([name])
    assert res["dietary_tag"] == "Eggetarian" and not res["is_vegetarian"] and res["is_eggetarian"], res["dietary_tag"]


@pytest.mark.parametrize("name", ["Beef", "Cow meat", "Beef mince", "Chicken, poultry, breast, skinless", "Chicken", "Mutton", "Lamb, mince, raw"])
def test_real_meat_is_still_meat(name):
    res = classify([name])
    assert res["dietary_tag"] == "Non-Vegetarian" and not res["is_vegetarian"] and not res["is_eggetarian"], (name, res["dietary_tag"])


def test_a_tea_recipe_is_vegetarian_and_an_omelette_is_eggetarian():
    tea = classify(["Hot tea (Garam Chai)", "Milk, whole, Cow", "Sugar, white", "Tea, black, infusion, average", "Water, distilled"])
    assert tea["is_vegetarian"] and tea["dietary_tag"] == "Jain"
    omelette = classify(["Omelette", "Egg, poultry, whole, raw", "Onion", "Oil"])
    assert omelette["dietary_tag"] == "Eggetarian"
    keema = classify(["Egg keema", "Mutton, mince", "Egg, poultry, whole, raw"])
    assert keema["dietary_tag"] == "Non-Vegetarian"
