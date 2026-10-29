"""Meal planner gate: spice mixes, condiments and batch-sized calorie figures are not meals."""
import pytest

from ms3_user.services.meal_candidates import is_condiment_or_mix, is_plan_candidate


@pytest.mark.parametrize("name", [
    "Garam masala", "Chat masala", "Kashmiri masala", "Pav bhaji masala", "Rasam powder (Rasam masala)", "Sambar powder (Sambar masala)",
    "Bengal 5 Spice Blend (Panch Phoran)", "Gun powder chutney", "Idli podi",
    "Coconut chutney (Nariyal ki chutney)", "Mint and coriander chutney (Pudinay aur dhaniye ki chutney)", "Schezwan chutney",
    "Mango pickle (Aam ka achaar)", "Pickled mustard greens", "Garlic pickle (Lahasun ka achar)",
    "White sauce (thin)", "Cheese sauce", "Tomato ketchup", "Mayonnaise", "Thousand island dressing", "Curd dip",
    "Brown stock", "Vegetable stock", "Apple jam (Seb ka murabba)", "Guava jelly (Amrood ki jelly)", "Lemon squash (Nimbu ka squash)",
])
def test_condiments_and_mixes_are_not_meals(name):
    assert is_condiment_or_mix(name), name
    assert not is_plan_candidate(name, 250.0, "Lunch"), name


@pytest.mark.parametrize("name", [
    "Masala dosa", "Masala Dosa with Coconut Chutney & Sambhar", "Jain Mysore Masala Dosa", "Masala arbi", "Paneer butter masala",
    "Chole masala", "Shahi chicken masala", "Baked fish with cheese sauce", "Spaghetti and cheese balls in tomato sauce",
    "Jam and fruit pancake", "Gulab jamun with milk powder", "Sprouts upma", "Dal dhokli", "Peanut pulao", "Masala chai",
    "Cabbage and peas (Pattagobhi aur matar)", "Jhatpat achar with carrot (Jhatpat achaar gajar ke saath)", "Tomato soup", "Vegetable mix",
])
def test_real_dishes_are_kept(name):
    assert not is_condiment_or_mix(name), name


@pytest.mark.parametrize("slot,kcal,ok", [
    ("Snack", 1553, False),     # the Schezwan chutney snack from the report
    ("Snack", 650, False), ("Snack", 150, True), ("Snack", 20, False),
    ("Breakfast", 301, True), ("Breakfast", 950, False), ("Breakfast", 40, False),
    ("Lunch", 4876, False),     # a whole-batch figure (Paneer pulao 4,876 kcal)
    ("Lunch", 450, True), ("Dinner", 1200, False), ("Dinner", 3, False), ("Dinner", 267, True),
])
def test_calorie_sanity_per_slot(slot, kcal, ok):
    assert is_plan_candidate("Vegetable pulao", kcal, slot) is ok


def test_unknown_calories_are_rejected():
    assert not is_plan_candidate("Vegetable pulao", None, "Lunch")


def test_user_made_meals_skip_only_the_name_rule():
    assert is_plan_candidate("Chutney sandwich", 300.0, "Snack", user_made=True)
    assert not is_plan_candidate("Chutney sandwich", 3000.0, "Snack", user_made=True)
