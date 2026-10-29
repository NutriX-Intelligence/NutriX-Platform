import json
import re
from typing import Any, Dict, Optional

from ms2_llm.schemas import NutritionPer100g

UNKNOWN = "unknown"
_UNKNOWN_NAMES = {"", "unknown", "none", "n/a", "na", "null", "no food", "no food visible", "empty", "nothing"}

MAX_KCAL_PER_100G = 900.0
ATWATER_TOLERANCE = 0.25


def normalize_label(name: Any) -> str:
    label = re.sub(r"\s+", " ", str(name or "").replace("_", " ")).strip().lower()
    return UNKNOWN if label in _UNKNOWN_NAMES else label


def parse_name_only(text: Any) -> str:
    """Reduce a free-text 'what food is this?' answer to a lowercase label, or UNKNOWN (no answer, a sentence, a refusal)."""
    first = (str(text or "").strip().splitlines() or [""])[0]
    label = re.sub(r"[\"'`*.!]", "", first.strip().lower()).strip(" :-")
    label = re.sub(r"^(a|an|the)\s+", "", re.sub(r"\s+", " ", label))
    sentence = label.startswith(("i ", "this ", "it ", "there ", "the image", "image "))
    if not label or sentence or len(label.split()) > 3 or any(w in label for w in ("sorry", "cannot", "can't", "no food", "not sure")):
        return UNKNOWN
    return normalize_label(label)


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Strip markdown fences and parse the first {...} block in the model output."""
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def check_macros(kcal: float, protein: float, carbs: float, fat: float) -> Optional[str]:
    """Return a reason string if the macros are implausible, else None."""
    if min(kcal, protein, carbs, fat) < 0:
        return "negative value"
    if kcal > MAX_KCAL_PER_100G:
        return f"kcal > {MAX_KCAL_PER_100G:g} per 100g"
    if protein + carbs + fat > 100.5:
        return "protein+carbs+fat exceeds 100g per 100g"
    expected = 4 * protein + 4 * carbs + 9 * fat
    if kcal == 0:
        if expected > 5:
            return "kcal is 0 but macros are not"
    elif abs(expected - kcal) / kcal > ATWATER_TOLERANCE:
        return f"kcal {kcal:g} inconsistent with macros (Atwater estimate {expected:g})"
    return None


def parse_nutrition(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse model output into
    {"food_name", "confidence", "per_100g": NutritionPer100g|None, "flagged", "flag_reason"}.
    Returns None when the output is unparseable (caller may retry).
    """
    data = extract_json(text)
    if data is None:
        return None

    label = normalize_label(data.get("food_name"))

    conf = _num(data.get("confidence"))
    if conf is not None:
        conf = max(0.0, min(1.0, conf))

    vals = [_num(data.get(k)) for k in ("calories_per_100g", "protein_g", "carbs_g", "fat_g")]
    if label == UNKNOWN:
        return {"food_name": UNKNOWN, "confidence": conf, "per_100g": None, "flagged": True,
                "flag_reason": "no food identified"}
    if any(v is None for v in vals):
        return {"food_name": label, "confidence": conf, "per_100g": None, "flagged": True,
                "flag_reason": "missing macro fields"}

    reason = check_macros(*vals)
    per_100g = None if reason and reason == "negative value" else NutritionPer100g(
        calories=vals[0], protein_g=vals[1], carbs_g=vals[2], fat_g=vals[3]
    )
    return {"food_name": label, "confidence": conf, "per_100g": per_100g,
            "flagged": reason is not None, "flag_reason": reason}
