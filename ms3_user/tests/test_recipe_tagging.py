"""Recipe library tagging: tags come from ingredients, curated tags are kept unless contradicted, fast food is untouched."""
import pytest

from shared.db import SessionLocal
from shared.models import Recipe, RecipeIngredient
from ms3_user.services.recipe_tagging import decide, retag_recipes
from ms3_user.services.recommendation_engine import RecommendationEngine


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        # leave the shared throw-away DB as found: other tests treat "no recipes" as "no seeded library"
        session.rollback()
        codes = [c for (c,) in session.query(Recipe.recipe_code).filter(Recipe.recipe_code.like("%TAGT%")).all()]
        if codes:
            session.query(RecipeIngredient).filter(RecipeIngredient.recipe_code.in_(codes)).delete(synchronize_session=False)
            session.query(Recipe).filter(Recipe.recipe_code.in_(codes)).delete(synchronize_session=False)
            session.commit()
        RecommendationEngine._RECIPE_TAG_CACHE.clear()
        session.close()


def _recipe(db, code, name, ingredients, tag=None, brand=None, primarysource=None):
    r = Recipe(recipe_code=code, recipe_name=name, category="Lunch/Dinner", dietary_tag=tag, brand=brand, primarysource=primarysource)
    db.add(r)
    db.flush()
    for ing in ingredients:
        db.add(RecipeIngredient(recipe_id=r.id, recipe_code=code, ingredient_name=ing, food_name=ing, amount=1.0, unit="g"))
    db.commit()
    return r


def _tag(db, code):
    db.expire_all()
    return db.query(Recipe).filter_by(recipe_code=code).one().dietary_tag


# ── the rule for curated tags ────────────────────────────────────────────────
@pytest.mark.parametrize("declared,classified,expected,reason_prefix", [
    ("Jain", "Jain", "Jain", "declared"),
    ("Vegan", "Jain", "Vegan", "declared"),                       # curated tag kept when ingredients do not contradict it
    (None, "Vegan", "Vegan", "ingredients"),
    ("Vegetarian", "Non-Vegetarian", "Non-Vegetarian", "conflict"),   # the safer reading wins
    ("Jain", "Pescatarian", "Pescatarian", "conflict"),
    ("Vegan", "Eggetarian", "Eggetarian", "conflict"),
    ("Non-Vegetarian", "Vegetarian", "Non-Vegetarian", "declared"),   # a non-veg claim is never loosened
])
def test_decide(declared, classified, expected, reason_prefix):
    tag, reason = decide(declared, classified)
    assert tag == expected and reason.startswith(reason_prefix)


# ── tagging from ingredients ─────────────────────────────────────────────────
def test_untagged_and_wrongly_tagged_recipes_get_their_ingredient_based_tag(db):
    _recipe(db, "TAGT_JAIN", "Paneer capsicum sabzi", ["Paneer", "Tomato", "Capsicum", "Jeera", "Ghee"], tag="Vegetarian")
    _recipe(db, "TAGT_VEGAN", "Tofu tomato stir fry", ["Tofu", "Tomato", "Capsicum", "Jeera", "Mustard Oil"])
    _recipe(db, "TAGT_ONION", "Onion tomato curry", ["Tomato", "Pyaaz", "Salt"])
    _recipe(db, "TAGT_CHICKEN", "Chicken curry", ["Chicken", "Onion", "Salt"], tag="Vegetarian")   # the safety bug: mislabelled vegetarian

    result = retag_recipes(db, apply=True, declared={})
    assert result["total"] >= 4
    assert _tag(db, "TAGT_JAIN") == "Jain"
    assert _tag(db, "TAGT_VEGAN") in ("Jain", "Vegan")          # tofu + tomato + capsicum + mustard oil is both Jain and vegan
    assert _tag(db, "TAGT_ONION") == "Vegan"                    # onion rules out Jain
    assert _tag(db, "TAGT_CHICKEN") == "Non-Vegetarian"


def test_the_engine_then_offers_each_recipe_only_to_the_right_diets(db):
    _recipe(db, "TAGT_E_JAIN", "Paneer capsicum bhaji", ["Paneer", "Tomato", "Capsicum", "Jeera", "Ghee"])
    _recipe(db, "TAGT_E_CHICKEN", "Butter chicken", ["Chicken", "Butter", "Tomato"])
    retag_recipes(db, apply=True, declared={})
    db.expire_all()
    jain, chicken = (db.query(Recipe).filter_by(recipe_code=c).one() for c in ("TAGT_E_JAIN", "TAGT_E_CHICKEN"))
    RecommendationEngine._RECIPE_TAG_CACHE.clear()
    assert RecommendationEngine.is_jain(jain) and RecommendationEngine.is_vegetarian(jain)
    assert not RecommendationEngine.is_vegetarian(chicken) and not RecommendationEngine.is_vegan(chicken)


def test_fast_food_items_are_never_touched(db):
    _recipe(db, "FF_TAGT_0001", "Veg Whopper", ["Chicken"], tag="Jain", brand="Burger King")   # chain-declared tag wins
    retag_recipes(db, apply=True, declared={})
    assert _tag(db, "FF_TAGT_0001") == "Jain"


def test_regional_curated_tag_is_kept_but_overridden_when_contradicted(db):
    _recipe(db, "REG_TAGT_0001", "Dal Baati Tagtest", ["Toor Dal", "Ghee", "Wheat Flour"])
    _recipe(db, "REG_TAGT_0002", "Fish Curry Tagtest", ["Fish", "Coconut Milk"])
    declared = {"dal baati tagtest": "Jain", "fish curry tagtest": "Vegetarian"}
    result = retag_recipes(db, apply=True, declared=declared)
    assert _tag(db, "REG_TAGT_0001") == "Jain"                    # curated tag kept
    assert _tag(db, "REG_TAGT_0002") == "Pescatarian"             # declared vegetarian but it is fish: safer tag wins
    assert any(c[0] == "REG_TAGT_0002" for c in result["conflicts"])


def test_dry_run_changes_nothing_and_only_untagged_respects_existing_tags(db):
    _recipe(db, "TAGT_DRY", "Chicken tikka dry", ["Chicken"], tag="Vegetarian")
    _recipe(db, "TAGT_NEW", "Chicken korma new", ["Chicken"])

    dry = retag_recipes(db, apply=False, declared={})
    assert any(c[0] == "TAGT_DRY" for c in dry["changes"]) and _tag(db, "TAGT_DRY") == "Vegetarian"

    retag_recipes(db, apply=True, only_untagged=True, declared={})
    assert _tag(db, "TAGT_DRY") == "Vegetarian"       # already tagged: left alone
    assert _tag(db, "TAGT_NEW") == "Non-Vegetarian"   # untagged: classified


def test_classify_from_ingredients_ignores_the_stored_tag(db):
    r = _recipe(db, "TAGT_IGN", "Chicken sandwich", ["Chicken", "Bread"], tag="Vegetarian")
    assert RecommendationEngine.classify_from_ingredients(r)["dietary_tag"] == "Non-Vegetarian"


# ── a Jain tag must not make a dairy recipe "vegan" ──────────────────────────
def test_jain_tagged_recipe_with_dairy_is_not_offered_to_vegans(db):
    RecommendationEngine._RECIPE_TAG_CACHE.clear()
    dairy = _recipe(db, "TAGT_LEAK_DAIRY", "Paneer capsicum fry", ["Paneer", "Tomato", "Capsicum", "Jeera", "Ghee"], tag="Jain")
    assert RecommendationEngine.is_jain(dairy) and RecommendationEngine.is_vegetarian(dairy)
    assert not RecommendationEngine.is_vegan(dairy)


def test_jain_tagged_recipe_that_is_really_vegan_is_still_offered_to_vegans(db):
    RecommendationEngine._RECIPE_TAG_CACHE.clear()
    both = _recipe(db, "TAGT_LEAK_BOTH", "Tofu capsicum stir fry", ["Tofu", "Tomato", "Capsicum", "Jeera", "Mustard Oil"], tag="Jain")
    assert RecommendationEngine.is_jain(both) and RecommendationEngine.is_vegan(both)


def test_fast_food_jain_item_without_ingredients_is_not_offered_to_vegans(db):
    RecommendationEngine._RECIPE_TAG_CACHE.clear()
    item = _recipe(db, "FF_TAGT_LEAK", "Veg Wrap", [], tag="Jain", brand="Burger King")
    assert RecommendationEngine.is_jain(item) and RecommendationEngine.is_vegetarian(item) and not RecommendationEngine.is_vegan(item)


def test_vegan_tag_is_vegan_and_vegetarian_but_not_jain(db):
    RecommendationEngine._RECIPE_TAG_CACHE.clear()
    item = _recipe(db, "TAGT_LEAK_VEGAN", "Onion rice", ["Rice", "Onion", "Oil"], tag="Vegan")
    assert RecommendationEngine.is_vegan(item) and RecommendationEngine.is_vegetarian(item) and not RecommendationEngine.is_jain(item)
