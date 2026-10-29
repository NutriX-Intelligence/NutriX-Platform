"""
Is this recipe something a person would actually eat as a meal in this slot?

The recipe library is a food-composition table, so besides dishes it holds spice mixes (Garam masala, Rasam powder), condiments
(chutneys, pickles, sauces, mayonnaise), preserves (jam, squash, syrup), stocks, and a number of rows whose "per serving" calories are
a whole-batch figure (e.g. Paneer pulao 4,876 kcal). Left alone, the meal planner happily picks them: a plan once offered Rasam powder as
dinner and a 1,553 kcal chutney as a snack.

`is_plan_candidate` is the gate the planner applies to every candidate.
"""
import re
from typing import Optional

# per single serving, by slot: (min kcal, max kcal). Outside this range the figure is a condiment-sized scrap or a whole-batch total.
KCAL_LIMITS = {
    "Breakfast": (80.0, 900.0),
    "Lunch": (100.0, 1100.0),
    "Dinner": (100.0, 1100.0),
    "Snack": (40.0, 600.0),
}
_DEFAULT_LIMITS = (80.0, 1100.0)

_PAREN = re.compile(r"\s*\([^)]*\)\s*")
# a name that says "<dish> with/in <something>" is a dish even if it ends with a condiment word ("baked fish with cheese sauce")
_DISH_MARKER = re.compile(r"\b(with|in)\b")
_CONDIMENT_ENDING = re.compile(
    r"\b(chutney|chatni|thokku|pachadi|pickle|pickled|achar|achaar|murabba|marmalade|jam|jelly|squash|cordial|syrup|"
    r"sauce|ketchup|dip|dressing|mayonnaise|relish|spread|paste|stock|broth|powder|podi|blend|seasoning|"
    r"(?:garam|chaat|chat|kashmiri|pav\s*bhaji|biryani|tandoori|sambar|rasam|kitchen\s*king|goda|tea|chai)\s+masala|panch\s*phoran|panch\s*phoron)$",
    re.I,
)


def is_condiment_or_mix(name: Optional[str]) -> bool:
    """True for spice mixes, chutneys, pickles, sauces, stocks, jams... (judged on the name without its parenthetical alias)."""
    base = _PAREN.sub(" ", name or "").strip().lower()
    if not base:
        return False
    if _DISH_MARKER.search(base):
        return False
    if base.startswith("pickled "):          # "Pickled mustard greens": a pickle named by its state, not its last word
        return True
    return bool(_CONDIMENT_ENDING.search(base))


def is_plan_candidate(name: Optional[str], kcal: Optional[float], slot: str, user_made: bool = False) -> bool:
    """Name and calorie sanity for one slot. `user_made` (a homely meal the user entered) skips the name rule, not the calorie one."""
    low, high = KCAL_LIMITS.get(slot, _DEFAULT_LIMITS)
    if kcal is None or not (low <= float(kcal) <= high):
        return False
    return user_made or not is_condiment_or_mix(name)
