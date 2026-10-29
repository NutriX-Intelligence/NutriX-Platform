"""AI text chain: Gemini -> local Qwen (MS2 llm/generate) -> canned offline text, with an honest `source` label."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from ms3_user.main import app
from ms3_user.services import ai_text, gemini_client

client = TestClient(app)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("AI_LOCAL_FALLBACK", "true")
    monkeypatch.setenv("MS2_LLM_URL", "http://localhost:8003")
    gemini_client.reset_state()
    yield
    monkeypatch.setattr(ai_text, "_local_transport", None)
    gemini_client.reset_state()


def _local(monkeypatch, handler):
    calls = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    monkeypatch.setattr(ai_text, "_local_transport", httpx.MockTransport(wrapped))
    return calls


def _gemini_down(monkeypatch):
    def boom(*a, **k):
        raise gemini_client.GeminiError("upstream", "overloaded")

    monkeypatch.setattr(gemini_client, "generate", boom)


# ── the chain ────────────────────────────────────────────────────────────────
def test_gemini_answer_wins_and_local_is_not_called(monkeypatch):
    monkeypatch.setattr(gemini_client, "generate", lambda *a, **k: "  from gemini  ")
    calls = _local(monkeypatch, lambda r: httpx.Response(200, json={"text": "from local"}))
    assert ai_text.generate_text("hi") == ("from gemini", "gemini")
    assert calls == []


def test_falls_back_to_local_when_gemini_fails(monkeypatch):
    _gemini_down(monkeypatch)
    calls = _local(monkeypatch, lambda r: httpx.Response(200, json={"text": " from local "}))
    assert ai_text.generate_text("Protein snack?", system="Be brief", max_new_tokens=100) == ("from local", "local")
    sent = json.loads(calls[0].content)
    assert calls[0].url.path == "/api/v1/llm/generate"
    assert sent == {"prompt": "Protein snack?", "system": "Be brief", "max_new_tokens": 100}


def test_uses_local_when_gemini_is_not_configured(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    _local(monkeypatch, lambda r: httpx.Response(200, json={"text": "local only"}))
    assert ai_text.generate_text("hi") == ("local only", "local")


def test_everything_down_raises_with_both_reasons(monkeypatch):
    _gemini_down(monkeypatch)
    _local(monkeypatch, lambda r: httpx.Response(503, json={}))
    with pytest.raises(ai_text.AIUnavailable) as e:
        ai_text.generate_text("hi")
    assert "gemini" in str(e.value) and "local" in str(e.value)


def test_local_connection_error_is_reported_not_raised_raw(monkeypatch):
    _gemini_down(monkeypatch)

    def handler(r):
        raise httpx.ConnectError("ms2 down")

    _local(monkeypatch, handler)
    with pytest.raises(ai_text.AIUnavailable):
        ai_text.generate_text("hi")


def test_local_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("AI_LOCAL_FALLBACK", "false")
    _gemini_down(monkeypatch)
    calls = _local(monkeypatch, lambda r: httpx.Response(200, json={"text": "x"}))
    with pytest.raises(ai_text.AIUnavailable):
        ai_text.generate_text("hi")
    assert calls == [] and ai_text.any_provider() is True  # gemini is still "a provider", just failing


def test_no_provider_at_all(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("AI_LOCAL_FALLBACK", "false")
    assert ai_text.any_provider() is False
    with pytest.raises(ai_text.AIUnavailable):
        ai_text.generate_text("hi")


def test_empty_local_answer_is_a_failure(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    _local(monkeypatch, lambda r: httpx.Response(200, json={"text": "   "}))
    with pytest.raises(ai_text.AIUnavailable):
        ai_text.generate_text("hi")


def test_flatten_contents_keeps_the_conversation():
    contents = [{"role": "user", "parts": [{"text": "I am vegetarian"}]},
                {"role": "model", "parts": [{"text": "Great, noted."}]},
                {"role": "user", "parts": [{"text": "Dinner idea?"}]}]
    flat = ai_text.flatten_contents(contents)
    assert "User: I am vegetarian" in flat and "Coach: Great, noted." in flat and flat.rstrip().endswith("last User message.")


def test_ms2_url_is_rewritten_outside_docker(monkeypatch):
    monkeypatch.setenv("MS2_LLM_URL", "http://ms2-llm:8003/")
    assert ai_text._ms2_url() == "http://localhost:8003"


# ── routes ───────────────────────────────────────────────────────────────────
def test_coach_reports_local_when_gemini_is_down(monkeypatch):
    _gemini_down(monkeypatch)
    calls = _local(monkeypatch, lambda r: httpx.Response(200, json={"text": "Try paneer tikka."}))
    r = client.post("/api/v1/ai/coach", json={"message": "dinner?", "history": [{"role": "user", "message": "veg"}]})
    assert r.status_code == 200 and r.json() == {"reply": "Try paneer tikka.", "source": "local"}
    assert "Conversation so far" in json.loads(calls[0].content)["prompt"]


def test_all_text_routes_fall_back_to_local_then_to_canned(monkeypatch):
    _gemini_down(monkeypatch)
    _local(monkeypatch, lambda r: httpx.Response(200, json={"text": "LOCAL TEXT"}))
    assert client.post("/api/v1/ai/diet-plan", json={"user_id": 9}).json() == {"plan": "LOCAL TEXT", "source": "local"}
    recipe = client.post("/api/v1/ai/recipe-generator", json={"ingredients": "egg"}).json()
    assert (recipe["recipe"].strip(), recipe["source"]) == ("LOCAL TEXT", "local")
    inst = client.post("/api/v1/recipes/generate-instructions", json={"recipe_name": "Poha"})
    assert inst.status_code == 200 and inst.json() == {"instructions": "LOCAL TEXT", "source": "local"}

    _local(monkeypatch, lambda r: httpx.Response(503, json={}))  # MS2 down too: canned text, never an error
    assert client.post("/api/v1/ai/coach", json={"message": "snack"}).json()["source"] == "offline"
    assert client.post("/api/v1/ai/diet-plan", json={"user_id": 9}).json()["source"] == "offline"
    assert client.post("/api/v1/ai/recipe-generator", json={"ingredients": "egg"}).json()["source"] == "offline"
    assert client.post("/api/v1/recipes/generate-instructions", json={"recipe_name": "Poha"}).status_code == 503
