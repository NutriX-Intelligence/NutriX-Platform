# Phase 4 Execution Tasks — MS2: LLM Nutrition & Vision Service (Port 8003)

> Based on `docs/MASTER_PLAN.md` Phase 4 and `docs/MASTER_ARCHITECTURE.md` (Microservice 2).
> Phase 3 is paused at the HitL / per-user adapter work (`docs/tasks/tasks3.md`). MS2 is built first so
> that MS1 has a local VLM fallback when YOLO cannot identify a food.

## Target Flow

```
ESP32 image + weight ──> MS1 YOLO inference
                           │
                           ├─ identified (conf ≥ YOLO_CONF_THRESHOLD, class not suppressed)
                           │      └─> DB lookup ─> macros ─> INSERT meal_logs ─> Redis sync
                           │
                           └─ unidentified (conf < YOLO_CONF_THRESHOLD, no detection, or class ∈ {lassi, kulfi})
                                  └─> POST MS2 /api/v1/llm/vision-infer  (image + weight)
                                         Qwen3-VL-2B returns { food_name, per-100g macro estimate }
                                         │
                                         └─> DB lookup on food_name (exact → alias → partial)
                                                ├─ hit  ─> DB macros (source of truth)
                                                └─ miss ─> Qwen macros, INSERT into foods as "LLM Inferred"
                                         ─> INSERT meal_logs ─> Redis sync   (same path as YOLO)
```

## Design Decisions (agreed)

| Topic | Decision |
|---|---|
| **Model** | **Qwen3-VL-2B-Instruct** via Hugging Face `transformers`, bf16 on CUDA. No Gemini, no Ollama |
| **Model location** | Stays in the Windows HF cache, read from WSL through `/mnt/c/Users/HP/.cache/huggingface/hub/models--Qwen--Qwen3-VL-2B-Instruct/snapshots/<hash>` and set via `VLM_MODEL_PATH`. Measured `/mnt/c` read speed is ~214 MB/s, so a one-time cold load takes ~20 s. Copying into WSL would still use C: disk |
| **Residency** | Load **once at MS2 startup** and keep it resident. Measure VRAM with MS1 + MS2 both up. If it's too tight, switch to on-demand load/unload (the pattern from the reference `VLMEngine`) behind a config flag |
| **One call per frame** | Qwen returns the food label **and** per-100 g macros (kcal, protein, carbs, fat) in one JSON response |
| **Macro source of truth** | DB first. Qwen macros are used only on a DB miss, then persisted (`brand="LLM Inferred"`, `food_code="LLM_<slug>"`) so the next lookup hits the DB |
| **Label space** | Free-form food name, with no fixed class list in the prompt. The DB has ~1,880 foods (123 wholeFoods + 1,460 Indian_Food_DF + 144 UK + 97 Indian nutrition + 54 US, pre-dedup); listing them would add >10k tokens per call |
| **YOLO hint** | YOLO's low-confidence guess is passed to Qwen as a hint, **except** for suppressed classes (lassi/kulfi), so it can't bias Qwen toward the same mistake |
| **Lassi/kulfi fix** | If YOLO's top detection is lassi or kulfi, treat the frame as unidentified. The list is configurable via `YOLO_SUPPRESSED_CLASSES=lassi,kulfi`. No next-best-box fallback for now (that needs YOLO re-testing) |
| **HitL** | Skipped this phase. No `/hitl/confirm`, no confirmation step. Qwen's answer is logged directly |
| **Timeouts** | MS1 → MS2 timeout of **30 s**. The gateway already allows 60 s for `weight-frame` |
| **YOLO threshold** | Configurable via `YOLO_CONF_THRESHOLD`; raised from the 0.3 testing value to **0.5** now that the VLM fallback exists |

---

## 4.0 Prerequisites (user-run)
- [x] 4.0.1 Start infra: `docker compose up -d postgres redis`
- [x] 4.0.2 Install VLM deps into the WSL `.venv`: `pip install "transformers>=4.57" accelerate qwen-vl-utils`
- [x] 4.0.3 Add the new env keys to `.env` and `.env.example`: `VLM_MODEL_PATH`, `VLM_MAX_NEW_TOKENS`, `VLM_MAX_PIXELS`, `VLM_KEEP_LOADED=true`, `MS2_TIMEOUT_S=30`, `YOLO_SUPPRESSED_CLASSES=lassi,kulfi`
- [ ] 4.0.4 Check the real food count: `SELECT count(*) FROM foods;` (the plan assumes ~1,880)

## 4.1 MS2 Scaffolding
- [x] 4.1 Config module (`ms2_llm/config.py`)
  - [x] Load `.env` (same pattern as `gateway/config.py`)
  - [x] Expose `VLM_MODEL_PATH` (fallback: the HF id `Qwen/Qwen3-VL-2B-Instruct`), `VLM_MAX_NEW_TOKENS` (default ~128), `VLM_MAX_PIXELS` (default 480×640), `VLM_KEEP_LOADED`
- [x] 4.2 Pydantic schemas (`ms2_llm/schemas.py`)
  - [x] `NutritionPer100g { calories, protein_g, carbs_g, fat_g }`
  - [x] `VisionInferResponse { food_name, confidence?, per_100g, source: "qwen3-vl-2b", latency_ms, flagged }`
  - [x] `LookupRequest { food_name }` / `LookupResponse { food_name, per_100g, source }`

## 4.2 VLM Engine (`ms2_llm/vlm_engine.py`)
- [x] 4.3 Port the reference `VLMEngine` (transformers + `qwen_vl_utils.process_vision_info`)
  - [x] Drop the `frame_request.flag` pull mechanism; the image arrives as bytes over HTTP
  - [x] `load()` at FastAPI lifespan startup; log load time and `torch.cuda.memory_allocated()`
  - [x] `infer(image: PIL.Image | None, prompt: str) -> str` with `torch.inference_mode()`, low temperature (deterministic, `do_sample=False`)
  - [x] A single `asyncio.Lock` serialises GPU access; run blocking `generate` in a threadpool (`run_in_threadpool`)
  - [x] When `VLM_KEEP_LOADED=false`, load per call and free afterwards with `del` + `gc.collect()` + `torch.cuda.empty_cache()`
- [x] 4.4 Prompts (`ms2_llm/prompts.py`)
  - [x] Vision prompt: "Identify the single main food item on the scale. Return ONLY JSON: `{food_name, confidence, calories_per_100g, protein_g, carbs_g, fat_g}`". Include the YOLO hint line only when one is provided
  - [x] Text lookup prompt: the same JSON contract, without the image
  - [x] Defaults live in code; read an override from `system_prompt_registry` (`vision_infer_v2`, `nutrition_lookup_v2`) when the DB is up, and add both keys to `shared/seeders/seed_prompts.py`
- [x] 4.5 Output parsing and guardrails (`ms2_llm/validation.py`)
  - [x] Strip markdown fences, extract the first `{...}` block, validate with Pydantic
  - [x] Normalise `food_name` (lowercase, strip, collapse spaces)
  - [x] Sanity bounds: `0 ≤ kcal ≤ 900` per 100 g, macros ≥ 0, `P + C + F ≤ 100`
  - [x] Atwater check: `|4P + 4C + 9F − kcal| / kcal ≤ 0.25`. On failure, keep the label but set `flagged=true` (and don't persist the macros to `foods`)
  - [x] On unparseable output, retry once; then return `food_name="unknown"` with `flagged=true`

## 4.3 MS2 Endpoints (`ms2_llm/main.py`)
- [x] 4.6 Extract MS1's 3-step DB lookup (exact → alias → trusted partial) from `ms1_cv/main.py` into `shared/food_lookup.py`, plus `persist_llm_food(...)` (upsert on `food_code`, plus a `food_aliases` row when the raw name differs)
- [x] 4.7 `POST /api/v1/llm/vision-infer` (multipart: `image`, `weight`, optional `yolo_hint`)
  - [x] Returns Qwen's label and macro estimate. MS2 does **not** write `meal_logs` (MS1 owns that)
- [x] 4.8 `POST /api/v1/llm/lookup`: text-only food name to per-100 g macros (DB-first, then Qwen, then persist). Replaces MS1's hardcoded `sample_kcal` fallback
- [x] 4.9 Audit logging via `shared/audit.log_audit_event` (`service="ms2"`, `operation` = `llm_vision` / `llm_lookup`, with confidence, latency, flagged, and the parsed output in `output_summary`) through `BackgroundTasks`
- [x] 4.10 `/health`: add a `vlm` check (loaded?, device, VRAM allocated/reserved)

## 4.4 MS1 Changes
- [x] 4.11 Lassi/kulfi suppression in `ms1_cv/cv_engine.py`
  - [x] Read `YOLO_SUPPRESSED_CLASSES` (default `lassi,kulfi`)
  - [x] If the top detection's class is in the set, route to `_handle_failed_detection` with reason `"Suppressed class: <name>"` and **no** `fallback_class` hint
- [x] 4.12 MS2 client (`ms1_cv/llm_client.py`): `httpx` with a `MS2_TIMEOUT_S` (30 s) timeout. Returns `None` on any failure
- [x] 4.13 In `ingest_weight_frame` (`ms1_cv/main.py`)
  - [x] If unidentified, call `vision-infer` (with the YOLO hint when allowed)
  - [x] Run Qwen's `food_name` through `shared/food_lookup.py`. On a hit, use DB macros; on a miss, use Qwen's macros and persist them (unless flagged)
  - [x] `meal_logs.source`: `"esp32_yolo"` vs `"esp32_qwen_vlm"`. Include `identified_by` (`yolo` / `qwen`) in the response payload
  - [x] If MS2 is unreachable or times out, keep the current behaviour (log as `Unknown`) with `source="llm-timeout"`
- [x] 4.14 Remove the hardcoded `sample_kcal` dict and default 100 kcal; use `/llm/lookup` for YOLO-identified foods that miss the DB

## 4.5 Packaging, Tests, Docs
- [x] 4.15 `ms2_llm/requirements.txt`: add `pillow`, `python-multipart`, `pydantic`; remove the unused `ollama`. *Deviation:* the heavy GPU deps (`transformers`, `accelerate`, `qwen-vl-utils`) live in `ms2_llm/requirements-vlm.txt` (installed by the Dockerfile; `torch` comes from the CUDA base image) so CI doesn't download multi-GB wheels. `torch`/`transformers` are imported lazily
- [x] 4.16 `ms2_llm/Dockerfile`: CUDA base image, model mounted as a volume (never baked into the image). Add a GPU reservation and `depends_on` postgres/redis for `ms2-llm` in `docker-compose.yml`
- [x] 4.17 Unit tests (`ms2_llm/tests/`; 35 tests pass). These must pass in CI with **no** GPU, model, or Postgres
  - [x] Mock `VLMEngine.infer`; cover parsing with fences and junk text, guardrail rejection, the DB-hit vs miss path, and the suppressed-class → unidentified path in `cv_engine`
  - [x] Keep `test_health.py` passing when the model isn't loaded (the CI path)
- [x] 4.18 Integration script `scripts/test_ms2.py`: send a sample image (including a lassi/kulfi misclassification frame) to `vision-infer`, print the label, macros, latency and VRAM, then do a text lookup of a known and an unknown dish
- [x] 4.19 VRAM measurement: record steady-state and peak with MS1 + MS2 running (`nvidia-smi`), then decide whether to keep `VLM_KEEP_LOADED=true`. **Result:** ~4.5 GB of 6.1 GB (73 %) with MS1 + MS2 loaded, ~1.6 GB headroom, so the model stays resident
- [x] 4.20 Docs
  - [x] Add an MS2 section to `docs/testing/PIPELINE_2_SOFTWARE.md`. Run MS2 **without `--reload`**, since each reload re-reads the 4 GB model (~20 s)
  - [x] Tick off Phase 4 in `docs/MASTER_PLAN.md`
  - [x] Update `AI_CONTEXT.md` so "current focus" reflects the Phase 4 pivot

---

## Out of Scope (deferred)
- HitL confirmation (`/hitl/confirm`), per-user adapters, retraining (tasks3 3.1, 3.8–3.10)
- Using YOLO's next-best non-suppressed detection (needs YOLO re-testing)
- `POST /api/v1/llm/generate` for MS4 agents (add in Phase 6; the engine supports text-only prompts already)
- Offline retry queue for failed MS2 calls
- vLLM / production serving, Gemini or any cloud fallback
