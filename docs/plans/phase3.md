# Phase 3 — MS1: CV & Ingestion Service (Port 8001)

> **Goal:** Complete and wire the MS1 FastAPI service so that scale telemetry (`weight + JPEG`) flows
> end-to-end through the gateway, gets identified by YOLOv8, has macros resolved from the DB (with
> LLM/external API fallback), writes a verified meal log to PostgreSQL, triggers Redis sync, and
> the Per-User Adapter system is fully operational. Barcode lookup is handled separately and purely
> by passing a barcode string — no image-based barcode decoding in MS1.

**Phase Status:** Not Started
**Depends On:** Phase 1 (Complete), Phase 2 (Complete)
**Blocks:** Phase 5 (MS3 daily summary depends on meal_logs written by MS1), Phase 8 (ESP32 firmware test)

---

## Context and Architecture Alignment

From `MASTER_ARCHITECTURE.md` Layer 3, MS1's complete decision pipeline:

```
ESP32 POST weight + JPEG
        |
        v
  [No Barcode path — barcode comes from Flutter/Web frontend as text]
        |
        v
   YOLOv8 Inference (NutriX_yolo_custom.pt + per-user head adapter)
        |
        +-- Confidence >= 80% --> Local PostgreSQL food lookup
        |                               |
        |                 +-- Hit ------> calculate macros -> INSERT meal_log
        |                 +-- Miss -----> OpenFoodFacts/USDA API -> INSERT
        |                                       |
        |                               +-- Miss --> POST /api/v1/llm/lookup (MS2)
        |
        +-- Confidence < 80% --> POST /api/v1/llm/vision-infer (MS2)
                                         |
                                  Flutter confirmation prompt
                                         |
                               POST /api/v1/hitl/confirm
                                         |
                              Generate YOLO annotation -> retrain (freeze=10)
                              Save user_N_head.pt -> user_adapters table
```

### What Phase 3 Is NOT

- No barcode reading from images (`pyzbar` is **not** used for scale frames — barcode is sent as plain text string from Flutter/Web frontends to `GET /api/v1/barcode/{barcode}`)
- No direct user auth logic (user_id comes from `X-User-ID` header injected by the gateway)
- No business logic for meal planning or recipe ranking (those are MS3 responsibilities)
- MS2 (LLM) is NOT built yet in Phase 3 — MS1 calls to MS2 must gracefully handle `502` and fall back

---

## Clarifications & Design Decisions

### Barcode Design (Critical — User Clarified)

| Component | Who Does It | How |
|---|---|---|
| **Barcode scanning** (reading the QR/barcode from camera) | Flutter App (Dart) / Web (JS) | `simple_barcode_scanner` package in Flutter, or JS barcode library in browser |
| **Barcode lookup** (fetching product nutrition) | **MS1** via `GET /api/v1/barcode/{barcode}` | Receives the raw barcode string, queries OpenFoodFacts -> local DB -> MS2 LLM |
| **Barcode result caching** | MS1 (shared PostgreSQL) | Caches results in `barcode_cache` table for future hits |

> **Therefore:** `pyzbar` (image barcode decode) is **removed** from the MS1 pipeline for scale frames.
> The `GET /api/v1/barcode/{barcode}` endpoint receives the barcode as a URL path param — it does NOT
> receive an image.

### MS2 Call Handling (MS2 Not Built Yet)

Since Phase 4 (MS2) has not been implemented yet, all MS1 calls to MS2 endpoints must:
1. Set a 10-second timeout
2. On `ConnectError` / `502`: log the timeout in `audit_logs` with `source = "llm-timeout"`
3. Return a placeholder macro record and continue — never block the ingestion pipeline

### Per-User Adapter Loading

The `NutriXCVEngine` in `cv_engine.py` already has a solid mock and real inference pipeline.
What is **missing**:
- DB lookup for a user-specific head adapter weights path from `user_adapters` table
- Disk loading and hot-swapping of user head at inference time
- Fallback to global `NutriX_yolo_custom.pt` if no user adapter exists

### HitL Engine Import Fix

The existing `hitl_engine.py` has a **broken import**:
```python
from backend.services.ingestion.cv_engine import MealSession  # Wrong path
```
This must be changed to:
```python
from ms1_cv.cv_engine import MealSession  # Correct monorepo path
```

### retrain_yolo.py — Adapter-Only Mode (freeze=10)

The existing `retrain_yolo.py` does full retraining (no freeze). It must be modified to support
a `user_id` parameter that:
- Uses `freeze=10` (freeze layers 0-9 = backbone + neck)
- Outputs to `dataset/trained/user_{user_id}/`
- Saves only the final head `user_{user_id}_head.pt` (~400KB) to disk
- Writes a record to `user_adapters` table in PostgreSQL

---

## Delivery Checklist

### 3.1 FastAPI App Assembly (`ms1_cv/main.py`)

Currently `ms1_cv/main.py` only has a health check. This needs to expose all 4 MS1 routes.

**Endpoints to implement:**

| Method | Route | Handler | Auth |
|---|---|---|---|
| `POST` | `/api/v1/ingest/weight-frame` | Receives `weight` + `image` multipart | Device-Token (validated by gateway, `X-User-ID` injected) |
| `GET` | `/api/v1/barcode/{barcode}` | Barcode string lookup | JWT (`X-User-ID` injected) |
| `POST` | `/api/v1/ocr/upload` | Nutrition label image -> macros via MS2 | JWT |
| `POST` | `/api/v1/hitl/confirm` | User correction + adapter retrain trigger | JWT |

**Implementation notes:**
- Read `X-User-ID` from headers (injected by gateway) — never from query params
- All endpoints must return structured JSON with `status`, `source`, and `data` fields
- Use FastAPI `UploadFile` for multipart image uploads
- The `/health` endpoint already exists, preserve it

**File:** `ms1_cv/main.py`

---

### 3.2 Weight-Frame Ingestion Handler (`ms1_cv/services/ingest_handler.py`)

The core business logic for `POST /api/v1/ingest/weight-frame`. This is a new file, pulling the pipeline together.

**Full execution flow:**
```python
async def handle_weight_frame(weight: float, image: UploadFile, user_id: str, db: Session):
    # 1. Save image to temp file
    # 2. Load user adapter from DB (user_adapters table lookup by user_id)
    # 3. Run NutriXCVEngine.process_scale_event() with loaded model
    # 4a. If confidence >= 80%:
    #     -> lookup_food_from_db(food_name, db)
    #     -> If DB miss: lookup_from_external_apis(food_name)
    #     -> If still miss: call_ms2_llm_lookup(food_name)
    #     -> calculate macros = (weight_g / 100) * nutrients_per_100g
    #     -> INSERT into meal_logs
    #     -> append_audit_log(user_id, source, confidence, food_name)
    #     -> return {status: "logged", meal_log: ...}
    # 4b. If confidence < 80%:
    #     -> save image to dataset/pending/
    #     -> call_ms2_vision_infer(image_path)
    #     -> store pending_session in memory (keyed by session_id)
    #     -> return {status: "pending_hitl", candidate: ..., session_id: ...}
```

**File:** `ms1_cv/services/ingest_handler.py`

---

### 3.3 Barcode Lookup Handler (`ms1_cv/services/barcode_handler.py`)

This receives a **barcode string** (not an image) from `GET /api/v1/barcode/{barcode}`.

**Lookup Priority Chain:**
1. **Local PostgreSQL `barcode_cache` table**: Sub-millisecond. Return immediately on hit.
2. **OpenFoodFacts API** (`https://world.openfoodfacts.org/api/v2/product/{barcode}.json`): Free, covers most packaged products.
3. **USDA FoodData Central API** (`https://api.nal.usda.gov/fdc/v1/...`): Secondary lookup for USDA-registered products.
4. **MS2 LLM Lookup** (`POST /api/v1/llm/lookup` via internal httpx): For completely unknown products — uses product name from step 2/3 as the query.

**Port from MS3 barcode_service.py:**
The MS3 codebase (`ms3_user/NutriX-main/.../barcode_service.py`) has a rich 4-tier fallback
(OFF -> DuckDuckGo scraper -> Gemini AI -> local DB match) already implemented. This logic should be
**ported and adapted** into `ms1_cv/services/barcode_handler.py`, replacing the Gemini AI fallback
with MS2 LLM lookup (internal, no API cost).

**Response format:**
```json
{
  "status": "success",
  "source": "openfoodfacts",
  "barcode": "8901725130052",
  "product_name": "Haldiram's Aloo Bhujia",
  "brand": "Haldiram's",
  "nutrients_per_100g": {
    "calories": 550.0,
    "protein_g": 8.5,
    "carbs_g": 55.0,
    "fat_g": 34.0
  },
  "health_score": 42,
  "health_category": "Poor"
}
```

**File:** `ms1_cv/services/barcode_handler.py`

---

### 3.4 OCR Handler (`ms1_cv/services/ocr_handler.py`)

Receives a nutrition label image (`POST /api/v1/ocr/upload`) and extracts macro data.

**Implementation approach:**
- Pass the image to **MS2** (`POST /api/v1/llm/vision-infer` with an OCR prompt) — leverages multimodal LLM.
- Until MS2 is available: use lightweight local `pytesseract` OCR + regex parser as fallback.
- Parse `Calories`, `Protein`, `Carbohydrates`, `Fat`, `Sodium`, `Fibre` from OCR output.

**Pytesseract-based fallback regex targets:**
```python
patterns = {
    "calories":  r"(?:energy|calories)[^\d]*([\d.]+)\s*(?:kcal|kj)?",
    "protein_g": r"protein[^\d]*([\d.]+)\s*g",
    "carbs_g":   r"carbohydrate[^\d]*([\d.]+)\s*g",
    "fat_g":     r"(?:total\s+)?fat[^\d]*([\d.]+)\s*g"
}
```

**File:** `ms1_cv/services/ocr_handler.py`

---

### 3.5 HitL Confirm Handler (`ms1_cv/services/hitl_confirm_handler.py`)

Receives `POST /api/v1/hitl/confirm` after the user confirms or edits the AI candidate suggestion.

**Payload schema:**
```json
{
  "session_id": "abc123",
  "addition_index": 0,
  "confirmed_food_name": "Paneer Tikka",
  "confirmed_weight_g": 150.0
}
```

**Execution flow:**
1. Retrieve the `MealSession` from the in-memory session store by `session_id`
2. Call `NutriXHitlEngine.apply_user_correction(session, addition_index, confirmed_food_name, pending_image_path)`
3. Look up macros for `confirmed_food_name` from PostgreSQL -> external API -> MS2 LLM (same cascade as ingest)
4. Calculate macros: `(confirmed_weight_g / 100) * nutrients_per_100g`
5. INSERT into `meal_logs` table
6. Trigger `retrain_yolo_adapter(user_id, session)` as a **background task** (non-blocking)
7. Return `{status: "confirmed", meal_log: {...}}`

> **Session Store Note:** For now, use a simple in-memory `dict` keyed by `session_id`. In Phase 9+,
> this should migrate to Redis for multi-instance safety. This is acceptable for the single-node
> local phase.

**File:** `ms1_cv/services/hitl_confirm_handler.py`

---

### 3.6 Food Macro Lookup Service (`ms1_cv/services/food_lookup.py`)

Shared by both ingest and HitL handlers — abstracts the 3-tier food macro resolution cascade.

**Lookup Priority:**
1. **PostgreSQL `foods` + `food_nutrients` JOIN** by exact match, then alias match via `food_aliases`
2. **OpenFoodFacts / USDA FoodData Central** public APIs (by food name search, not barcode)
3. **MS2 LLM text lookup** (`POST http://ms2-llm:8003/api/v1/llm/lookup`)

**Normalization rule:**
- All returned values must be **per 100g** (`calories_per_100g`, `protein_g`, `carbs_g`, `fat_g`)
- Caller multiplies by `(weight_g / 100.0)` to get actual meal macros

**MS2 fallback resilience:**
- Hard timeout: 10 seconds using `httpx.AsyncClient`
- On timeout: `source = "llm-timeout"`, return a placeholder record with all macros = `0.0`
- Always log the attempt in `audit_logs`

**File:** `ms1_cv/services/food_lookup.py`

---

### 3.7 CV Engine Adapter Swapping (`ms1_cv/cv_engine.py`)

The existing `NutriXCVEngine` does not yet implement per-user head swapping.

**Changes needed:**
```python
class NutriXCVEngine:
    def load_user_adapter(self, user_id: str, db: Session) -> bool:
        """
        Checks user_adapters table for a valid adapter for this user.
        If found, loads user_{user_id}_head.pt and hot-swaps into the model.
        Returns True if user adapter loaded, False if using global baseline.
        """
        ...

    def process_scale_event(
        self,
        image_path: str,
        current_weight: float,
        session: MealSession,
        user_id: str = None,   # NEW
        db: Session = None     # NEW
    ) -> Tuple[bool, Dict[str, Any]]:
        # Calls self.load_user_adapter(user_id, db) at start
        ...
```

**File:** `ms1_cv/cv_engine.py` (modify existing)

---

### 3.8 HitL Engine Import Fix & Per-User Dataset Paths (`ms1_cv/hitl_engine.py`)

**Fix broken import:**
```python
# FROM (broken):
from backend.services.ingestion.cv_engine import MealSession

# TO (correct):
from ms1_cv.cv_engine import MealSession
```

**Per-user dataset paths:**
Modify `apply_user_correction()` to accept optional `user_id` and write to:
```
dataset/trained/user_{user_id}/image.jpg
dataset/trained/user_{user_id}/image.txt
```
This prevents class ID collisions between users.

**File:** `ms1_cv/hitl_engine.py` (modify existing)

---

### 3.9 retrain_yolo.py — Adapter-Only Mode with freeze=10 (`ms1_cv/retrain_yolo.py`)

The existing `run_retraining()` does full fine-tuning. Add a new function:

```python
def run_adapter_retraining(user_id: str, db: Session) -> str:
    """
    Runs freeze=10 adapter-only fine-tuning for a specific user.
    Saves only the final head layers as user_{user_id}_head.pt (~400KB).
    Returns the saved weights path.
    """
    model = YOLO("ms1_cv/NutriX_yolo_custom.pt")
    results = model.train(
        data=f"dataset/trained/user_{user_id}/data.yaml",
        epochs=3,
        freeze=10,        # Freeze layers 0-9 (backbone + neck)
        imgsz=320,
        batch=2,
        device="cpu",    # or "cuda" if GPU available
        project=f"runs/user_{user_id}",
        name="adapter",
        degrees=180.0,
        fliplr=0.5,
        flipud=0.5
    )
    head_weights_path = f"dataset/adapters/user_{user_id}_head.pt"
    # Copy from runs/user_{user_id}/adapter/weights/best.pt
    # INSERT/UPDATE user_adapters table in PostgreSQL
    return head_weights_path
```

**File:** `ms1_cv/retrain_yolo.py` (modify existing)

---

### 3.10 Audit Log Writer (`ms1_cv/services/audit_writer.py`)

Shared utility to write every inference trace to the `audit_logs` PostgreSQL table.

**What is logged after every ingest/barcode/HitL event:**

| Column | Value |
|---|---|
| `user_id` | From `X-User-ID` header |
| `service` | `"ms1_cv"` |
| `event_type` | `"ingest"` / `"barcode_lookup"` / `"hitl_confirm"` / `"ocr"` |
| `input_hash` | SHA256 of image bytes (for deduplication) |
| `predicted_class` | Top YOLO class name |
| `confidence` | YOLO confidence float |
| `source` | `"yolo"` / `"openfoodfacts"` / `"usda"` / `"ms2_llm"` / `"llm-timeout"` / `"cache"` |
| `faithfulness_score` | `NULL` initially — populated later by MS4 Meta-Auditor |
| `created_at` | UTC timestamp |

**File:** `ms1_cv/services/audit_writer.py`

---

### 3.11 Dockerfile Hardening (`ms1_cv/Dockerfile`)

The existing `Dockerfile` uses `ultralytics/ultralytics:latest` as the base — correct for GPU.

**Changes needed:**
- Add `tesseract-ocr` system package (for OCR fallback): `apt-get install tesseract-ocr`
- Add `libzbar0` system package
- Run as non-root user (`ms1:ms1`) for security parity with gateway
- Add `HEALTHCHECK` directive pointing to `/health`

**File:** `ms1_cv/Dockerfile` (modify existing)

---

### 3.12 In-Memory Session Store (`ms1_cv/session_store.py`)

A simple module-level dict for storing active `MealSession` objects keyed by `session_id`.

```python
# In-memory store: session_id -> MealSession
_sessions: Dict[str, MealSession] = {}

def create_session(user_id: str) -> MealSession: ...
def get_session(session_id: str) -> Optional[MealSession]: ...
def delete_session(session_id: str) -> None: ...
```

> **Note:** Intentionally simple for Phase 3. Phase 9 will migrate to Redis TTL keys for
> multi-instance safety.

**File:** `ms1_cv/session_store.py`

---

### 3.13 Integration Tests (`ms1_cv/tests/test_ms1_ingest.py`)

Tests that cover the full ingest pipeline without requiring live GPU or MS2:

| Test | What It Validates |
|---|---|
| `test_health_check` | `GET /health` returns `200 OK` |
| `test_ingest_high_confidence_mock` | Mock YOLOv8 >=80% -> DB food lookup -> meal_log INSERT |
| `test_ingest_low_confidence_pending` | Mock YOLOv8 <80% -> returns `pending_hitl` status |
| `test_hitl_confirm_flow` | HitL confirm with mock session -> meal_log INSERT + adapter retrain queued |
| `test_barcode_lookup_cached` | Cached barcode hit -> returns from `barcode_cache` without external call |
| `test_barcode_lookup_off_api` | Mock OpenFoodFacts response -> correct macro extraction |
| `test_barcode_lookup_ms2_fallback` | OFF miss + MS2 `502` -> returns `llm-timeout` placeholder |
| `test_audit_log_written` | After ingest, `audit_logs` table has a new record |

Use `mock_mode=True` on `NutriXCVEngine` and `respx` for mocking external HTTP calls.

**File:** `ms1_cv/tests/test_ms1_ingest.py`

---

## Open Questions for User

> Please confirm the following before implementation begins:

1. **Session Persistence**: The `MealSession` (tracking weight delta and pending HitL state) is stored
   in-memory in a Python dict. If the MS1 container restarts, pending sessions are lost and the user
   would need to re-scan. Is this acceptable for Phase 3?

2. **OCR dependency**: The OCR handler requires `tesseract-ocr` (~50MB) in the Docker container.
   Should we:
   - **a.** Include it (pytesseract fallback works without MS2)
   - **b.** Skip for now — OCR always routes to MS2 LLM vision-infer (returns `502` until Phase 4)

3. **retrain_yolo.py background task**: After HitL confirm, adapter retraining (2-5 min on CPU or
   ~30s on GPU) runs as a `BackgroundTask`. User gets immediate response; new adapter loads on
   **next** scale event. Is this acceptable, or should we return a `task_id` for polling?

4. **External API Keys**: USDA FoodData Central requires a free API key (`USDA_API_KEY` env var).
   OpenFoodFacts requires no key. Should USDA be included in Phase 3 or deferred?

---

## Complete Route Table for MS1 (Phase 3)

| Method | Route | Handler File | Calls MS2? | DB Write? |
|---|---|---|---|---|
| `GET` | `/health` | `main.py` | No | No |
| `POST` | `/api/v1/ingest/weight-frame` | `ingest_handler.py` | Yes (vision-infer, optional) | Yes (meal_logs, audit_logs) |
| `GET` | `/api/v1/barcode/{barcode}` | `barcode_handler.py` | Yes (llm/lookup, fallback) | Yes (barcode_cache) |
| `POST` | `/api/v1/ocr/upload` | `ocr_handler.py` | Yes (vision-infer) | No |
| `POST` | `/api/v1/hitl/confirm` | `hitl_confirm_handler.py` | No | Yes (meal_logs, user_adapters) |

---

## File Inventory

### MODIFY Existing Files

| File | What Changes |
|---|---|
| `ms1_cv/main.py` | Add all 4 route handlers, lifespan for model pre-load |
| `ms1_cv/cv_engine.py` | Add `load_user_adapter()`, pass `user_id + db` to `process_scale_event()` |
| `ms1_cv/hitl_engine.py` | Fix import path, add per-user dataset directory support |
| `ms1_cv/retrain_yolo.py` | Add `run_adapter_retraining(user_id, db)` with `freeze=10` |
| `ms1_cv/Dockerfile` | Add tesseract-ocr, non-root user, HEALTHCHECK |

### NEW Files

| File | Purpose |
|---|---|
| `ms1_cv/services/__init__.py` | Package marker |
| `ms1_cv/services/ingest_handler.py` | Weight-frame ingestion orchestrator |
| `ms1_cv/services/barcode_handler.py` | Barcode string lookup (OFF -> USDA -> MS2 LLM) |
| `ms1_cv/services/ocr_handler.py` | Nutrition label image -> macros |
| `ms1_cv/services/hitl_confirm_handler.py` | HitL confirmation flow |
| `ms1_cv/services/food_lookup.py` | Shared 3-tier food macro resolution |
| `ms1_cv/services/audit_writer.py` | Audit log writer to `audit_logs` table |
| `ms1_cv/session_store.py` | In-memory `MealSession` store |
| `ms1_cv/tests/test_ms1_ingest.py` | Integration test suite |

---

## Implementation Order

```
1.  Fix hitl_engine.py import (trivial, unblocks everything else)
2.  Create session_store.py (needed by both ingest and HitL handlers)
3.  Create services/food_lookup.py (shared dependency — build first)
4.  Create services/audit_writer.py (shared dependency)
5.  Create services/ingest_handler.py (uses food_lookup + audit_writer + cv_engine)
6.  Modify cv_engine.py adapter loading (used by ingest_handler)
7.  Modify retrain_yolo.py adapter mode (used by hitl_confirm_handler)
8.  Create services/hitl_confirm_handler.py (uses hitl_engine + retrain + food_lookup)
9.  Create services/barcode_handler.py (standalone, uses food_lookup)
10. Create services/ocr_handler.py (standalone, calls MS2)
11. Update ms1_cv/main.py (wire all routes, lifespan model pre-load)
12. Update ms1_cv/Dockerfile
13. Write ms1_cv/tests/test_ms1_ingest.py
```

---

## Verification Plan

### Manual Verification

With MS1 running locally (`PYTHONPATH=. uvicorn ms1_cv.main:app --port 8001 --reload`):

```bash
# 1. Health check
curl http://localhost:8001/health
# Expected: {"status": "healthy", "service": "ms1_cv"}

# 2. Barcode lookup (known Indian packaged snack)
curl -H "X-User-ID: 1" http://localhost:8001/api/v1/barcode/8901725130052
# Expected: product_name populated, nutrients per 100g from OpenFoodFacts

# 3. Weight-frame ingest with mock image
curl -X POST http://localhost:8001/api/v1/ingest/weight-frame \
  -H "X-User-ID: 1" \
  -F "weight=180.5" \
  -F "image=@apple_test.jpg"
# Expected: {"status": "logged", ...} or {"status": "pending_hitl", ...}

# 4. Verify meal_logs table
psql -U nutrix_user -d nutrix_db -c \
  "SELECT food_name, weight_g, calories, source FROM meal_logs ORDER BY created_at DESC LIMIT 5;"

# 5. Verify audit_logs table
psql -U nutrix_user -d nutrix_db -c \
  "SELECT event_type, predicted_class, confidence, source FROM audit_logs ORDER BY created_at DESC LIMIT 5;"
```

### Gateway -> MS1 End-to-End

With both Gateway (port 8000) and MS1 (port 8001) running:

```bash
# Scale frame via gateway (Device-Token auth)
curl -X POST http://localhost:8000/api/v1/ingest/weight-frame \
  -H "Device-Token: NutriX_ESP32_SECURE_TOKEN" \
  -H "User-ID: 1" \
  -F "weight=180.5" \
  -F "image=@apple_test.jpg"

# Barcode via gateway (JWT auth)
TOKEN=$(python gateway/generate_token.py | tail -2 | head -1 | awk '{print $NF}')
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/barcode/8901725130052"
```

### Automated Tests

```bash
pytest ms1_cv/tests/ -v
# Expected: All 8 tests pass
```

---

## Technical Debt Noted (Deferred to Later Phases)

| Issue | Deferred To |
|---|---|
| In-memory session dict must migrate to Redis TTL keys for multi-container safety | Phase 9 |
| USDA API fallback skipped if `USDA_API_KEY` not set | Optional in Phase 3 |
| `food_nutrients` values may not be normalized to per-100g (Phase 1 deferred debt) | Phase 5 cleanup |
| Head adapter `.pt` files stored on local disk — needs shared NFS/S3 for multi-machine | Phase 9 |
