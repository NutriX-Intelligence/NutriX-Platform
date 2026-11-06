"""FSN A2: a capture with no trustworthy macros must not be logged as a real 0 kcal meal."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import ms1_cv.main as m1
from shared.db import get_db
from shared.models import Food, FoodAlias, FoodNutrient, MealLog, User


class _FakeEngine:
    """YOLO stand-in: always below threshold, so the frame goes to the (mocked) VLM."""
    def process_scale_event(self, image_path, current_weight, session):
        return False, {"status": "unidentified", "reason": "low confidence", "fallback_class": "chocolate", "fallback_conf": 0.2}


@pytest.fixture()
def env(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    for model in (User, Food, FoodNutrient, FoodAlias, MealLog):
        model.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(User(id=1, name="t", email="t@x"))
    db.commit()

    def _get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    m1.app.dependency_overrides[get_db] = _get_db
    monkeypatch.setattr(m1, "_engine", _FakeEngine())
    monkeypatch.setattr(m1, "_resolve_scale_user", lambda db, uid: 1)   # user/profile tables are not under test
    monkeypatch.setattr(m1, "LATEST_RAW_PATH", str(tmp_path / "raw.jpg"))
    monkeypatch.setattr(m1, "LATEST_ANNOTATED_PATH", str(tmp_path / "ann.jpg"))
    monkeypatch.setattr(m1, "CAPTURE_LOG_DIR", str(tmp_path / "log"))
    monkeypatch.setattr(m1, "sync_daily_macros", lambda db, uid: {"date": "x", "calories": 0.0})
    calls = {"lookup": 0}
    state = {"vision": None, "lookup": None}

    async def vision_infer(*a, **k):
        return state["vision"]

    async def lookup(*a, **k):
        calls["lookup"] += 1
        return state["lookup"]

    monkeypatch.setattr(m1.llm_client, "vision_infer", vision_infer)
    monkeypatch.setattr(m1.llm_client, "lookup", lookup)
    yield db, state, calls
    m1.app.dependency_overrides.pop(get_db, None)
    db.close()


def _post(weight=50.0):
    c = TestClient(m1.app)
    return c.post("/api/v1/ingest/weight-frame", data={"weight": str(weight)},
                  files={"image": ("f.jpg", b"not-a-real-jpeg", "image/jpeg")}, headers={"x-user-id": "1"}).json()


def _add(db, name, kcal, p=0, c=0, f=0):
    food = Food(food_code=f"T_{name}", name=name, brand=None)
    food.nutrients = FoodNutrient(energy_kcal=kcal, protein_g=p, carb_g=c, fat_g=f)
    db.add(food)
    db.commit()


def test_flagged_vlm_and_flagged_lookup_is_marked_no_nutrition_data(env):
    """The demo 'Chocolate Bar' path: both Qwen calls flagged, no DB row."""
    db, state, _ = env
    state["vision"] = {"food_name": "chocolate bar", "confidence": 0.8, "per_100g": {"calories": 350, "protein_g": 1.5, "carbs_g": 28, "fat_g": 15}, "flagged": True}
    state["lookup"] = {"per_100g": {"calories": 450, "protein_g": 1, "carbs_g": 25, "fat_g": 15}, "flagged": True}
    out = _post()
    assert out["macro_source"] == "no_nutrition_data" and out["calories"] == 0.0
    row = db.query(MealLog).one()
    assert row.food_name == "Chocolate Bar" and row.source == "no_nutrition_data"


def test_zero_energy_db_row_goes_to_ms2_lookup(env):
    """The demo 'Oreo' path: an all-zero DB row used to be a 'db' hit logged as 0 kcal."""
    db, state, calls = env
    _add(db, "Oreo", 0)
    state["vision"] = {"food_name": "oreo", "confidence": 0.8, "per_100g": None, "flagged": True}
    state["lookup"] = {"per_100g": {"calories": 480, "protein_g": 5, "carbs_g": 70, "fat_g": 20}, "flagged": False, "source": "qwen3-vl-2b"}
    out = _post(10.0)
    assert calls["lookup"] == 1
    assert out["macro_source"] == "qwen3-vl-2b" and out["calories"] == 48.0
    assert db.query(MealLog).one().source == "esp32_qwen_vlm"


def test_ms2_zero_kcal_answer_is_not_trusted(env):
    db, state, _ = env
    state["vision"] = {"food_name": "chocolate bar", "confidence": 0.8, "per_100g": {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}, "flagged": False}
    state["lookup"] = {"per_100g": {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}, "flagged": False}
    assert _post()["macro_source"] == "no_nutrition_data"
    assert db.query(Food).count() == 0          # the empty estimate is not persisted either


def test_timeout_keeps_llm_timeout_source(env):
    db, state, _ = env
    state["vision"] = {"food_name": "chocolate bar", "confidence": 0.8, "per_100g": None, "flagged": True}
    state["lookup"] = None
    assert _post()["macro_source"] == "llm-timeout"
    assert db.query(MealLog).one().source == "llm-timeout"


def test_real_db_hit_is_unchanged(env):
    db, state, calls = env
    _add(db, "Oreo", 483, 5.2, 71.9, 19.6)
    state["vision"] = {"food_name": "oreo", "confidence": 0.8, "per_100g": None, "flagged": True}
    out = _post(10.0)
    assert out["macro_source"] == "db" and out["calories"] == 48.3 and calls["lookup"] == 0
    assert db.query(MealLog).one().source == "esp32_qwen_vlm"


def test_capture_record_written_per_meal_log(env):
    import json
    import os
    db, state, _ = env
    state["vision"] = {"food_name": "chocolate bar", "confidence": 0.8, "per_100g": None, "flagged": True, "flag_reason": "x"}
    state["lookup"] = {"per_100g": {"calories": 500, "protein_g": 5, "carbs_g": 60, "fat_g": 28}, "flagged": False, "source": "qwen3-vl-2b"}
    _post(20.0)
    row = db.query(MealLog).one()
    rec = json.load(open(os.path.join(m1.CAPTURE_LOG_DIR, f"{row.id}.json")))
    assert rec["meal_log_id"] == row.id and rec["yolo_status"] == "unidentified"
    assert rec["yolo_conf"] == 0.2 and rec["vlm"]["food_name"] == "chocolate bar" and rec["identified_by"] == "qwen"
    assert rec["calories"] == 100.0 and rec["macro_source"] == "qwen3-vl-2b"
    assert rec["image_path"] and os.path.exists(rec["image_path"])


def test_meal_log_source_mapping():
    assert m1.meal_log_source("db", "yolo") == "esp32_yolo"
    assert m1.meal_log_source("qwen3-vl-2b", "qwen") == "esp32_qwen_vlm"
    assert m1.meal_log_source("no_nutrition_data", "qwen") == "no_nutrition_data"
    assert m1.meal_log_source("llm-timeout", "qwen") == "llm-timeout"
