"""Central Gemini client: key handling, model fallback, retries, cooldown, and graceful degradation of the AI routes."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from ms3_user.main import app
from ms3_user.services import gemini_client
from ms3_user.services.barcode_service import BarcodeService
from ms3_user.services.ocr_engine import OCREngine

client = TestClient(app)


def _ok(text: str) -> httpx.Response:
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


@pytest.fixture(autouse=True)
def gemini_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    monkeypatch.setenv("GEMINI_MODEL", "model-a")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "model-b,model-c")
    monkeypatch.setattr(gemini_client.time, "sleep", lambda s: None)
    gemini_client.reset_state()
    yield
    monkeypatch.setattr(gemini_client, "_transport", None)
    gemini_client.reset_state()


def _use(monkeypatch, handler):
    calls = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    monkeypatch.setattr(gemini_client, "_transport", httpx.MockTransport(wrapped))
    return calls


def _model_of(request: httpx.Request) -> str:
    return request.url.path.split("/models/")[1].split(":")[0]


# ── configuration / request shape ────────────────────────────────────────────
def test_not_configured_raises_without_any_http(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    for legacy in ("GEMINI_3_6_API_KEY", "GEMINI_API_KEY_1"):
        monkeypatch.delenv(legacy, raising=False)
    calls = _use(monkeypatch, lambda r: _ok("x"))
    assert gemini_client.is_configured() is False
    with pytest.raises(gemini_client.GeminiError) as e:
        gemini_client.generate("hi")
    assert e.value.kind == "not_configured" and calls == []


def test_key_is_sent_as_a_header_never_in_the_url(monkeypatch):
    calls = _use(monkeypatch, lambda r: _ok("hello"))
    assert gemini_client.generate("hi") == "hello"
    req = calls[0]
    assert req.headers["x-goog-api-key"] == "test-key-123"
    assert "test-key-123" not in str(req.url) and "key=" not in str(req.url)


def test_payload_has_system_instruction_json_mode_temperature_and_image(monkeypatch):
    calls = _use(monkeypatch, lambda r: _ok("{}"))
    gemini_client.generate("describe", system="be brief", json_mode=True, temperature=0.1, image_bytes=b"\x89PNG", mime_type="image/png")
    body = json.loads(calls[0].content)
    assert body["systemInstruction"]["parts"][0]["text"] == "be brief"
    assert body["generationConfig"] == {"responseMimeType": "application/json", "temperature": 0.1}
    parts = body["contents"][0]["parts"]
    assert parts[0]["text"] == "describe" and parts[1]["inline_data"]["mime_type"] == "image/png"


def test_multi_turn_contents_are_passed_through(monkeypatch):
    calls = _use(monkeypatch, lambda r: _ok("ok"))
    history = [{"role": "user", "parts": [{"text": "a"}]}, {"role": "model", "parts": [{"text": "b"}]}]
    gemini_client.generate(contents=history)
    assert json.loads(calls[0].content)["contents"] == history


# ── model fallback / retries ─────────────────────────────────────────────────
def test_unknown_model_falls_through_to_the_next(monkeypatch):
    calls = _use(monkeypatch, lambda r: httpx.Response(404, json={}) if _model_of(r) == "model-a" else _ok("from b"))
    assert gemini_client.generate("hi") == "from b"
    assert [_model_of(c) for c in calls] == ["model-a", "model-b"]


def test_overloaded_503_moves_straight_to_the_next_model(monkeypatch):
    calls = _use(monkeypatch, lambda r: httpx.Response(503, json={"error": {"message": "high demand"}}) if _model_of(r) == "model-a" else _ok("from b"))
    assert gemini_client.generate("hi") == "from b"
    assert [_model_of(c) for c in calls] == ["model-a", "model-b"]          # no pointless second try on the overloaded model


def test_transient_500_is_retried_on_the_same_model(monkeypatch):
    state = {"n": 0}

    def handler(r):
        state["n"] += 1
        return httpx.Response(500) if state["n"] == 1 else _ok("recovered")

    calls = _use(monkeypatch, handler)
    assert gemini_client.generate("hi") == "recovered"
    assert [_model_of(c) for c in calls] == ["model-a", "model-a"]


def test_slow_model_read_timeout_falls_through_to_the_next_model(monkeypatch):
    def handler(r):
        if _model_of(r) == "model-a":
            raise httpx.ReadTimeout("slow")
        return _ok("from b")

    calls = _use(monkeypatch, handler)
    assert gemini_client.generate("hi") == "from b"
    assert [_model_of(c) for c in calls] == ["model-a", "model-b"]


def test_connect_failure_still_stops_everything(monkeypatch):
    def handler(r):
        raise httpx.ConnectTimeout("cannot reach google")

    calls = _use(monkeypatch, handler)
    with pytest.raises(gemini_client.GeminiError) as e:
        gemini_client.generate("hi")
    assert "unreachable" in str(e.value) and len(calls) == 1


def test_per_attempt_timeout_is_capped(monkeypatch):
    monkeypatch.setenv("GEMINI_REQUEST_TIMEOUT", "4")
    assert gemini_client._per_attempt_timeout() == 4.0
    monkeypatch.setenv("GEMINI_REQUEST_TIMEOUT", "garbage")
    assert gemini_client._per_attempt_timeout() == 10.0


def test_bad_key_fails_fast_without_trying_other_models(monkeypatch):
    calls = _use(monkeypatch, lambda r: httpx.Response(403, json={}))
    with pytest.raises(gemini_client.GeminiError) as e:
        gemini_client.generate("hi")
    assert e.value.kind == "upstream" and len(calls) == 1


def test_network_error_fails_fast(monkeypatch):
    def handler(r):
        raise httpx.ConnectError("no route")

    calls = _use(monkeypatch, handler)
    with pytest.raises(gemini_client.GeminiError) as e:
        gemini_client.generate("hi")
    assert "unreachable" in str(e.value) and len(calls) == 1


def test_empty_or_blocked_answer_is_a_bad_response(monkeypatch):
    _use(monkeypatch, lambda r: httpx.Response(200, json={"candidates": []}))
    with pytest.raises(gemini_client.GeminiError) as e:
        gemini_client.generate("hi")
    assert e.value.kind == "bad_response"


# ── cooldown ─────────────────────────────────────────────────────────────────
def test_cooldown_after_repeated_failures_then_recovers(monkeypatch):
    calls = _use(monkeypatch, lambda r: httpx.Response(500))
    for _ in range(gemini_client._FAILURES_BEFORE_COOLDOWN):
        with pytest.raises(gemini_client.GeminiError):
            gemini_client.generate("hi")
    made = len(calls)
    with pytest.raises(gemini_client.GeminiError) as e:
        gemini_client.generate("hi")
    assert e.value.kind == "cooling_down" and len(calls) == made  # no HTTP while cooling down

    gemini_client.reset_state()
    _use(monkeypatch, lambda r: _ok("back"))
    assert gemini_client.generate("hi") == "back"


# ── JSON helpers ─────────────────────────────────────────────────────────────
def test_generate_json_strips_fences_and_extracts_the_object(monkeypatch):
    _use(monkeypatch, lambda r: _ok('Sure!\n```json\n{"a": 1, "b": "x"}\n```'))
    assert gemini_client.generate_json("give json") == {"a": 1, "b": "x"}


def test_generate_json_rejects_non_json(monkeypatch):
    _use(monkeypatch, lambda r: _ok("I cannot do that"))
    with pytest.raises(gemini_client.GeminiError) as e:
        gemini_client.generate_json("give json")
    assert e.value.kind == "bad_response"


# ── routes degrade gracefully (no 30 s stalls, same payload keys as before + `source`) ──
def test_coach_is_offline_without_a_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    r = client.post("/api/v1/ai/coach", json={"message": "best breakfast?"})
    assert r.status_code == 200 and r.json()["source"] == "offline" and "Breakfast" in r.json()["reply"]


def test_coach_uses_gemini_when_available(monkeypatch):
    monkeypatch.setattr(gemini_client, "generate", lambda *a, **k: "  Eat more protein.  ")
    r = client.post("/api/ai/coach", json={"message": "hi", "history": [{"role": "user", "message": "yo"}]})
    assert r.json() == {"reply": "Eat more protein.", "source": "gemini"}


def test_coach_falls_back_when_gemini_fails(monkeypatch):
    def boom(*a, **k):
        raise gemini_client.GeminiError("upstream", "down")

    monkeypatch.setattr(gemini_client, "generate", boom)
    r = client.post("/api/v1/ai/coach", json={"message": "snack ideas"})
    assert r.status_code == 200 and r.json()["source"] == "offline"


def test_diet_plan_and_recipe_generator_sources(monkeypatch):
    monkeypatch.setattr(gemini_client, "generate", lambda *a, **k: "PLAN TEXT")
    plan = client.post("/api/v1/ai/diet-plan", json={"user_id": 7})
    assert plan.status_code == 200 and plan.json() == {"plan": "PLAN TEXT", "source": "gemini"}
    recipe = client.post("/api/v1/ai/recipe-generator", json={"ingredients": "egg, spinach"})
    assert recipe.json() == {"recipe": "PLAN TEXT", "source": "gemini"}

    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert client.post("/api/v1/ai/diet-plan", json={"user_id": 7}).json()["source"] == "offline"
    assert client.post("/api/v1/ai/recipe-generator", json={"ingredients": "egg"}).json()["source"] == "offline"


def test_generate_instructions_503_without_key_and_works_with_one(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    r = client.post("/api/v1/recipes/generate-instructions", json={"recipe_name": "Poha"})
    assert r.status_code == 503

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(gemini_client, "generate", lambda *a, **k: "1. Rinse poha.\n2. Temper spices.")
    ok = client.post("/api/v1/recipes/generate-instructions", json={"recipe_name": "Poha", "ingredients": ["poha", "onion"]})
    assert ok.status_code == 200 and ok.json()["instructions"].startswith("1. Rinse")

    def boom(*a, **k):
        raise gemini_client.GeminiError("upstream", "down")

    monkeypatch.setattr(gemini_client, "generate", boom)
    assert client.post("/api/v1/recipes/generate-instructions", json={"recipe_name": "Poha"}).status_code == 503


# ── OCR / barcode use the client ─────────────────────────────────────────────
def test_ocr_extraction_goes_through_the_client(monkeypatch):
    captured = {}

    def fake_json(prompt, **kwargs):
        captured.update(kwargs)
        return {"energy_kcal": "533", "protein_g": 7.5, "carb_g": 58, "fat_g": 28, "serving_size": "34g"}

    monkeypatch.setattr(gemini_client, "generate_json", fake_json)
    result = OCREngine.extract_nutrition_with_gemini(b"jpegbytes")
    assert result["energy_kcal"] == 533.0 and result["serving_size"] == "34g" and result["fibre_g"] == 0.0
    assert captured["image_bytes"] == b"jpegbytes"


def test_ocr_and_barcode_are_quiet_without_a_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert OCREngine.extract_nutrition_with_gemini(b"x") is None
    assert BarcodeService.estimate_nutrition_from_gemini("Maggi", "8901058852712") is None


def test_barcode_estimate_goes_through_the_client(monkeypatch):
    monkeypatch.setattr(gemini_client, "generate_json", lambda *a, **k: {
        "product_name": "Test Biscuit", "brand": "TestCo", "energy_kcal": 480, "protein_g": 6, "carb_g": 70,
        "fat_g": 19, "fibre_g": 2, "sodium_mg": 300, "sugar_g": 25, "saturated_fat_g": 9, "estimated_price": 20,
        "nutrition_grade": "D"})
    res = BarcodeService.estimate_nutrition_from_gemini("Biscuit", "8900000000000")
    assert res and res["brand"] == "TestCo" and res["nutrition_grade"] == "d" and res["energy_kcal"] == 480.0


def test_barcode_image_reader_uses_the_client(monkeypatch):
    monkeypatch.setattr(gemini_client, "generate_json", lambda *a, **k: {"barcode": "8901058852712"})
    # a blank image defeats the local OpenCV detectors, so the Gemini fallback decides
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (255, 255, 255)).save(buf, format="JPEG")
    assert BarcodeService.detect_barcode_from_image(buf.getvalue()) == "8901058852712"


def test_quoted_key_from_env_is_unwrapped(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", '"abc-123"')
    calls = _use(monkeypatch, lambda r: _ok("hi"))
    gemini_client.generate("hi")
    assert calls[0].headers["x-goog-api-key"] == "abc-123"


def test_invalid_key_400_fails_fast_with_googles_message(monkeypatch):
    bad = {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}}
    calls = _use(monkeypatch, lambda r: httpx.Response(400, json=bad))
    with pytest.raises(gemini_client.GeminiError) as e:
        gemini_client.generate("hi")
    assert "API key" in str(e.value) and len(calls) == 1      # did NOT cycle through the fallback models


def test_extra_generation_config_from_env_is_merged(monkeypatch):
    monkeypatch.setenv("GEMINI_GENERATION_CONFIG", '{"thinkingConfig": {"thinkingBudget": 0}, "maxOutputTokens": 500}')
    calls = _use(monkeypatch, lambda r: _ok("{}"))
    gemini_client.generate("hi", json_mode=True, temperature=0.2)
    config = json.loads(calls[0].content)["generationConfig"]
    assert config == {"thinkingConfig": {"thinkingBudget": 0}, "maxOutputTokens": 500,
                      "responseMimeType": "application/json", "temperature": 0.2}


def test_bad_generation_config_is_ignored(monkeypatch):
    monkeypatch.setenv("GEMINI_GENERATION_CONFIG", "not json")
    calls = _use(monkeypatch, lambda r: _ok("ok"))
    gemini_client.generate("hi")
    assert "generationConfig" not in json.loads(calls[0].content)
