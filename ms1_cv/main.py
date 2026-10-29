import os
import uuid
import tempfile
import shutil
import cv2
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, Header, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session

from datetime import datetime
from shared.db import get_db
from shared import clock
from shared.health import check_health
from shared.models import MealLog, User
from shared.food_lookup import lookup_food, per_100g, persist_llm_food, normalize_name
from shared.macro_sync import sync_daily_macros
from ms1_cv import llm_client
from ms1_cv.cv_engine import NutriXCVEngine, MealSession

# ── In-memory result store: session_id -> result dict ──────────────────────
_results: dict = {}

# ── Live captures directory for viewing frames in real-time ───────────────
CAPTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dataset/live_captures"))
os.makedirs(CAPTURES_DIR, exist_ok=True)
LATEST_RAW_PATH = os.path.join(CAPTURES_DIR, "latest_raw.jpg")
LATEST_ANNOTATED_PATH = os.path.join(CAPTURES_DIR, "latest_annotated.jpg")

# ── YOLO model path (prefer custom best.pt, fallback to yolov8n.pt) ────────
_MODEL_PATH = "/home/harsh/Nutrix/backend/services/ingestion/best.pt"
if not os.path.exists(_MODEL_PATH):
    _MODEL_PATH = "yolov8n.pt"   # auto-download fallback

# YOLO confidence needed to trust a detection; below it (or on a suppressed class) the
# frame goes to MS2's vision model. Tune via YOLO_CONF_THRESHOLD in .env.
_CONF_THRESHOLD = float(os.getenv("YOLO_CONF_THRESHOLD", "0.5"))

# Shared engine instance (lazy-loaded on first request)
_engine: Optional[NutriXCVEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load the YOLO model at startup so first request is fast."""
    global _engine
    _engine = NutriXCVEngine(model_path=_MODEL_PATH, confidence_threshold=_CONF_THRESHOLD)
    # Warm up the model
    _ = _engine.model
    yield


app = FastAPI(
    title="NutriX MS1 CV & Ingestion Service",
    version="1.0.0",
    lifespan=lifespan
)


# ── Health ──────────────────────────────────────────────────────────────────
@app.get("/")
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    return check_health(service_name="ms1_cv", db=db, include_redis=True, version="1.0.0")


# ── Image Viewer Endpoints (View real-time captures in browser) ────────────
@app.get("/captures/latest")
def get_latest_raw_image():
    if not os.path.exists(LATEST_RAW_PATH):
        raise HTTPException(status_code=404, detail="No capture received yet")
    return FileResponse(LATEST_RAW_PATH, media_type="image/jpeg")


@app.get("/captures/annotated")
def get_latest_annotated_image():
    if not os.path.exists(LATEST_ANNOTATED_PATH):
        raise HTTPException(status_code=404, detail="No annotated capture available yet")
    return FileResponse(LATEST_ANNOTATED_PATH, media_type="image/jpeg")


# ── Scale user resolution ───────────────────────────────────────────────────
# Accounts are created through MS3 (register). For bench testing, AUTO_CREATE_DEV_USER=true lets an
# unknown User-ID be created on the fly (and keeps the Postgres id sequence ahead of it).
_AUTO_CREATE_DEV_USER = os.getenv("AUTO_CREATE_DEV_USER", "false").strip().lower() in ("1", "true", "yes", "on")


_LOG_UNKNOWN_SCANS = os.getenv("LOG_UNKNOWN_SCANS", "false").strip().lower() in ("1", "true", "yes", "on")


class _NotLogged(Exception):
    """Control flow: skip persisting this scan."""


def _resolve_scale_user(db: Session, x_user_id: Optional[str]) -> int:
    if x_user_id and x_user_id.isdigit():
        uid = int(x_user_id)
    elif _AUTO_CREATE_DEV_USER:
        uid = 1
    else:
        raise HTTPException(status_code=400, detail="Missing or invalid User-ID header.")

    if db.query(User).filter(User.id == uid).first():
        return uid
    if not _AUTO_CREATE_DEV_USER:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown user {uid}. Register the account first (POST /api/v1/auth/register).",
        )
    db.add(User(id=uid, name="Smart Scale User", email=f"user_{uid}@nutrix.local"))
    db.commit()
    try:  # an explicit id does not advance the serial sequence: do it, or the next registration collides
        from sqlalchemy import text
        db.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT GREATEST(MAX(id), 1) FROM users))"))
        db.commit()
    except Exception:
        db.rollback()  # not Postgres (SQLite fallback)
    return uid


# ── POST /api/v1/ingest/weight-frame ───────────────────────────────────────
@app.post("/api/v1/ingest/weight-frame")
async def ingest_weight_frame(
    weight: float = Form(...),
    image: UploadFile = File(...),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
    db: Session = Depends(get_db)
):
    """
    Receives multipart POST from ESP32 scale (via gateway).
    Runs YOLO inference on the image, fetches calories from DB,
    annotates and saves the image, and returns the result.
    """
    target_uid = _resolve_scale_user(db, x_user_id)
    session_id = str(uuid.uuid4())

    # Save uploaded image to temp file and latest_raw.jpg
    suffix = os.path.splitext(image.filename or "frame.jpg")[1] or ".jpg"
    image_bytes = await image.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    shutil.copy(tmp_path, LATEST_RAW_PATH)

    try:
        session = MealSession(session_id=session_id)
        success, result = _engine.process_scale_event(
            image_path=tmp_path,
            current_weight=weight,
            session=session
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # ── Resolve the food label (YOLO first, MS2 Qwen3-VL fallback) ───────────
    identified_by = "yolo"
    vlm_macros = None       # per-100g macros estimated by Qwen, used only on a DB miss
    vlm_flagged = False
    llm_timeout = False
    yolo_status = result.get("status", "unidentified")

    if yolo_status == "ignored":
        # The scale reported (almost) no weight: there is no food to identify, so neither YOLO nor MS2 runs
        # and nothing is logged (it used to create an "Unknown, 0 kcal" meal per press).
        print(f"[Scan] user={target_uid} weight={weight}g -> ignored: {result.get('reason', '')}. "
              f"YOLO/MS2 not run, nothing logged. Check scale calibration/tare.")
        payload = {
            "session_id": session_id, "status": "ignored", "identified_by": "none", "macro_source": "none",
            "yolo_status": yolo_status, "food_label": "No Weight Detected", "confidence": 0.0,
            "weight_g": round(weight, 2), "calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0,
            "reason": result.get("reason", ""), "user_id": x_user_id,
        }
        _results[session_id] = payload
        return JSONResponse(content=payload)

    if success and yolo_status == "identified":
        addition = result["addition"]
        food_name = addition["food_name"]
        confidence_val = round(addition["confidence"] * 100, 1)
        bbox = addition.get("bounding_box")  # [xmin, ymin, xmax, ymax] normalized
        status_val = "identified"
    else:
        food_name = "unknown"
        confidence_val = 0.0
        bbox = (result.get("addition", {}) or {}).get("bounding_box")
        status_val = yolo_status
        if yolo_status != "ignored":
            # fallback_class is None for suppressed classes (lassi/kulfi): no biasing hint
            vlm = await llm_client.vision_infer(image_bytes, weight, result.get("fallback_class"), x_user_id)
            if vlm is None:
                llm_timeout = True
            elif vlm.get("food_name") and vlm["food_name"] != "unknown":
                food_name = vlm["food_name"]
                confidence_val = round((vlm.get("confidence") or 0.0) * 100, 1)
                bbox = None
                status_val = "identified"
                identified_by = "qwen"
                vlm_macros = vlm.get("per_100g")
                vlm_flagged = bool(vlm.get("flagged"))

    # ── Macro lookup: local DB -> Qwen's estimate -> MS2 text lookup ─────────
    clean_name = normalize_name(food_name)
    per100 = None
    macro_source = "none"

    try:
        db_food = lookup_food(db, clean_name)
        per100 = per_100g(db_food) if db_food else None
        if per100:
            macro_source = "db"
    except Exception:
        db.rollback()  # table not yet migrated; fall through to the LLM

    if per100 is None and vlm_macros and not vlm_flagged:
        per100 = vlm_macros
        macro_source = "qwen3-vl-2b"
        persist_llm_food(db, clean_name, per100)  # next scan of this food is a plain DB hit

    if per100 is None and clean_name not in ("", "unknown"):
        lk = await llm_client.lookup(clean_name, x_user_id)
        if lk and lk.get("per_100g") and not lk.get("flagged"):
            per100 = lk["per_100g"]
            macro_source = lk.get("source", "llm")
        elif lk is None:
            llm_timeout = True

    if per100 is None:
        per100 = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
        macro_source = "llm-timeout" if llm_timeout else "none"

    total_calories = round((weight / 100.0) * per100["calories"], 2)
    total_protein = round((weight / 100.0) * per100["protein_g"], 2)
    total_carbs = round((weight / 100.0) * per100["carbs_g"], 2)
    total_fat = round((weight / 100.0) * per100["fat_g"], 2)

    print(f"[Scan] user={target_uid} weight={weight}g yolo={yolo_status} ({result.get('reason', '')}) "
          f"-> '{clean_name}' identified_by={identified_by if clean_name != 'unknown' else 'none'} macros={macro_source}")

    payload = {
        "session_id": session_id,
        "status": status_val,
        "identified_by": identified_by if clean_name != "unknown" else "none",
        "macro_source": macro_source,
        "yolo_status": yolo_status,
        "food_label": clean_name.title(),
        "confidence": confidence_val,
        "weight_g": round(weight, 2),
        "calories": total_calories,
        "protein": total_protein,
        "carbs": total_carbs,
        "fat": total_fat,
        "reason": result.get("reason", ""),
        "user_id": x_user_id
    }

    # ── Save Meal Entry to PostgreSQL meal_logs Table ─────────────────────────
    try:
        if clean_name == "unknown" and not _LOG_UNKNOWN_SCANS:
            # nothing was recognised (YOLO and Qwen both gave up, or MS2 was down): a 0 kcal "Unknown" row only clutters the app
            raise _NotLogged()
        meal_entry = MealLog(
            user_id=target_uid,
            log_date=clock.today(),
            meal_type="Scale Capture",
            food_name=payload["food_label"],
            calories=payload["calories"],
            protein=payload["protein"],
            carbs=payload["carbs"],
            fat=payload["fat"],
            weight_g=payload["weight_g"],
            source=("llm-timeout" if macro_source == "llm-timeout"
                    else "esp32_qwen_vlm" if identified_by == "qwen" else "esp32_yolo")
        )
        db.add(meal_entry)
        db.commit()
        print(f"[Database] Logged meal #{meal_entry.id}: {meal_entry.food_name} ({meal_entry.calories} kcal) for user {target_uid}")

        # Live dashboard cache (<10 ms reads in MS3): canonical payload shared with MS3 and the DB trigger
        macros = sync_daily_macros(db, target_uid)
        print(f"[Redis] Synced user:{target_uid}:macros:{macros['date']} -> {macros['calories']:.1f} kcal total today")
    except _NotLogged:
        print("[Scan] not identified -> nothing logged (set LOG_UNKNOWN_SCANS=true to keep these)")
    except Exception as e:
        db.rollback()
        print(f"[Warning] Could not save to meal_logs: {e}")

    # ── Annotate and Save Image for Live Visual Inspection ───────────────────
    try:
        cv_img = cv2.imread(LATEST_RAW_PATH)
        if cv_img is not None:
            h, w, _ = cv_img.shape
            label_text = f"{payload['food_label']} ({payload['confidence']}%) | {payload['calories']} kcal | {payload['weight_g']}g"
            
            if bbox and len(bbox) == 4:
                x1, y1, x2, y2 = int(bbox[0]*w), int(bbox[1]*h), int(bbox[2]*w), int(bbox[3]*h)
                cv2.rectangle(cv_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(cv_img, label_text, (max(5, x1), max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 2)
            else:
                # Banner at the top
                cv2.rectangle(cv_img, (0, 0), (w, 30), (0, 0, 0), -1)
                cv2.putText(cv_img, label_text, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
                
            cv2.imwrite(LATEST_ANNOTATED_PATH, cv_img)
    except Exception as e:
        print(f"[Warning] Failed to annotate image: {e}")

    # Store result so ESP32 can poll it if needed
    _results[session_id] = payload

    return JSONResponse(content=payload)


# ── GET /api/v1/ingest/result/{session_id} ─────────────────────────────────
@app.get("/api/v1/ingest/result/{session_id}")
def get_ingest_result(session_id: str):
    result = _results.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No result found for session_id: {session_id}")
    return JSONResponse(content=result)
