"""Barcode lookup never returns a "null" product name (a Gemini answer of the string "null" used to be cached and logged as "null (coca cola)")."""
import json

import pytest

from shared import models
from shared.db import SessionLocal
from ms3_user.services import gemini_client
from ms3_user.services.barcode_service import BarcodeService

CODE = "9990000000017"


@pytest.mark.parametrize("value", [None, "", "  ", "null", "NULL", "None", "n/a", "Unknown", "undefined"])
def test_placeholder_names_are_not_names(value):
    assert BarcodeService.clean_name(value) is None


def test_real_names_are_kept_and_trimmed():
    assert BarcodeService.clean_name("  Sprite   Lemon-Lime ") == "Sprite Lemon-Lime"


@pytest.fixture
def db():
    s = SessionLocal()
    s.query(models.BarcodeCache).filter(models.BarcodeCache.barcode == CODE).delete()
    s.commit()
    yield s
    s.query(models.BarcodeCache).filter(models.BarcodeCache.barcode == CODE).delete()
    s.commit()
    s.close()


def _no_network(monkeypatch, gemini_answer):
    monkeypatch.setattr(BarcodeService, "fetch_from_open_food_facts", classmethod(lambda cls, b: None))
    monkeypatch.setattr(BarcodeService, "scrape_product_name_from_search", classmethod(lambda cls, b: None))
    monkeypatch.setattr(gemini_client, "is_configured", lambda: True)
    monkeypatch.setattr(gemini_client, "generate_json", lambda *a, **k: gemini_answer)


def test_gemini_null_name_falls_back_to_brand(db, monkeypatch):
    _no_network(monkeypatch, {"product_name": "null", "brand": "Coca Cola", "energy_kcal": 40.0, "protein_g": 0.0,
                              "carb_g": 10.0, "fat_g": 0.0, "nutrition_grade": "e"})
    out = BarcodeService.get_product(db, CODE)

    assert out["product_name"] != "null" and "null" not in out["product_name"].lower()
    assert out["product_name"] == "Coca Cola product" and out["brand"] == "Coca Cola"


def test_gemini_real_name_is_used(db, monkeypatch):
    _no_network(monkeypatch, {"product_name": "Sprite Lemon-Lime 250 ml", "brand": "Coca-Cola", "energy_kcal": 40.0,
                              "protein_g": 0.0, "carb_g": 10.0, "fat_g": 0.0})
    assert BarcodeService.get_product(db, CODE)["product_name"] == "Sprite Lemon-Lime 250 ml"


def test_cached_row_with_null_name_is_resolved_again(db, monkeypatch):
    db.add(models.BarcodeCache(barcode=CODE, product_name="null", brand="Coca Cola", ingredients_text="",
                               nutrition_grade="e", nutriments_json=json.dumps({"energy_kcal": 40.0, "carb_g": 10.0}),
                               health_score=10, health_category="E", source_detail="old"))
    db.commit()
    _no_network(monkeypatch, {"product_name": "Sprite Lemon-Lime", "brand": "Coca-Cola", "energy_kcal": 40.0,
                              "protein_g": 0.0, "carb_g": 10.0, "fat_g": 0.0})

    assert BarcodeService.get_product(db, CODE)["product_name"] == "Sprite Lemon-Lime"
