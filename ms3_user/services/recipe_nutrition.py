"""
Structured name + macros for an AI-generated recipe.

The model is asked to end its answer with one fenced JSON block of per-serving numbers. `extract` parses and validates it
(falling back to the figures written in the recipe text), removes the block from the text shown to the user, and never
invents numbers: anything missing or implausible comes back as None so the app can leave the field empty instead of
showing junk.
"""
import json
import re
from typing import Any, Dict, Optional

MACHINE_BLOCK_INSTRUCTION = (
    "\n\nAfter the recipe, end your answer with ONE fenced json block and nothing after it, exactly in this shape, using "
    "realistic numbers for ONE serving (never zeros):\n"
    '```json\n{"name": "<recipe name>", "servings": 2, "per_serving": {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}}\n```'
)

_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S | re.I)
MAX_KCAL_PER_SERVING = 3000.0
MAX_MACRO_GRAMS = 500.0
ATWATER_TOLERANCE = 0.35

_TEXT_PATTERNS = {
    "calories": re.compile(r"(?:total\s+)?calories?[^0-9\n]{0,30}(\d{2,4}(?:\.\d+)?)", re.I),
    "protein_g": re.compile(r"protein[^0-9\n]{0,30}(\d+(?:\.\d+)?)\s*g", re.I),
    "carbs_g": re.compile(r"carb(?:ohydrate)?s?[^0-9\n]{0,30}(\d+(?:\.\d+)?)\s*g", re.I),
    "fat_g": re.compile(r"\bfats?\b[^0-9\n]{0,30}(\d+(?:\.\d+)?)\s*g", re.I),
}
# a broken or truncated machine block at the very end (invalid JSON, or the model stopped mid-block) must not reach the user
_TRAILING_BLOCK = re.compile(r"\s*```(?:json)?\s*\{[^`]*(?:```)?\s*$", re.I)
_NAME_LINE = re.compile(r"(?im)^\s*[#*\s>-]*recipe\s*name\s*[:*\s-]*\s*(.+?)\s*$")
_HEADING = re.compile(r"(?m)^\s*#{1,3}\s*(.+?)\s*$")


def _num(value: Any) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f >= 0 else None


def _clean_name(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    name = re.sub(r"[*_#`>]+", "", str(raw)).strip(" :-–—\t")
    name = re.sub(r"^[^\w(]+", "", name).strip()          # leading emoji / symbols
    return name[:80] or None


def _split_block(text: str):
    """(text without the machine block, parsed dict or None). The LAST block that parses wins."""
    for match in reversed(list(_BLOCK.finditer(text))):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return (text[: match.start()] + text[match.end():]).rstrip() + "\n", data
    return text, None


def _from_text(text: str) -> Dict[str, Optional[float]]:
    found: Dict[str, Optional[float]] = {}
    for key, pattern in _TEXT_PATTERNS.items():
        matches = pattern.findall(text)
        found[key] = _num(matches[-1]) if matches else None   # the closing "total" section wins over per-ingredient lines
    return found


def _plausible(values: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    cal, p, c, f = (values.get(k) for k in ("calories", "protein_g", "carbs_g", "fat_g"))
    if cal is not None and cal > MAX_KCAL_PER_SERVING:
        return {k: None for k in values}
    if sum(v for v in (p, c, f) if v is not None) > MAX_MACRO_GRAMS:
        return {k: None for k in values}
    return values


def extract(text: str) -> Dict[str, Any]:
    """{"recipe": visible text, "name", "servings", "nutrition": {...} | None}"""
    visible, block = _split_block(text or "")
    if _TRAILING_BLOCK.search(visible):
        visible = _TRAILING_BLOCK.sub("", visible).rstrip() + "\n"
    name = servings = None
    values: Dict[str, Optional[float]] = {"calories": None, "protein_g": None, "carbs_g": None, "fat_g": None}
    basis = None

    if block:
        per = block.get("per_serving") if isinstance(block.get("per_serving"), dict) else block
        from_block = {k: _num(per.get(k)) for k in values}
        if any(v for v in from_block.values()):                # an all-zero block is a template, not an answer
            values, basis = from_block, "ai_block"
        name = _clean_name(block.get("name"))
        s = _num(block.get("servings"))
        servings = int(s) if s and 1 <= s <= 20 else None

    if all(v is None for v in values.values()):
        parsed = _from_text(visible)
        if any(v for v in parsed.values()):
            values, basis = parsed, "parsed_text"

    values = _plausible(values)
    nutrition = None
    if any(v is not None for v in values.values()):
        cal, p, c, f = (values[k] for k in ("calories", "protein_g", "carbs_g", "fat_g"))
        consistent = None
        if None not in (cal, p, c, f) and cal:
            consistent = abs((4 * p + 4 * c + 9 * f) - cal) / cal <= ATWATER_TOLERANCE
        nutrition = {**{k: (round(v, 1) if v is not None else None) for k, v in values.items()},
                     "per": "serving", "basis": basis, "consistent": consistent}

    if not name:
        m = _NAME_LINE.search(visible) or _HEADING.search(visible)
        name = _clean_name(m.group(1)) if m else None
    return {"recipe": visible, "name": name, "servings": servings, "nutrition": nutrition}
