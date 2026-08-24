import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from shared.models import (
    Base, User, Profile, Food, FoodNutrient, Recipe, RecipeNutrition,
    RecipeIngredient, Serving, HomelyMeal, HomelyMealIngredient,
    UserAdapter, AuditLog, ClinicalAlert, ClinicalReport, SystemPromptRegistry
)
from shared.health import check_health, check_database, check_redis
from shared.redis_client import set_daily_macros, get_daily_macros, invalidate_daily_macros
from shared.audit import log_audit_event, compute_input_hash

# In-memory SQLite engine for fast, isolated unit tests
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, echo=False)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

def test_all_34_tables_registered():
    tables = Base.metadata.tables.keys()
    assert len(tables) >= 34
    expected_tables = [
        "users", "profiles", "user_preferences", "goals", "foods",
        "food_nutrients", "recipes",
        "recipe_ingredients", "recipe_nutrition", "recipe_steps", "servings",
        "ingredient_rules", "meal_logs", "water_logs", "weight_logs",
        "barcode_cache", "recommendation_history", "health_scores", "analytics",
        "generated_meal_plans", "unit_conversions", "homely_meals", "homely_meal_ingredients",
        "homely_meal_nutrition", "homely_meal_versions", "homely_meal_reviews",
        "homely_meal_tags", "search_history", "settings",
        # 5 new NutriX tables
        "user_adapters", "audit_logs", "clinical_alerts", "clinical_reports", "system_prompt_registry"
    ]
    for table_name in expected_tables:
        assert table_name in tables, f"Missing table {table_name}"

def test_user_and_profile_relationship(db):
    user = User(name="Harsh Patel", email="harsh@nutrix.ai")
    profile = Profile(age=24, gender="Male", height=175.0, weight=70.0, goal="muscle_gain")
    user.profile = profile
    db.add(user)
    db.commit()

    saved_user = db.query(User).filter_by(email="harsh@nutrix.ai").first()
    assert saved_user is not None
    assert saved_user.profile.age == 24
    assert saved_user.profile.height == 175.0

def test_food_and_nutrients_relationship(db):
    food = Food(food_code="TEST_PANEER_01", name="Paneer Raw", brand="Amul")
    nutrients = FoodNutrient(energy_kcal=265.0, protein_g=18.0, fat_g=20.0, carb_g=1.2)
    food.nutrients = nutrients
    db.add(food)
    db.commit()

    saved_food = db.query(Food).filter_by(food_code="TEST_PANEER_01").first()
    assert saved_food is not None
    assert saved_food.nutrients.protein_g == 18.0
    assert saved_food.nutrients.energy_kcal == 265.0

def test_user_adapter_creation(db):
    user = User(name="CV User", email="cv@nutrix.ai")
    db.add(user)
    db.commit()

    adapter = UserAdapter(
        user_id=user.id,
        weights_path="adapters/user_cv_head_v1.pt",
        adapter_version=1,
        num_classes=123,
        class_mappings={"0": "paneer_tikka", "1": "roti"}
    )
    db.add(adapter)
    db.commit()

    saved_adapter = db.query(UserAdapter).filter_by(user_id=user.id).first()
    assert saved_adapter is not None
    assert saved_adapter.weights_path == "adapters/user_cv_head_v1.pt"
    assert saved_adapter.class_mappings["0"] == "paneer_tikka"

def test_audit_logging_and_hash(db):
    log_id = log_audit_event(
        service="ms1",
        operation="yolo_inference",
        user_id=1,
        input_data={"image_path": "/tmp/thali.jpg"},
        output_data={"detections": [{"class": "roti", "conf": 0.94}]},
        confidence=0.94,
        latency_ms=45,
        db=db
    )
    assert log_id is not None
    audit_entry = db.query(AuditLog).filter_by(id=log_id).first()
    assert audit_entry is not None
    assert audit_entry.service == "ms1"
    assert audit_entry.confidence == 0.94
    assert len(audit_entry.input_hash) == 64  # SHA256 hex string length

def test_redis_macros_cache_and_fallback():
    user_id = 999
    date_str = "2026-08-08"
    sample_macros = {"calories": 1850.0, "protein": 110.0, "carbs": 190.0, "fat": 55.0}

    # Set
    success = set_daily_macros(user_id, date_str, sample_macros)
    assert success is True

    # Get
    cached = get_daily_macros(user_id, date_str)
    assert cached is not None
    assert cached["calories"] == 1850.0
    assert cached["protein"] == 110.0

    # Invalidate
    inv_success = invalidate_daily_macros(user_id, date_str)
    assert inv_success is True
    assert get_daily_macros(user_id, date_str) is None

def test_health_check_module(db):
    health = check_health(service_name="ms3_user", db=db, include_redis=True)
    assert "status" in health
    assert health["service"] == "ms3_user"
    assert "database" in health["checks"]
    assert health["checks"]["database"]["status"] == "ok"
