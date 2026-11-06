"""
Shared food lookup used by MS1 (scale ingestion) and MS2 (LLM nutrition service).

Lookup order (per MASTER_ARCHITECTURE "Lookup Priority Order"):
  1. Exact canonical name match (case-insensitive)
  2. Exact alias match
  3. Partial match, restricted to trusted brands. OFF by default (FOOD_LOOKUP_PARTIAL=true turns it on), and even
     then only for queries of >= 2 words whose text covers >= 80 % of the candidate name's characters: the FSN S5
     audit found single-word partial hits resolving to the wrong food ("paneer" -> Palakpaneer, "pepper" -> Bell Pepper).

A row whose energy_kcal is null/0 is not a usable hit (it is a miss, so the caller asks MS2) unless the food is one of
the few that really have ~0 kcal (water, black coffee, diet soda, ...). Packaged imports contain such empty rows
(e.g. "OREO", all zero), and they used to be logged as 0 kcal meals.

Foods inferred by the LLM are persisted with brand "LLM Inferred" so that the next
lookup of the same name is a plain DB hit and the Meta-Auditor can audit them.
"""
import logging
import os
import re
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.models import Food, FoodAlias, FoodNutrient

logger = logging.getLogger("shared.food_lookup")

TRUSTED_PARTIAL_BRANDS = ["Whole Food", "YOLO Generic"]
LLM_BRAND = "LLM Inferred"
PARTIAL_MIN_WORDS = 2
PARTIAL_MIN_COVERAGE = 0.8      # len(query) / len(candidate name), after normalisation

# Foods whose real energy is ~0 kcal/100 g: a 0 kcal DB row for these is correct, not missing data.
ZERO_ENERGY_FOODS = {
    "water", "drinking water", "mineral water", "packaged drinking water", "sparkling water", "soda water",
    "club soda", "ice", "black coffee", "black tea", "green tea", "herbal tea", "diet coke", "coke zero",
    "diet soda", "diet cola", "salt",
}


def normalize_name(name: str) -> str:
    """Lowercase, replace underscores, collapse whitespace."""
    return re.sub(r"\s+", " ", (name or "").replace("_", " ")).strip().lower()


def partial_enabled() -> bool:
    return os.getenv("FOOD_LOOKUP_PARTIAL", "false").strip().lower() in ("1", "true", "yes", "on")


def is_zero_energy_food(name: str) -> bool:
    return normalize_name(name) in ZERO_ENERGY_FOODS


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _usable(food: Food, query: str = "") -> bool:
    """A hit is usable only if it has an energy value, or the food is genuinely ~0 kcal."""
    n = food.nutrients
    if n is None:
        return False
    if (n.energy_kcal or 0.0) > 0:
        return True
    return is_zero_energy_food(query) or is_zero_energy_food(getattr(food, "name", "") or "")


def _first_with_macros(foods: Iterable[Food], query: str = "") -> Optional[Food]:
    """Several rows can share a name; the first usable one wins. Rows with null/0 energy are skipped (-> miss)."""
    return next((f for f in foods if _usable(f, query)), None)


def partial_coverage(query: str, candidate_name: str) -> float:
    cand = normalize_name(candidate_name)
    return len(normalize_name(query)) / len(cand) if cand else 0.0


def partial_allowed(query: str, candidate_name: str) -> bool:
    q = normalize_name(query)
    return len(q.split()) >= PARTIAL_MIN_WORDS and partial_coverage(q, candidate_name) >= PARTIAL_MIN_COVERAGE


def lookup_food_with_tier(db: Session, name: str) -> Tuple[str, Optional[Food]]:
    """(tier, Food) with tier in exact | alias | partial | miss. lookup_food is this without the tier."""
    clean = normalize_name(name)
    if not clean:
        return "miss", None

    food = _first_with_macros(db.query(Food).filter(Food.name.ilike(_escape_like(clean), escape="\\")).all(), clean)
    if food:
        return "exact", food

    food = _first_with_macros(
        (alias.food for alias in db.query(FoodAlias).filter(
            FoodAlias.alias_name.ilike(_escape_like(clean), escape="\\")
        ).all()), clean)
    if food:
        return "alias", food

    if partial_enabled() and len(clean.split()) >= PARTIAL_MIN_WORDS:
        cands = db.query(Food).filter(
            Food.name.ilike(f"%{_escape_like(clean)}%", escape="\\"),
            Food.brand.in_(TRUSTED_PARTIAL_BRANDS),
        ).all()
        cands = sorted((f for f in cands if partial_allowed(clean, f.name)),
                       key=lambda f: -partial_coverage(clean, f.name))
        food = _first_with_macros(cands, clean)
        if food:
            return "partial", food

    return "miss", None


def lookup_food(db: Session, name: str) -> Optional[Food]:
    """Return the matching Food (with usable nutrients) or None."""
    return lookup_food_with_tier(db, name)[1]


def per_100g(food: Food) -> Optional[Dict[str, float]]:
    """Macros per 100 g for a Food, or None if it has no nutrient row."""
    n = food.nutrients if food else None
    if n is None:
        return None
    return {
        "calories": n.energy_kcal or 0.0,
        "protein_g": n.protein_g or 0.0,
        "carbs_g": n.carb_g or 0.0,
        "fat_g": n.fat_g or 0.0,
    }


def lookup_macros(db: Session, name: str) -> Optional[Dict[str, float]]:
    """Convenience wrapper: name -> per-100g macros, or None on a miss."""
    food = lookup_food(db, name)
    return per_100g(food) if food else None


def persist_llm_food(db: Session, raw_name: str, macros: Dict[str, float]) -> Optional[Food]:
    """
    Insert an LLM-inferred food (idempotent on food_code). Adds an alias row when the
    raw name differs from the canonical one. Returns the Food, or None on failure.
    """
    canonical = normalize_name(raw_name)
    if not canonical or canonical == "unknown":
        return None

    food_code = "LLM_" + re.sub(r"[^a-z0-9]+", "_", canonical).strip("_")
    try:
        food = db.query(Food).filter(Food.food_code == food_code).first()
        if food is None:
            food = Food(food_code=food_code, name=canonical.title(), brand=LLM_BRAND)
            food.nutrients = FoodNutrient(
                energy_kcal=macros.get("calories", 0.0),
                protein_g=macros.get("protein_g", 0.0),
                carb_g=macros.get("carbs_g", 0.0),
                fat_g=macros.get("fat_g", 0.0),
            )
            db.add(food)
            db.commit()
            logger.info("Persisted LLM-inferred food '%s' (%s)", food.name, food_code)
        return food
    except IntegrityError:
        # Concurrent insert of the same food_code: use the winner's row.
        db.rollback()
        return db.query(Food).filter(Food.food_code == food_code).first()
    except Exception as e:
        db.rollback()
        logger.error("Failed to persist LLM food '%s': %s", raw_name, e)
        return None
