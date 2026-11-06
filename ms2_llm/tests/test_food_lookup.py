import pytest

from ms2_llm.tests.conftest import add_food
from shared.food_lookup import (LLM_BRAND, lookup_food, lookup_food_with_tier, lookup_macros, partial_allowed,
                                persist_llm_food)


@pytest.fixture()
def partial_on(monkeypatch):
    monkeypatch.setenv("FOOD_LOOKUP_PARTIAL", "true")


def test_exact_and_alias_match(db):
    add_food(db, "Apple", 52, 0.3, 14, 0.2, aliases=["seb"])
    assert lookup_food_with_tier(db, "apple")[0] == "exact"    # case-insensitive
    assert lookup_food_with_tier(db, "SEB")[0] == "alias"
    assert lookup_food(db, "SEB").name == "Apple"
    assert lookup_food(db, "spaceship") is None


def test_partial_tier_is_off_by_default(db, monkeypatch):
    monkeypatch.delenv("FOOD_LOOKUP_PARTIAL", raising=False)
    add_food(db, "Paneer Butter Masala", 240, 10, 8, 18)
    assert lookup_food_with_tier(db, "paneer butter masal") == ("miss", None)


def test_partial_needs_two_words_and_80pct_coverage(db, partial_on):
    add_food(db, "Paneer Tikka", 240, 14, 8, 17)
    add_food(db, "Palakpaneer", 180, 9, 6, 13)
    add_food(db, "Bell Pepper", 31, 1, 6, 0.3)
    add_food(db, "Paneer Butter Masala", 240, 10, 8, 18)
    assert lookup_food(db, "tikka") is None                    # single word: never partial
    assert lookup_food(db, "paneer") is None                   # the S5 'paneer' -> Palakpaneer case
    assert lookup_food(db, "pepper") is None                   # the S5 'pepper' -> Bell Pepper case
    assert lookup_food(db, "butter masala") is None            # 13/20 chars = 65 % < 80 %
    tier, food = lookup_food_with_tier(db, "paneer butter masal")   # 19/20 chars = 95 %
    assert (tier, food.name) == ("partial", "Paneer Butter Masala")


def test_partial_allowed_rule():
    assert partial_allowed("paneer butter masal", "Paneer Butter Masala")
    assert not partial_allowed("paneer", "Palakpaneer")
    assert not partial_allowed("butter masala", "Paneer Butter Masala")


def test_partial_match_ignores_untrusted_brands(db, partial_on):
    add_food(db, "Tikka Masala Sauce", 90, 2, 10, 4, brand="SomeBrand")
    assert lookup_food(db, "tikka masala sauc") is None


def test_zero_energy_row_is_a_miss(db):
    """The demo 'Chocolate Bar' / 'Oreo' 0 kcal logs: an empty row must not count as a DB hit."""
    add_food(db, "Chocolate Bar", 0, 0, 0, 0)
    add_food(db, "Macro Only", 0, 3, 10, 1)        # energy missing even though grams exist: still a miss
    assert lookup_food(db, "chocolate bar") is None
    assert lookup_macros(db, "chocolate bar") is None
    assert lookup_food(db, "macro only") is None


def test_zero_energy_row_is_kept_for_zero_kcal_foods(db):
    add_food(db, "Black Coffee", 0, 0, 0, 0)
    add_food(db, "Water", 0, 0, 0, 0, aliases=["paani"])
    assert lookup_food(db, "black coffee").name == "Black Coffee"
    assert lookup_food(db, "water").name == "Water"


def test_zero_row_skipped_in_favour_of_complete_row(db):
    add_food(db, "OREO", 0, 0, 0, 0)
    full = add_food(db, "Oreo", 483, 5.2, 71.9, 19.6)
    assert lookup_food(db, "oreo").id == full.id


def test_like_wildcards_are_escaped(db):
    add_food(db, "Apple", 52, 0.3, 14, 0.2)
    assert lookup_food(db, "%") is None
    assert lookup_food(db, "a_ple") is None


def test_lookup_macros_shape(db):
    add_food(db, "Apple", 52, 0.3, 14, 0.2)
    assert lookup_macros(db, "apple") == {"calories": 52, "protein_g": 0.3, "carbs_g": 14, "fat_g": 0.2}


def test_persist_llm_food_is_idempotent_and_then_a_db_hit(db):
    macros = {"calories": 150, "protein_g": 11, "carbs_g": 8, "fat_g": 8}
    first = persist_llm_food(db, "Murgh Makhani", macros)
    again = persist_llm_food(db, "murgh  makhani", macros)

    assert first.id == again.id and first.brand == LLM_BRAND
    assert first.food_code == "LLM_murgh_makhani"
    assert lookup_macros(db, "murgh makhani")["calories"] == 150


def test_persist_refuses_unknown(db):
    assert persist_llm_food(db, "unknown", {"calories": 1, "protein_g": 0, "carbs_g": 0, "fat_g": 0}) is None
