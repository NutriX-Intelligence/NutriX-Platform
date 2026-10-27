"""
Async client for MS2 (LLM Nutrition & Vision). Every call returns None on any failure
(timeout, connection error, non-200) so MS1 can degrade gracefully.
"""
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("ms1_cv.llm_client")


def _ms2_url() -> str:
    url = os.getenv("MS2_LLM_URL", "http://localhost:8003")
    # Outside Docker the compose hostname does not resolve
    if not os.path.exists("/.dockerenv"):
        url = url.replace("//ms2-llm:", "//localhost:")
    return url.rstrip("/")


def _timeout_s() -> float:
    return float(os.getenv("MS2_TIMEOUT_S", "30"))


def _headers(user_id: Optional[str]) -> Dict[str, str]:
    return {"X-User-ID": user_id} if user_id else {}


async def vision_infer(
    image_bytes: bytes,
    weight: float,
    yolo_hint: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    data = {"weight": str(weight)}
    if yolo_hint:
        data["yolo_hint"] = yolo_hint
    try:
        async with httpx.AsyncClient(timeout=_timeout_s()) as client:
            r = await client.post(
                f"{_ms2_url()}/api/v1/llm/vision-infer",
                files={"image": ("frame.jpg", image_bytes, "image/jpeg")},
                data=data,
                headers=_headers(user_id),
            )
        if r.status_code == 200:
            return r.json()
        logger.warning("MS2 vision-infer returned %s: %s", r.status_code, r.text[:200])
    except Exception as e:
        logger.warning("MS2 vision-infer failed: %r", e)
    return None


async def lookup(food_name: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=_timeout_s()) as client:
            r = await client.post(
                f"{_ms2_url()}/api/v1/llm/lookup",
                json={"food_name": food_name},
                headers=_headers(user_id),
            )
        if r.status_code == 200:
            return r.json()
        logger.warning("MS2 lookup returned %s: %s", r.status_code, r.text[:200])
    except Exception as e:
        logger.warning("MS2 lookup failed: %r", e)
    return None
