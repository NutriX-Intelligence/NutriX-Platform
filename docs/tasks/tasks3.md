# Phase 3 Execution Tasks

> Based on the Mid-Semester Trial Run (`docs/trial_midSem.md`) and recent CV ingest fixes.

- [x] 3.1 Wrap CV Engine in a FastAPI app (`ms1/main.py`) exposing:
  - [x] `POST /api/v1/ingest/weight-frame` (receives multipart from gateway, calculates weight delta, triggers YOLO and DB)
  - [ ] `POST /api/v1/hitl/confirm` (user confirms/edits unidentified item)
  - [x] `GET /api/v1/barcode/{barcode}` (barcode lookup handler) — **moved to MS3 (Phase 5)**
  - [x] `POST /api/v1/ocr/upload` (OCR image to macros) — **moved to MS3 (Phase 5)**
- [x] 3.2 Add OpenCV barcode decode path inside `cv_engine.py` (using `pyzbar`) — **moved to MS3 (Phase 5)**
- [x] 3.3 Add PostgreSQL food lookup after identification 
  - [x] Includes exact matching against `foods` and `food_aliases`.
  - [x] Includes partial matching for trusted brands (`Whole Food` and `YOLO Generic`).
- [x] 3.4 Add OpenFoodFacts / USDA API fallback lookup (for barcode misses) — **moved to MS3 (Phase 5)**
- [x] 3.5 Add MS2 LLM nutrition lookup call (`POST http://llm-service:8003/api/v1/llm/lookup`) for unknown foods
- [x] 3.6 Add MS2 Vision call (`POST http://llm-service:8003/api/v1/llm/vision-infer`) when YOLO is unidentified / below `YOLO_CONF_THRESHOLD` (done in Phase 4; Qwen's label is logged directly, HitL confirmation deferred)
- [x] 3.7 Add PostgreSQL `meal_logs` INSERT after food confirmed
- [x] 3.7.1 Add Redis cache sync trigger update (Redis stream updates accurately with new daily totals)
- [ ] 3.8 Modify `retrain_yolo.py` to support `freeze=10` adapter-only retraining with per-user output path
- [ ] 3.9 Modify `hitl_engine.py` to save adapter weights path to `user_adapters` table after retraining
- [ ] 3.10 Implement Per-User Head Adapter loading in `cv_engine.py` (load user head from DB/disk, swap on inference)
- [ ] 3.11 Add execution trace logging to `audit_logs` table after each inference
- [x] 3.12 Write Dockerfile for MS1 (GPU-enabled base: `ultralytics/ultralytics`)
- [x] 3.13 Integration test: Full scale-to-DB flow end-to-end with a real image (`scripts/dev_capture.py` working flawlessly)
