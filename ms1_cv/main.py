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
from shared.health import check_health
from shared.models import Food, FoodNutrient, MealLog, User
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

# Shared engine instance (lazy-loaded on first request)
_engine: Optional[NutriXCVEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load the YOLO model at startup so first request is fast."""
    global _engine
    _engine = NutriXCVEngine(model_path=_MODEL_PATH, confidence_threshold=0.5)
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
    session_id = str(uuid.uuid4())

    # Save uploaded image to temp file and latest_raw.jpg
    suffix = os.path.splitext(image.filename or "frame.jpg")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(image.file, tmp)
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

    # Build the response payload
    if success and result.get("status") == "identified":
        addition = result["addition"]
        food_name = addition["food_name"]
        confidence_val = round(addition["confidence"] * 100, 1)
        bbox = addition.get("bounding_box")  # [xmin, ymin, xmax, ymax] normalized
        
        # ── Database Lookup for Calories ────────────────────────────────────
        clean_name = food_name.replace("_", " ").strip()
        calories_per_100g = 0.0
        
        try:
            db_food = db.query(Food).filter(
                (Food.name.ilike(f"%{clean_name}%")) | (Food.name.ilike(f"%{food_name}%"))
            ).first()
            if db_food and db_food.nutrients:
                calories_per_100g = db_food.nutrients.energy_kcal or 0.0
        except Exception:
            pass  # Fallback gracefully if table not yet migrated
            
        # Standard fallback calorie lookup
        if calories_per_100g <= 0.0:
            sample_kcal = {
                "apple": 52.0, "banana": 89.0, "roti": 264.0, "bread": 265.0,
                "rice": 130.0, "cucumber": 15.0, "tomato": 18.0, "mango": 60.0,
                "paneer": 296.0, "paneer tikka": 240.0, "paneer_tikka": 240.0,
                "lassi": 85.0, "sweet lassi": 89.0, "salted lassi": 45.0,
                "dosa": 168.0, "idli": 140.0, "samosa": 262.0, "biryani": 160.0,
                "dal": 116.0, "chole": 164.0, "rajma": 140.0, "poha": 130.0,
                "upma": 135.0, "vada pav": 289.0, "pav bhaji": 150.0,
                "orange": 47.0, "egg": 155.0, "chicken": 239.0
            }
            calories_per_100g = sample_kcal.get(clean_name.lower(), sample_kcal.get(food_name.lower(), 120.0))
            
        total_calories = round((weight / 100.0) * calories_per_100g, 2)
        
        payload = {
            "session_id": session_id,
            "status": "identified",
            "food_label": clean_name.title(),
            "confidence": confidence_val,
            "weight_g": round(weight, 2),
            "calories": total_calories,
            "user_id": x_user_id
        }
    else:
        # Fallback handling
        fallback_name = (result.get("fallback_class") or "unknown").replace("_", " ").strip()
        confidence_val = round((result.get("addition", {}) or {}).get("confidence", 0.0) * 100, 1)
        fallback_cal_per_100g = 100.0
        total_calories = round((weight / 100.0) * fallback_cal_per_100g, 2)
        bbox = (result.get("addition", {}) or {}).get("bounding_box")
        
        payload = {
            "session_id": session_id,
            "status": result.get("status", "unidentified"),
            "food_label": fallback_name.title(),
            "confidence": confidence_val,
            "weight_g": round(weight, 2),
            "calories": total_calories,
            "reason": result.get("reason", ""),
            "user_id": x_user_id
        }

    # ── Save Meal Entry to PostgreSQL meal_logs Table ─────────────────────────
    try:
        target_uid = 1
        if x_user_id and x_user_id.isdigit():
            target_uid = int(x_user_id)
            
        usr = db.query(User).filter(User.id == target_uid).first()
        if not usr:
            usr = User(id=target_uid, name="Smart Scale User", email=f"user_{target_uid}@nutrix.local")
            db.add(usr)
            db.commit()
            
        meal_entry = MealLog(
            user_id=target_uid,
            log_date=datetime.utcnow().date(),
            meal_type="Scale Capture",
            food_name=payload["food_label"],
            calories=payload["calories"],
            protein=round((weight / 100.0) * 3.5, 2),
            carbs=round((weight / 100.0) * 12.0, 2),
            fat=round((weight / 100.0) * 2.5, 2),
            weight_g=payload["weight_g"],
            source="esp32_smart_scale"
        )
        db.add(meal_entry)
        db.commit()
        print(f"[Database] Logged meal #{meal_entry.id}: {meal_entry.food_name} ({meal_entry.calories} kcal) for user {target_uid}")
        
        # ── Synchronize with Redis Cache (<10ms fast read for Flutter App) ───
        try:
            from shared.redis_client import set_daily_macros, publish_event
            today_str = datetime.utcnow().date().isoformat()
            today_meals = db.query(MealLog).filter(
                MealLog.user_id == target_uid,
                MealLog.log_date == datetime.utcnow().date()
            ).all()
            
            tot_cal = sum(m.calories for m in today_meals)
            tot_prot = sum(m.protein for m in today_meals)
            tot_carb = sum(m.carbs for m in today_meals)
            tot_fat = sum(m.fat for m in today_meals)
            
            macro_data = {
                "user_id": target_uid,
                "date": today_str,
                "calories": round(tot_cal, 2),
                "protein_g": round(tot_prot, 2),
                "carbs_g": round(tot_carb, 2),
                "fat_g": round(tot_fat, 2),
                "meals_count": len(today_meals),
                "latest_item": payload["food_label"]
            }
            
            set_daily_macros(target_uid, today_str, macro_data)
            publish_event(f"macro_updates:{target_uid}", macro_data)
            print(f"[Redis] Synced user:{target_uid}:macros:{today_str} -> {tot_cal:.1f} kcal total today")
        except Exception as re_err:
            print(f"[Warning] Redis sync skipped: {re_err}")
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
