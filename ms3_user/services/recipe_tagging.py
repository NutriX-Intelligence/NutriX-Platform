"""
(Re)tag the home-style recipe library with its dietary class.

Why this matters: the recommendation engine pre-filters recipes in SQL by `recipes.dietary_tag` and then TRUSTS that
tag. A Jain or vegan user can therefore only ever see recipes that were tagged Jain/Vegan, and a vegetarian user is only as safe as the
tag is correct. A keyword guess (anything with "chicken" in the name is non-veg, everything else vegetarian) mislabelled hundreds of
recipes, so Jain/vegan users saw almost nothing and vegetarians could be shown chicken stock.

The tag is now derived from the ingredient list with the engine's own classifier (RecommendationEngine.classify_from_ingredients):
  * fast-food items (brand set) keep the tag the chain published,
  * regional recipes keep the curated tag from their CSV, unless the ingredients clearly contradict it
    (declared vegetarian/vegan/Jain but the ingredients contain meat, fish or egg: the safer, classifier tag wins),
  * everything else is classified from its ingredients.
"""
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from shared.models import Recipe
from ms3_user.services.recommendation_engine import RecommendationEngine

DATA_DIR = Path(__file__).resolve().parents[2] / "dataset" / "ms3_datasets"
REGIONAL_CSVS = [
    "bengali_foods.csv", "chinese_foods.csv", "gujarati_kathiyawadi_foods.csv", "italian_foods.csv", "japanese_foods.csv",
    "maharashtrian_foods.csv", "mexican_foods.csv", "punjabi_foods.csv", "rajasthani_foods.csv", "south_indian_foods.csv",
]
MEATLESS_CLAIMS = {"Jain", "Vegan", "Vegetarian"}
NOT_MEATLESS = {"Non-Vegetarian", "Pescatarian", "Eggetarian"}


def declared_regional_tags() -> Dict[str, str]:
    """{lower-cased dish name: tag} from the curated 'Dietary Tag' column of the regional CSVs (empty if the files are missing)."""
    try:
        import pandas as pd
        from shared.seeders.seed_recipes import map_dietary_tag
    except Exception:
        return {}
    out: Dict[str, str] = {}
    for filename in REGIONAL_CSVS:
        path = DATA_DIR / filename
        if not path.exists():
            continue
        df = pd.read_csv(path, encoding="utf-8", on_bad_lines="skip")
        for _, row in df.iterrows():
            name = str(row.get("Dish Name", "")).strip().lower()
            tag = map_dietary_tag(row.get("Dietary Tag"))
            if name and tag:
                out[name] = tag
    return out


def decide(declared: Optional[str], classified: str) -> Tuple[str, str]:
    """(final tag, reason). The safer reading wins when a curated tag contradicts the ingredients."""
    if declared:
        if declared in MEATLESS_CLAIMS and classified in NOT_MEATLESS:
            return classified, "conflict: ingredients contradict the declared tag"
        return declared, "declared"
    return classified, "ingredients"


def retag_recipes(
    db: Session,
    apply: bool = False,
    only_untagged: bool = False,
    declared: Optional[Dict[str, str]] = None,
) -> Dict[str, object]:
    """
    Classify every non-fast-food recipe. With apply=False nothing is written (dry run).
    Returns {"before": Counter, "after": Counter, "changes": [(code, name, old, new, reason)], "conflicts": [...], "total": n}.
    """
    declared = declared_regional_tags() if declared is None else declared
    query = db.query(Recipe).options(joinedload(Recipe.ingredients)).filter(Recipe.brand.is_(None))
    recipes: List[Recipe] = query.all()

    before, after = Counter(), Counter()
    changes, conflicts = [], []
    for recipe in recipes:
        old = recipe.dietary_tag
        before[old or "NULL"] += 1
        if only_untagged and old:
            after[old] += 1
            continue
        classified = RecommendationEngine.classify_from_ingredients(recipe)["dietary_tag"]
        regional = (recipe.recipe_code or "").startswith("REG_")
        new, reason = decide(declared.get((recipe.recipe_name or "").strip().lower()) if regional else None, classified)
        after[new] += 1
        if reason.startswith("conflict"):
            conflicts.append((recipe.recipe_code, recipe.recipe_name, declared.get((recipe.recipe_name or "").strip().lower()), classified))
        if new != old:
            changes.append((recipe.recipe_code, recipe.recipe_name, old, new, reason))
            if apply:
                recipe.dietary_tag = new
    if apply:
        db.commit()
    return {"before": before, "after": after, "changes": changes, "conflicts": conflicts, "total": len(recipes)}
