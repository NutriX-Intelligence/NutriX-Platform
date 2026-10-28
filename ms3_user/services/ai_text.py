"""
Text generation for MS3's AI features (coach, diet plan, recipe generator, recipe instructions).

Provider chain:  Gemini (several models, see gemini_client)  ->  local Qwen3-VL on MS2  ->  AIUnavailable.
The caller decides what to do when everything fails (the routes return their canned "offline" text), and every
answer is labelled with its `source`: "gemini" or "local".

The local step needs MS2's POST /api/v1/llm/generate and can be switched off with AI_LOCAL_FALLBACK=false.
Image features (OCR, barcode photo) keep their own deterministic local fallbacks and do not use this module.
"""
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ms3_user.services import gemini_client

logger = logging.getLogger("ms3.ai_text")

# tests replace this with httpx.MockTransport(...)
_local_transport: Optional[httpx.BaseTransport] = None


class AIUnavailable(Exception):
    """Every configured provider failed (or none is configured)."""


class LocalLLMError(Exception):
    pass


# ── local model (MS2) ─────────────────────────────────────────────────────────
def local_enabled() -> bool:
    return os.getenv("AI_LOCAL_FALLBACK", "true").strip().lower() in ("1", "true", "yes", "on")


def _ms2_url() -> str:
    url = os.getenv("MS2_LLM_URL", "http://localhost:8003")
    if not os.path.exists("/.dockerenv"):  # outside Docker the compose hostname does not resolve
        url = url.replace("//ms2-llm:", "//localhost:")
    return url.rstrip("/")


def local_generate(prompt: str, system: Optional[str] = None, max_new_tokens: int = 384, timeout: float = 40.0) -> str:
    try:
        with httpx.Client(timeout=timeout, transport=_local_transport) as client:
            response = client.post(
                f"{_ms2_url()}/api/v1/llm/generate",
                json={"prompt": prompt, "system": system, "max_new_tokens": max_new_tokens},
            )
    except httpx.HTTPError as e:
        raise LocalLLMError(f"MS2 unreachable ({type(e).__name__})")
    if response.status_code != 200:
        raise LocalLLMError(f"MS2 returned HTTP {response.status_code}")
    text = str(response.json().get("text", "")).strip()
    if not text:
        raise LocalLLMError("MS2 returned an empty answer")
    return text


def flatten_contents(contents: List[Dict[str, Any]]) -> str:
    """Gemini-style multi-turn `contents` -> one prompt for the local model."""
    lines = []
    for turn in contents:
        speaker = "User" if turn.get("role", "user") == "user" else "Coach"
        text = " ".join(str(p.get("text", "")) for p in turn.get("parts", []) if isinstance(p, dict)).strip()
        if text:
            lines.append(f"{speaker}: {text}")
    return "Conversation so far:\n" + "\n".join(lines) + "\n\nReply as the Coach to the last User message."


# ── the chain ─────────────────────────────────────────────────────────────────
def any_provider() -> bool:
    return gemini_client.is_configured() or local_enabled()


def generate_text(
    prompt: Optional[str] = None,
    *,
    contents: Optional[List[Dict[str, Any]]] = None,
    system: Optional[str] = None,
    gemini_timeout: float = 18.0,
    local_timeout: float = 40.0,
    max_new_tokens: int = 384,
) -> Tuple[str, str]:
    """Return (text, source) with source "gemini" | "local", or raise AIUnavailable."""
    errors: List[str] = []

    if gemini_client.is_configured():
        try:
            text = gemini_client.generate(prompt, contents=contents, system=system, timeout=gemini_timeout)
            return text.strip(), "gemini"
        except gemini_client.GeminiError as e:
            logger.warning("Gemini failed (%s): %s", e.kind, e)
            errors.append(f"gemini: {e}")

    if local_enabled():
        try:
            local_prompt = flatten_contents(contents) if contents is not None else (prompt or "")
            text = local_generate(local_prompt, system=system, max_new_tokens=max_new_tokens, timeout=local_timeout)
            logger.info("Answered by the local model (Gemini unavailable)")
            return text, "local"
        except LocalLLMError as e:
            logger.warning("Local model failed: %s", e)
            errors.append(f"local: {e}")

    raise AIUnavailable("; ".join(errors) or "no AI provider is configured")
