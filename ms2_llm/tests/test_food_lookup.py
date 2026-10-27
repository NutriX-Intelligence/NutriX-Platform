from ms2_llm.tests.conftest import add_food
from shared.food_lookup import LLM_BRAND, lookup_food, lookup_macros, persist_llm_food


def test_exact_alias_and_partial_match(db):
    add_food(db, "Apple", 52, 0.3, 14, 0.2, aliases=["seb"])
    add_food(db, "Paneer Tikka", 240, 14, 8, 17)

    assert lookup_food(db, "apple").name == "Apple"          # exact, case-insensitive
    assert lookup_food(db, "SEB").name == "Apple"             # alias
    assert lookup_food(db, "tikka").name == "Paneer Tikka"    # partial, trusted brand
    assert lookup_food(db, "spaceship") is None


def test_partial_match_ignores_untrusted_brands(db):
    add_food(db, "Tikka Masala Sauce", 90, 2, 10, 4, brand="SomeBrand")
    assert lookup_food(db, "tikka") is None


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
