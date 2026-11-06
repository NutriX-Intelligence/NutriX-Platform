from ms2_llm.validation import check_macros, extract_json, normalize_label, parse_nutrition

GOOD = '{"food_name": "Paneer Tikka", "confidence": 0.9, "calories_per_100g": 240, "protein_g": 14, "carbs_g": 8, "fat_g": 17}'


def test_extract_json_strips_fences_and_prose():
    text = "Sure! ```json\n" + GOOD + "\n``` hope that helps"
    assert extract_json(text)["food_name"] == "Paneer Tikka"


def test_extract_json_rejects_junk():
    assert extract_json("I cannot tell what this is") is None
    assert extract_json("{not json}") is None
    assert extract_json("") is None


def test_parse_valid_nutrition():
    r = parse_nutrition(GOOD)
    assert r["food_name"] == "paneer tikka"
    assert r["confidence"] == 0.9
    assert r["flagged"] is False
    assert r["per_100g"].calories == 240


def test_parse_unparseable_returns_none():
    assert parse_nutrition("no json here") is None


def test_unknown_label_is_flagged_without_macros():
    r = parse_nutrition('{"food_name": "unknown", "confidence": 0, "calories_per_100g": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}')
    assert r["food_name"] == "unknown" and r["flagged"] and r["per_100g"] is None


def test_missing_fields_flagged():
    r = parse_nutrition('{"food_name": "apple", "calories_per_100g": 52}')
    assert r["flagged"] and r["per_100g"] is None


def test_atwater_inconsistency_flagged_but_label_kept():
    r = parse_nutrition('{"food_name": "apple", "confidence": 0.8, "calories_per_100g": 500, "protein_g": 1, "carbs_g": 14, "fat_g": 0}')
    assert r["food_name"] == "apple"
    assert r["flagged"] and "Atwater" in r["flag_reason"]


def test_check_macros_bounds():
    assert check_macros(52, 0.3, 14, 0.2) is None
    assert check_macros(1000, 0, 0, 100) is not None          # > 900 kcal
    assert check_macros(300, 60, 60, 10) is not None           # > 100 g of macros
    assert check_macros(0, 0, 0, 0) is None                    # water-like


def test_confidence_clamped_and_label_normalised():
    r = parse_nutrition('{"food_name": "  Sweet   Lassi_ ", "confidence": 7, "calories_per_100g": 85, "protein_g": 3, "carbs_g": 14, "fat_g": 2}')
    assert r["food_name"] == "sweet lassi"
    assert r["confidence"] == 1.0
    assert normalize_label("None") == "unknown"


from ms2_llm.validation import parse_name_only


def test_parse_name_only():
    assert parse_name_only('Guava') == 'guava'
    assert parse_name_only('"a green apple."') == 'green apple'
    assert parse_name_only('unknown') == 'unknown'
    assert parse_name_only('') == 'unknown'
    assert parse_name_only('Sorry, I cannot tell what this is') == 'unknown'
    assert parse_name_only('This looks like a fresh round green fruit on a plate') == 'unknown'


from ms2_llm.validation import parse_nutrition as _parse


def test_kcal_mismatch_recomputed_from_macros_not_discarded():
    # the same numbers that were rejected in the scale log: 350 kcal vs Atwater 253
    out = _parse('{"food_name": "chocolate bar", "confidence": 0.95, "calories_per_100g": 350, "protein_g": 1.5, "carbs_g": 28, "fat_g": 15}')
    assert out['food_name'] == 'chocolate bar' and out['flagged'] is False
    assert out['per_100g'].calories == 253.0 and out['per_100g'].carbs_g == 28
    assert 'recomputed' in out['flag_reason']


def test_zero_kcal_with_real_macros_is_recomputed():
    out = _parse('{"food_name": "oreo", "confidence": 0.9, "calories_per_100g": 0, "protein_g": 5, "carbs_g": 70, "fat_g": 20}')
    assert out['per_100g'].calories == 4 * 5 + 4 * 70 + 9 * 20 and out['flagged'] is False


def test_negative_macros_still_rejected():
    out = _parse('{"food_name": "x", "confidence": 0.9, "calories_per_100g": 100, "protein_g": -5, "carbs_g": 10, "fat_g": 2}')
    assert out['flagged'] is True and out['per_100g'] is None
