"""A food row with empty (all-zero) nutrients must not win over a complete row with the same name."""
from types import SimpleNamespace

from shared.food_lookup import _first_with_macros


def _row(code, kcal, p=0.0, c=0.0, f=0.0):
    return SimpleNamespace(food_code=code, nutrients=SimpleNamespace(energy_kcal=kcal, protein_g=p, carb_g=c, fat_g=f))


def test_complete_row_wins_over_zero_row():
    zero, full = _row('ZERO', 0.0), _row('FULL', 480.0, 5.2, 71.9, 19.6)
    assert _first_with_macros([zero, full]).food_code == 'FULL'


def test_macros_only_row_counts_as_complete():
    assert _first_with_macros([_row('ZERO', 0.0), _row('MACROS', 0.0, 3.0)]).food_code == 'MACROS'


def test_falls_back_to_first_row_when_all_are_empty_and_none_when_no_rows():
    assert _first_with_macros([_row('A', 0.0), _row('B', 0.0)]).food_code == 'A'
    assert _first_with_macros([]) is None
