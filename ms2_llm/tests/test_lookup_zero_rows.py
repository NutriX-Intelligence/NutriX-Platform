"""A food row with empty (all-zero) nutrients must not win over a complete row with the same name."""
from types import SimpleNamespace

from shared.food_lookup import _first_with_macros


def _row(code, kcal, p=0.0, c=0.0, f=0.0):
    return SimpleNamespace(food_code=code, nutrients=SimpleNamespace(energy_kcal=kcal, protein_g=p, carb_g=c, fat_g=f))


def test_complete_row_wins_over_zero_row():
    zero, full = _row('ZERO', 0.0), _row('FULL', 480.0, 5.2, 71.9, 19.6)
    assert _first_with_macros([zero, full]).food_code == 'FULL'


def test_row_without_energy_is_not_usable_even_with_macro_grams():
    # changed (FSN A2): energy_kcal null/0 means missing data -> miss -> MS2 text lookup
    assert _first_with_macros([_row('ZERO', 0.0), _row('MACROS', 0.0, 3.0)]) is None
    assert _first_with_macros([_row('NULL', None, 3.0), _row('FULL', 52.0)]).food_code == 'FULL'


def test_all_empty_rows_and_no_rows_are_a_miss():
    assert _first_with_macros([_row('A', 0.0), _row('B', 0.0)]) is None
    assert _first_with_macros([]) is None
