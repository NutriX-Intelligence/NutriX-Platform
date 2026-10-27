import logging
import time
from typing import Dict, Optional, Tuple

from ms2_llm.config import PROMPT_CACHE_TTL_S

logger = logging.getLogger("ms2_llm.prompts")

VISION_KEY = "vision_infer_v2"
LOOKUP_KEY = "nutrition_lookup_v2"

JSON_CONTRACT = (
    "Respond with ONLY a single JSON object and nothing else (no markdown, no explanation) "
    "with exactly these keys: "
    '"food_name" (common English name in lowercase, as specific as possible, e.g. "paneer tikka" not "food"), '
    '"confidence" (0.0 to 1.0), '
    '"calories_per_100g", "protein_g", "carbs_g", "fat_g" '
    "(numbers per 100 g of the food as normally eaten)."
)

DEFAULT_PROMPTS: Dict[str, str] = {
    VISION_KEY: (
        "You are the NutriX food vision engine for a kitchen scale. "
        "Identify the single main food item on the scale in the image. "
        + JSON_CONTRACT
        + ' If no food is visible, set "food_name" to "unknown", "confidence" to 0 and all numbers to 0.'
    ),
    LOOKUP_KEY: (
        "You are the NutriX nutrition database engine. Given a food name, give its typical "
        "nutrition per 100 g, preferring ICMR Indian Food Composition Table values for Indian foods. "
        + JSON_CONTRACT
    ),
}

# prompt_key -> (fetched_at, text)
_cache: Dict[str, Tuple[float, str]] = {}


def get_system_prompt(key: str) -> str:
    """
    System prompt from system_prompt_registry (so Meta-Auditor patches apply without a
    restart), cached briefly, falling back to the in-code default if the DB is unavailable.
    """
    now = time.time()
    cached = _cache.get(key)
    if cached and now - cached[0] < PROMPT_CACHE_TTL_S:
        return cached[1]

    text: Optional[str] = None
    try:
        from shared.db import SessionLocal
        from shared.models import SystemPromptRegistry

        db = SessionLocal()
        try:
            row = (
                db.query(SystemPromptRegistry)
                .filter(SystemPromptRegistry.prompt_key == key, SystemPromptRegistry.is_active.is_(True))
                .first()
            )
            text = row.prompt_text if row else None
        finally:
            db.close()
    except Exception as e:
        logger.debug("Prompt registry unavailable for %s: %s", key, e)

    text = text or DEFAULT_PROMPTS[key]
    _cache[key] = (now, text)
    return text


def vision_user_prompt(weight_g: Optional[float] = None, yolo_hint: Optional[str] = None) -> str:
    parts = ["Identify the food on the scale."]
    if weight_g is not None:
        parts.append(f"The scale reads {weight_g:g} g.")
    if yolo_hint:
        parts.append(f'A detector weakly guessed "{yolo_hint}"; it may be wrong, so trust the image.')
    return " ".join(parts)


def lookup_user_prompt(food_name: str) -> str:
    return f"Food: {food_name}"
