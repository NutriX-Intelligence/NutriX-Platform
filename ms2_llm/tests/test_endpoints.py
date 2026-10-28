import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ms2_llm import main as ms2
from ms2_llm.tests.conftest import add_food
from ms2_llm.vlm_engine import VLMNotAvailable
from shared.db import get_db

APPLE = json.dumps({"food_name": "Apple", "confidence": 0.93, "calories_per_100g": 52,
                    "protein_g": 0.3, "carbs_g": 14, "fat_g": 0.2})
MAKHANI = json.dumps({"food_name": "murgh makhani", "confidence": 0.7, "calories_per_100g": 150,
                      "protein_g": 11, "carbs_g": 8, "fat_g": 8})


@pytest.fixture()
def client(db, monkeypatch):
    ms2.app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(ms2, "log_audit_event", lambda **kw: None)       # never touch the real audit_logs
    monkeypatch.setattr(ms2.prompts, "get_system_prompt", lambda key: "system")
    yield TestClient(ms2.app)                                             # no `with`: lifespan (GPU load) is not run
    ms2.app.dependency_overrides.clear()


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 30, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def _vision(client, **data):
    return client.post("/api/v1/llm/vision-infer", files={"image": ("f.jpg", _jpeg(), "image/jpeg")},
                       data={"weight": "180", **data})


def test_vision_infer_returns_label_and_macros(client, monkeypatch):
    seen = {}

    def fake_infer(system, user, image=None, max_new_tokens=None):
        seen["user"], seen["has_image"] = user, image is not None
        return "```json\n" + APPLE + "\n```"

    monkeypatch.setattr(ms2.engine, "infer", fake_infer)
    r = _vision(client, yolo_hint="mango")

    assert r.status_code == 200
    body = r.json()
    assert body["food_name"] == "apple" and body["per_100g"]["calories"] == 52
    assert body["flagged"] is False and body["source"] == "qwen3-vl-2b"
    assert seen["has_image"] and "mango" in seen["user"] and "180" in seen["user"]


def test_vision_infer_retries_once_then_gives_unknown(client, monkeypatch):
    calls = []
    monkeypatch.setattr(ms2.engine, "infer", lambda *a, **k: calls.append(1) or "I see a plate")
    body = _vision(client).json()

    assert len(calls) == 2
    assert body["food_name"] == "unknown" and body["flagged"] is True


def test_vision_infer_rejects_bad_image(client):
    r = client.post("/api/v1/llm/vision-infer", files={"image": ("f.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 400


def test_vision_infer_503_when_model_unavailable(client, monkeypatch):
    def boom(*a, **k):
        raise VLMNotAvailable("no weights")

    monkeypatch.setattr(ms2.engine, "infer", boom)
    r = _vision(client)
    assert r.status_code == 503 and r.json()["detail"]["source"] == "llm-unavailable"


def test_lookup_db_hit_never_calls_the_model(client, db, monkeypatch):
    add_food(db, "Apple", 52, 0.3, 14, 0.2)
    monkeypatch.setattr(ms2.engine, "infer", lambda *a, **k: pytest.fail("model should not be called"))

    body = client.post("/api/v1/llm/lookup", json={"food_name": "apple"}).json()
    assert body["source"] == "db" and body["per_100g"]["calories"] == 52


def test_lookup_miss_calls_model_and_persists(client, db, monkeypatch):
    monkeypatch.setattr(ms2.engine, "infer", lambda *a, **k: MAKHANI)

    first = client.post("/api/v1/llm/lookup", json={"food_name": "Murgh Makhani"}).json()
    assert first["source"] == "qwen3-vl-2b" and first["per_100g"]["calories"] == 150

    monkeypatch.setattr(ms2.engine, "infer", lambda *a, **k: pytest.fail("second lookup must hit the DB"))
    second = client.post("/api/v1/llm/lookup", json={"food_name": "murgh makhani"}).json()
    assert second["source"] == "db"


def test_lookup_flagged_result_is_not_persisted(client, db, monkeypatch):
    bad = json.dumps({"food_name": "x", "confidence": 1, "calories_per_100g": 800, "protein_g": 1,
                      "carbs_g": 1, "fat_g": 1})
    monkeypatch.setattr(ms2.engine, "infer", lambda *a, **k: bad)

    body = client.post("/api/v1/llm/lookup", json={"food_name": "mystery paste"}).json()
    assert body["flagged"] is True
    monkeypatch.setattr(ms2.engine, "infer", lambda *a, **k: "no json")
    assert client.post("/api/v1/llm/lookup", json={"food_name": "mystery paste"}).json()["source"] != "db"


def test_generate_returns_text_and_passes_system_and_limits(client, monkeypatch):
    seen = {}

    def fake_infer(system, user, image=None, max_new_tokens=None):
        seen.update(system=system, user=user, image=image, max_new_tokens=max_new_tokens)
        return "  1. Eat dal.  "

    monkeypatch.setattr(ms2.engine, "infer", fake_infer)
    r = client.post("/api/v1/llm/generate", json={"prompt": "Protein snack?", "system": "Be brief", "max_new_tokens": 100})
    assert r.status_code == 200
    assert r.json()["text"] == "1. Eat dal." and r.json()["source"] == "qwen3-vl-2b"
    assert seen == {"system": "Be brief", "user": "Protein snack?", "image": None, "max_new_tokens": 100}


def test_generate_uses_a_default_system_prompt_and_validates_input(client, monkeypatch):
    monkeypatch.setattr(ms2.engine, "infer", lambda system, user, image=None, max_new_tokens=None: system[:20])
    assert client.post("/api/v1/llm/generate", json={"prompt": "hi"}).json()["text"].startswith("You are NutriX")
    assert client.post("/api/v1/llm/generate", json={"prompt": ""}).status_code == 422
    assert client.post("/api/v1/llm/generate", json={"prompt": "x", "max_new_tokens": 99999}).status_code == 422


def test_generate_503_when_model_unavailable(client, monkeypatch):
    def boom(*a, **k):
        raise VLMNotAvailable("no weights")

    monkeypatch.setattr(ms2.engine, "infer", boom)
    assert client.post("/api/v1/llm/generate", json={"prompt": "hi"}).status_code == 503
