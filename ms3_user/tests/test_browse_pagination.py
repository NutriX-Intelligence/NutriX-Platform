"""Browse Recipes: real paging (X-Total-Count / X-Has-More), exclude_fast_food, and condiments hidden unless searched for."""
import pytest
from fastapi.testclient import TestClient

from ms3_user.main import app
from shared import models
from shared.db import SessionLocal

client = TestClient(app)
PREFIX = "BRWS"


def _nutrition(code):
    return models.RecipeNutrition(recipe_code=code, energy_kcal=300.0, protein_g=12.0, carb_g=40.0, fat_g=8.0,
                                  unit_serving_energy_kcal=300.0, unit_serving_protein_g=12.0, unit_serving_carb_g=40.0, unit_serving_fat_g=8.0)


@pytest.fixture(scope="module")
def library():
    db = SessionLocal()
    rows = [(f"{PREFIX}_D{i:02d}", f"Brwsdish paneer {i}", None) for i in range(9)]
    rows += [(f"{PREFIX}_C1", "Brws garam masala", None), (f"{PREFIX}_C2", "Brws coconut chutney (Nariyal ki chutney)", None),
             (f"FF_{PREFIX}_1", "Brws crispy burger", "KFC")]
    for code, name, brand in rows:
        db.add(models.Recipe(recipe_code=code, recipe_name=name, category="Lunch/Dinner", brand=brand))
        db.add(_nutrition(code))
    db.commit()
    yield
    codes = [c for (c,) in db.query(models.Recipe.recipe_code).filter(models.Recipe.recipe_code.like(f"%{PREFIX}%")).all()]
    db.query(models.RecipeNutrition).filter(models.RecipeNutrition.recipe_code.in_(codes)).delete(synchronize_session=False)
    db.query(models.Recipe).filter(models.Recipe.recipe_code.in_(codes)).delete(synchronize_session=False)
    db.commit()
    db.close()


@pytest.fixture(scope="module")
def account(library):
    r = client.post("/api/v1/auth/register", json={"email": "browse@example.com", "password": "secret123", "name": "Browse User"})
    assert r.status_code == 201, r.text
    body = r.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}


def _post(account, **params):
    uid, headers = account
    return client.post("/api/v1/foods/recommend", json={"user_id": uid, **params}, headers=headers)


def _mine(rows):
    return {r["recipe_code"] for r in rows if PREFIX in r["recipe_code"]}


def test_page_headers_describe_the_whole_catalogue(account):
    full = _post(account, limit=2000)
    total = len(full.json())
    assert full.status_code == 200 and full.headers["X-Total-Count"] == str(total) and full.headers["X-Has-More"] == "false"

    page = _post(account, limit=5, offset=0)
    assert len(page.json()) == 5 and page.headers["X-Total-Count"] == str(total)
    assert page.headers["X-Page-Offset"] == "0" and page.headers["X-Has-More"] == "true"

    last = _post(account, limit=5, offset=total - 3)
    assert len(last.json()) == 3 and last.headers["X-Has-More"] == "false"


def test_pages_do_not_overlap_and_cover_everything(account):
    seen, offset = [], 0
    while True:
        r = _post(account, limit=7, offset=offset)
        seen += [x["recipe_code"] for x in r.json()]
        if r.headers["X-Has-More"] == "false":
            break
        offset += 7
    assert len(seen) == len(set(seen)) == int(r.headers["X-Total-Count"])


def test_default_page_is_bigger_than_the_old_60():
    from ms3_user import schemas
    assert schemas.RecommendFoodsRequest(user_id=1).limit == 300


def test_condiments_are_hidden_when_browsing_but_found_when_searched(account):
    browsing = _mine(_post(account, limit=2000).json())
    assert f"{PREFIX}_C1" not in browsing and f"{PREFIX}_C2" not in browsing
    assert {f"{PREFIX}_D{i:02d}" for i in range(9)} <= browsing

    assert f"{PREFIX}_C1" in _mine(_post(account, limit=2000, query="garam masala").json())
    assert f"{PREFIX}_C2" in _mine(_post(account, limit=2000, query="chutney").json())


def test_exclude_fast_food_removes_branded_items_and_keeps_the_rest(account):
    with_ff = _mine(_post(account, limit=2000).json())
    without = _post(account, limit=2000, exclude_fast_food=True)
    assert f"FF_{PREFIX}_1" in with_ff
    assert f"FF_{PREFIX}_1" not in _mine(without.json()) and {f"{PREFIX}_D{i:02d}" for i in range(9)} <= _mine(without.json())
    assert all(not r["recipe_code"].startswith("FF_") for r in without.json())
    assert int(without.headers["X-Total-Count"]) < int(_post(account, limit=2000).headers["X-Total-Count"])
