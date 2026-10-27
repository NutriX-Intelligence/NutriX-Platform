import hashlib
import io
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import Image
from sqlalchemy.orm import Session

from ms2_llm import config, prompts
from ms2_llm.schemas import LookupRequest, LookupResponse, NutritionPer100g, VisionInferResponse
from ms2_llm.validation import UNKNOWN, parse_nutrition
from ms2_llm.vlm_engine import VLMNotAvailable, engine
from shared.audit import log_audit_event
from shared.db import get_db
from shared.food_lookup import lookup_food, per_100g, persist_llm_food
from shared.health import check_health

logger = logging.getLogger("ms2_llm")

SOURCE = "qwen3-vl-2b"
MAX_IMAGE_SIDE = 1280  # decode-time cap; the processor further limits to VLM_MAX_PIXELS


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load Qwen3-VL-2B once at startup (when VLM_KEEP_LOADED) so the first request is fast."""
    if config.VLM_AUTOLOAD and config.VLM_KEEP_LOADED:
        try:
            await run_in_threadpool(engine.load)
        except VLMNotAvailable as e:
            logger.error("MS2 starting without VLM: %s", e)
    yield


app = FastAPI(title="NutriX MS2 LLM Nutrition & Vision Service", version="1.0.0", lifespan=lifespan)


# ── Health ──────────────────────────────────────────────────────────────────
@app.get("/")
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    result = check_health(service_name="ms2_llm", db=db, include_redis=True, version="1.0.0")
    result["checks"]["vlm"] = engine.status()
    if not engine.loaded and config.VLM_KEEP_LOADED and result["status"] == "healthy":
        result["status"] = "degraded"
    return result


# ── Helpers ─────────────────────────────────────────────────────────────────
def _user_id(x_user_id: Optional[str]) -> Optional[int]:
    return int(x_user_id) if x_user_id and x_user_id.isdigit() else None


async def _run_vlm(system: str, user: str, image=None) -> dict:
    """Run Qwen and parse the JSON; retry once on unparseable output."""
    for _ in range(2):
        try:
            raw = await run_in_threadpool(engine.infer, system, user, image)
        except VLMNotAvailable as e:
            raise HTTPException(status_code=503, detail={"source": "llm-unavailable", "error": str(e)})
        parsed = parse_nutrition(raw)
        if parsed is not None:
            return parsed
        logger.warning("Unparseable VLM output: %r", raw[:200])
    return {"food_name": UNKNOWN, "confidence": None, "per_100g": None,
            "flagged": True, "flag_reason": "unparseable model output"}


def _audit(operation: str, user_id: Optional[int], input_data, resp, latency_ms: int):
    log_audit_event(
        service="ms2",
        operation=operation,
        user_id=user_id,
        input_data=input_data,
        output_data={
            "food_name": resp.food_name,
            "per_100g": resp.per_100g.model_dump() if resp.per_100g else None,
            "source": resp.source,
            "flag_reason": resp.flag_reason,
            "model": SOURCE,
        },
        confidence=getattr(resp, "confidence", None),
        latency_ms=latency_ms,
        flagged=resp.flagged,
    )


# ── POST /api/v1/llm/vision-infer ───────────────────────────────────────────
@app.post("/api/v1/llm/vision-infer", response_model=VisionInferResponse)
async def vision_infer(
    background: BackgroundTasks,
    image: UploadFile = File(...),
    weight: Optional[float] = Form(None),
    yolo_hint: Optional[str] = Form(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
):
    """Identify the food in a scale frame and estimate per-100g macros. Does not write meal_logs."""
    start = time.perf_counter()
    data = await image.read()
    try:
        pil = Image.open(io.BytesIO(data)).convert("RGB")
        pil.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image")

    parsed = await _run_vlm(
        prompts.get_system_prompt(prompts.VISION_KEY),
        prompts.vision_user_prompt(weight, yolo_hint),
        pil,
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    resp = VisionInferResponse(
        food_name=parsed["food_name"],
        confidence=parsed["confidence"],
        per_100g=parsed["per_100g"],
        source=SOURCE,
        latency_ms=latency_ms,
        flagged=parsed["flagged"],
        flag_reason=parsed["flag_reason"],
    )
    background.add_task(
        _audit, "llm_vision", _user_id(x_user_id),
        {"image_sha256": hashlib.sha256(data).hexdigest(), "weight": weight, "yolo_hint": yolo_hint},
        resp, latency_ms,
    )
    return resp


# ── POST /api/v1/llm/lookup ─────────────────────────────────────────────────
@app.post("/api/v1/llm/lookup", response_model=LookupResponse)
async def llm_lookup(
    req: LookupRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
):
    """Text to per-100g macros: local DB first, Qwen on a miss (then persisted)."""
    start = time.perf_counter()

    food = lookup_food(db, req.food_name)
    macros = per_100g(food) if food else None
    if macros:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return LookupResponse(food_name=food.name, per_100g=NutritionPer100g(**macros),
                              source="db", latency_ms=latency_ms)

    parsed = await _run_vlm(
        prompts.get_system_prompt(prompts.LOOKUP_KEY),
        prompts.lookup_user_prompt(req.food_name),
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    resp = LookupResponse(
        food_name=req.food_name.strip().lower(),
        per_100g=parsed["per_100g"],
        source=SOURCE,
        latency_ms=latency_ms,
        flagged=parsed["flagged"],
        flag_reason=parsed["flag_reason"],
    )
    # Persist under the name that was asked for, so the next lookup is a DB hit
    if resp.per_100g and not resp.flagged:
        persist_llm_food(db, req.food_name, resp.per_100g.model_dump())
    background.add_task(_audit, "llm_lookup", _user_id(x_user_id), {"food_name": req.food_name}, resp, latency_ms)
    return resp
