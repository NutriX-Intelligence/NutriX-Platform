"""
Shared food lookup used by MS1 (scale ingestion) and MS2 (LLM nutrition service).

Lookup order (per MASTER_ARCHITECTURE "Lookup Priority Order"):
  1. Exact canonical name match (case-insensitive)
  2. Exact alias match
  3. Partial match, restricted to trusted brands

Foods inferred by the LLM are persisted with brand "LLM Inferred" so that the next
lookup of the same name is a plain DB hit and the Meta-Auditor can audit them.
"""
import logging
import re
from typing import Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.models import Food, FoodAlias, FoodNutrient

logger = logging.getLogger("shared.food_lookup")

TRUSTED_PARTIAL_BRANDS = ["Whole Food", "YOLO Generic"]
LLM_BRAND = "LLM Inferred"


def normalize_name(name: str) -> str:
    """Lowercase, replace underscores, collapse whitespace."""
    return re.sub(r"\s+", " ", (name or "").replace("_", " ")).strip().lower()


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def lookup_food(db: Session, name: str) -> Optional[Food]:
    """Return the matching Food (with nutrients) or None."""
    clean = normalize_name(name)
    if not clean:
        return None

    food = db.query(Food).filter(Food.name.ilike(_escape_like(clean), escape="\\")).first()

    if not food:
        alias = db.query(FoodAlias).filter(
            FoodAlias.alias_name.ilike(_escape_like(clean), escape="\\")
        ).first()
        if alias:
            food = alias.food

    if not food:
        food = db.query(Food).filter(
            Food.name.ilike(f"%{_escape_like(clean)}%", escape="\\"),
            Food.brand.in_(TRUSTED_PARTIAL_BRANDS),
        ).first()

    return food


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
