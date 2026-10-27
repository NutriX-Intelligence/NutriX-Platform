import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.models import Food, FoodAlias, FoodNutrient


@pytest.fixture()
def db():
    """In-memory SQLite with only the food tables (no Postgres needed)."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    for model in (Food, FoodNutrient, FoodAlias):
        model.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def add_food(db, name, kcal, p, c, f, brand="Whole Food", aliases=()):
    food = Food(food_code=f"T_{name}", name=name, brand=brand)
    food.nutrients = FoodNutrient(energy_kcal=kcal, protein_g=p, carb_g=c, fat_g=f)
    db.add(food)
    db.flush()
    for a in aliases:
        db.add(FoodAlias(food_id=food.id, alias_name=a))
    db.commit()
    return food
