"""
The single place MS3 talks to Google Gemini.

Replaces the seven inline REST calls that used to be scattered over routes.py, ocr_engine.py and
barcode_service.py. What it fixes:

* the API key travels in the `x-goog-api-key` header, never in the URL (URLs end up in logs),
* one configurable model plus ordered fallbacks (GEMINI_MODEL / GEMINI_FALLBACK_MODELS), skipping a model the
  API reports as unknown or retired,
* bounded retries with backoff on 429/5xx, and an overall deadline per call,
* a short cooldown after an outage: callers fail fast instead of each waiting out a 30 s timeout,
* one typed error (GeminiError) so routes can degrade gracefully.

All functions are synchronous (the MS3 handlers that use them are plain `def`, run in FastAPI's threadpool).
"""
import base64
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("ms3.gemini")

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_KEY_ENV_NAMES = ("GEMINI_API_KEY", "GEMINI_3_6_API_KEY", "GEMINI_API_KEY_1")  # the last two are legacy names

RETRY_SAME_MODEL = {429, 500, 502, 504}   # transient: one more try on the same model
MAX_ATTEMPTS_PER_MODEL = 2
# 503 means "this model is overloaded right now": retrying it is pointless, go to the next model immediately.
COOLDOWN_SECONDS = 30.0
_FAILURES_BEFORE_COOLDOWN = 2

# tests replace this with httpx.MockTransport(...)
_transport: Optional[httpx.BaseTransport] = None

_lock = threading.Lock()
_consecutive_failures = 0
_down_until = 0.0


class GeminiError(Exception):
    """kind: not_configured | cooling_down | upstream | bad_response"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


# ── configuration ─────────────────────────────────────────────────────────────
def api_key() -> str:
    for name in _KEY_ENV_NAMES:
        value = os.environ.get(name, "").strip().strip('"').strip("'").strip()  # tolerate KEY="..." in .env
        if value:
            return value
    return ""


def is_configured() -> bool:
    return bool(api_key())


def models() -> List[str]:
    primary = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.8-flash"
    fallbacks = os.environ.get("GEMINI_FALLBACK_MODELS", "")  # model names are retired often: list yours with scripts/list_gemini_models.py
    ordered = [primary] + [m.strip() for m in fallbacks.split(",") if m.strip()]
    seen, unique = set(), []
    for m in ordered:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique


def reset_state() -> None:
    """Clear the failure counter and cooldown (used by tests)."""
    global _consecutive_failures, _down_until
    with _lock:
        _consecutive_failures, _down_until = 0, 0.0


def _record_success() -> None:
    global _consecutive_failures, _down_until
    with _lock:
        _consecutive_failures, _down_until = 0, 0.0


def _record_failure() -> None:
    global _consecutive_failures, _down_until
    with _lock:
        _consecutive_failures += 1
        if _consecutive_failures >= _FAILURES_BEFORE_COOLDOWN:
            _down_until = time.monotonic() + COOLDOWN_SECONDS
            logger.warning("Gemini unavailable: failing fast for %.0f s", COOLDOWN_SECONDS)


def _per_attempt_timeout() -> float:
    """Cap for ONE request, so a slow/overloaded model cannot eat the whole budget (GEMINI_REQUEST_TIMEOUT, default 10 s)."""
    try:
        return max(float(os.environ.get("GEMINI_REQUEST_TIMEOUT", "10")), 1.0)
    except ValueError:
        return 10.0


# ── core call ─────────────────────────────────────────────────────────────────
def extra_generation_config() -> Dict[str, Any]:
    """Optional GEMINI_GENERATION_CONFIG (JSON), merged into every request: e.g. a thinking budget or an output cap.
    Find what your key accepts with scripts/benchmark_gemini.py --variants."""
    raw = os.environ.get("GEMINI_GENERATION_CONFIG", "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    logger.warning("GEMINI_GENERATION_CONFIG is not a JSON object; ignoring it")
    return {}


def _build_payload(
    prompt: Optional[str],
    contents: Optional[List[Dict[str, Any]]],
    system: Optional[str],
    image_bytes: Optional[bytes],
    mime_type: str,
    json_mode: bool,
    temperature: Optional[float],
) -> Dict[str, Any]:
    if contents is None:
        parts: List[Dict[str, Any]] = [{"text": prompt or ""}]
        if image_bytes:
            parts.append({"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}})
        contents = [{"parts": parts}]
    payload: Dict[str, Any] = {"contents": contents}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    generation_config: Dict[str, Any] = dict(extra_generation_config())
    if json_mode:
        generation_config["responseMimeType"] = "application/json"
    if temperature is not None:
        generation_config["temperature"] = temperature
    if generation_config:
        payload["generationConfig"] = generation_config
    return payload


def _error_message(response: httpx.Response) -> str:
    """Google's own explanation of a 4xx (never contains our key), truncated for logs."""
    try:
        return str(response.json().get("error", {}).get("message", ""))[:200]
    except Exception:
        return response.text[:200]


def _is_bad_key(message: str) -> bool:
    m = message.lower()
    return "api key" in m and ("not valid" in m or "invalid" in m or "expired" in m)


def _extract_text(data: Dict[str, Any]) -> str:
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise GeminiError("bad_response", "Gemini returned no text (blocked or empty response)")


def generate(
    prompt: Optional[str] = None,
    *,
    contents: Optional[List[Dict[str, Any]]] = None,
    system: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    mime_type: str = "image/jpeg",
    json_mode: bool = False,
    temperature: Optional[float] = None,
    timeout: float = 30.0,
) -> str:
    """Return Gemini's text answer, or raise GeminiError. `timeout` is the overall budget for the whole call."""
    key = api_key()
    if not key:
        raise GeminiError("not_configured", "GEMINI_API_KEY is not set")
    if time.monotonic() < _down_until:
        raise GeminiError("cooling_down", "Gemini was unreachable moments ago; failing fast")

    payload = _build_payload(prompt, contents, system, image_bytes, mime_type, json_mode, temperature)
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    deadline = time.monotonic() + timeout
    last_error = "no model tried"

    unreachable = False
    out_of_time = False
    for model in models():
        url = BASE_URL.format(model=model)
        for attempt in range(MAX_ATTEMPTS_PER_MODEL):
            remaining = deadline - time.monotonic()
            if remaining <= 0.5:
                out_of_time = True
                break
            try:
                with httpx.Client(timeout=min(remaining, _per_attempt_timeout()), transport=_transport) as client:
                    response = client.post(url, json=payload, headers=headers)
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                # cannot even reach Google: other models will not help, fail fast
                last_error = f"{model}: {type(e).__name__}"
                logger.warning("Gemini unreachable (%s): %s", model, type(e).__name__)
                unreachable = True
                break
            except httpx.HTTPError as e:
                # read timeout / dropped connection: THIS model is slow or unhealthy, try the next one
                last_error = f"{model}: {type(e).__name__}"
                logger.warning("Gemini %s slow or unhealthy (%s): moving to the next model", model, type(e).__name__)
                break

            if response.status_code == 200:
                try:
                    text = _extract_text(response.json())
                except GeminiError:
                    logger.warning("Gemini %s returned HTTP 200 without text: %s", model, response.text[:300])
                    raise
                _record_success()
                return text

            last_error = f"{model}: HTTP {response.status_code}"
            message = _error_message(response)
            logger.warning("Gemini %s attempt %d/%d -> HTTP %s %s", model, attempt + 1, MAX_ATTEMPTS_PER_MODEL,
                           response.status_code, message)
            if response.status_code in RETRY_SAME_MODEL and attempt + 1 < MAX_ATTEMPTS_PER_MODEL:
                time.sleep(min(0.5 * (attempt + 1), max(deadline - time.monotonic() - 0.5, 0)))
                continue
            if response.status_code in (400, 404):
                if _is_bad_key(message):
                    # Google answers an invalid key with HTTP 400: no other model will accept it either
                    _record_failure()
                    raise GeminiError("upstream", f"Gemini rejected the API key: {message}")
                break  # unknown / retired model (or a feature this model lacks): next model
            if response.status_code in RETRY_SAME_MODEL or response.status_code == 503:
                break  # retries exhausted or model overloaded: next model
            # 401 / 403 and other 4xx: other models will not help
            _record_failure()
            raise GeminiError("upstream", f"Gemini rejected the request ({last_error})")
        if unreachable or out_of_time:
            break

    _record_failure()
    if unreachable:
        raise GeminiError("upstream", f"Gemini unreachable ({last_error})")
    if out_of_time:
        raise GeminiError("upstream", f"Gemini ran out of time after {timeout:.0f}s ({last_error})")
    hint = "; run scripts/list_gemini_models.py and set GEMINI_MODEL" if "HTTP 404" in last_error else ""
    raise GeminiError("upstream", f"All Gemini models failed ({last_error}){hint}")


# ── JSON helpers ──────────────────────────────────────────────────────────────
def parse_json_text(text: str) -> Any:
    """Parse a model answer that may be wrapped in markdown fences."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise GeminiError("bad_response", "Gemini did not return valid JSON")


def generate_json(prompt: Optional[str] = None, **kwargs: Any) -> Any:
    """`generate` in JSON mode, parsed. Raises GeminiError('bad_response') on invalid JSON."""
    kwargs.setdefault("json_mode", True)
    return parse_json_text(generate(prompt, **kwargs))
