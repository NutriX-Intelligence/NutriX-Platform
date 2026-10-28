# NutriX Project: Master Claude AI Handover Context (v2.0)

> **Document:** `docs/handoff2.md`  
> **Date:** October 28, 2026  
> **Status:** Phase 0–2, Phase 4 (MS2 LLM), and Phase 5 (MS3 User & Regional Integration) are **100% COMPLETE & VERIFIED**.  
> **Next Focus:** Phase 6 (MS4 Multi-Agent Clinical Guardian) & Phase 3 HitL / LoRA Adapters.

---

## 1. Executive Instructions for the New Claude Session

Welcome to the **NutriX** development workspace. You are continuing development on the NutriX platform. 

### Mandatory Operating Constraints (Non-Negotiable)
1. **Authoritative Runtime:** The **ONLY** active execution environment is **WSL2 (Ubuntu)** at `/home/harsh/Nutrix`.  
   Windows `C:\` or `C:\MAIN\Project\CalCount` is a mirrored repository mount — never execute builds or install packages directly on Windows.
2. **Execution Directives:** **DO NOT RUN COMMANDS THAT MODIFY THE SYSTEM AUTOMATICALLY.** Provide the exact terminal commands for the user to execute in their WSL2 terminal.
3. **Python Environment:** Always use `/home/harsh/Nutrix/.venv` and prefix executions with `PYTHONPATH=.`.
4. **Service Port Allocations:**
   * **Port 8000:** API Gateway (`gateway.main:app`)
   * **Port 8001:** MS1 Vision & Ingestion (`ms1_cv.main:app`)
   * **Port 8002:** MS3 User, Regional Analytics & Barcode/OCR (`ms3_user.main:app`)
   * **Port 8003:** MS2 Local VLM & Nutrition LLM (`ms2_llm.main:app`)
   * **Port 8004:** MS4 Multi-Agent Clinical Guardian (`ms4_agents.main:app`)
   * **Port 5432:** PostgreSQL (`nutrix-postgres` Docker container)
   * **Port 6379:** Redis (`nutrix-redis` Docker container)

---

## 2. Project State & Phase Progress Matrix

| Phase | Description | Status | Key Deliverables & Artifacts |
|---|---|---|---|
| **Phase 0** | Repo Scaffolding & Monorepo Setup | **Completed** | Monorepo layout, Dockerfiles, docker-compose, shared models, CI stubs |
| **Phase 1** | Data & Database Foundation | **Completed** | PostgreSQL Alembic migrations 001 & 002, 1,886 foods, 4,586 recipes, 3,355 fast food items |
| **Phase 2** | API Gateway (Port 8000) | **Completed** | Token authentication, reverse proxy, SSE streaming, 46/46 unit tests passing |
| **Phase 3** | MS1 Vision & Ingestion (Port 8001) | **Core Completed** | YOLOv8 123-class `best.pt`, scale delta guard ($\Delta \ge 0.5\text{g}$), VLM fallback client. *(HitL LoRA adapters paused)* |
| **Phase 4** | MS2 LLM Nutrition & Vision (Port 8003) | **Completed** | Qwen3-VL-2B resident in bf16 on RTX 3050, Atwater check, DB auto-persistence, text lookup, text generator |
| **Phase 5** | MS3 User & Regional Integration (Port 8002) | **Completed** | 54 dual-routed endpoints (canonical `/api/v1` + legacy), JWT numeric `sub`, 3-tier AI fallback (Gemini → Qwen → Canned), SSE live stream, 159 tests passing |
| **Phase 6** | MS4 Multi-Agent Clinical Guardian (Port 8004) | **Upcoming** | Event-driven agent tiers: Outlier Guardian, Clinical MDT, Meta-Auditor, OR-Tools dietetic optimization |
| **Phase 7** | Mobile Application (Flutter) | **Contract Ready** | Complete 57-path API contract documented in `docs/API_CONTRACT.md` and `docs/APP_HANDOFF.md` |

---

## 3. Deep-Dive: What Was Built in Phase 4 (MS2 LLM & Vision Service)

MS2 (`ms2_llm/`) was built to eliminate out-of-vocabulary and low-confidence failures in the computer vision pipeline.

### Core Architecture & Implementation
* **Model Engine (`ms2_llm/vlm_engine.py`):** Hosts **Qwen3-VL-2B-Instruct** locally using Hugging Face `transformers` in `bfloat16` on CUDA.
* **VRAM Footprint & Residency:** The model loads once at FastAPI startup (`VLM_KEEP_LOADED=true`). On the user's **NVIDIA RTX 3050 6GB Laptop GPU**, the resident footprint is **4.16 GB (67.7%)**, peaking at **4.41 GB (71.8%)** during active inference, leaving **~1.73 GB of free VRAM headroom**.
* **Dual-Tier Ingestion Flow:**
  1. **Fast-Path (YOLOv8 123-class `best.pt`):** Runs in **36–72 ms**. If confidence $\ge 50\%$ and class is not suppressed, YOLO wins and queries PostgreSQL for verified macros.
  2. **Fallback Path (Qwen3-VL-2B):** If YOLO confidence $< 50\%$, 0 objects detected, or class is in `YOLO_SUPPRESSED_CLASSES` (default: `lassi,kulfi`), MS1 dispatches multipart image + weight to `POST /api/v1/llm/vision-infer` on MS2 (~2.2 s).
* **Macronutrient Integrity & Atwater Guardrails (`ms2_llm/validation.py`):**
  * Qwen returns `{food_name, confidence, calories_per_100g, protein_g, carbs_g, fat_g}`.
  * Checked against the Atwater equation: $|4P + 4C + 9F - \text{kcal}| / \text{kcal} \le 0.25$.
  * Macro hierarchy: Database first (exact $\rightarrow$ alias $\rightarrow$ partial). On a DB miss, Qwen's macros are persisted to `foods` table under `brand="LLM Inferred"` for instant subsequent hits.
* **Additional Endpoints:**
  * `POST /api/v1/llm/lookup`: Text-to-nutrition resolver with DB-first caching.
  * `POST /api/v1/llm/generate`: General text completion endpoint added for MS3 and MS4 agent use.

---

## 4. Deep-Dive: What Was Built in Phase 5 (MS3 User & Regional Integration)

The regional analytics codebase (`NutriX-Regional-MS3`) has been completely refactored, decoupled from legacy nested directories, and cleanly integrated into `ms3_user/`.

### 1. Dual-Routing & Frontend Compatibility (`ms3_user/routing.py`)
To ensure the existing mobile app and dev dashboard do not break while maintaining architectural purity:
* All 54 endpoints are registered using `DualRouter`.
* Every endpoint is accessible via both:
  * **Canonical architecture path:** `/api/v1/...` (e.g., `/api/v1/meal-logs/today/{user_id}`)
  * **Legacy path:** `/api/...` (e.g., `/api/meal-logs/today/{user_id}`)
* Controlled by environment variable `ENABLE_LEGACY_ROUTES=true`.

### 2. Standardized JWT Authentication & Ownership (`ms3_user/deps.py`)
* Standardized token claim: `sub` is now the **numeric `user_id`** (with an optional `email` claim).
* Cryptographically verified using `JWT_SECRET_KEY` and `HS256`.
* Enforces strict object ownership: user $A$ cannot read or mutate data belonging to user $B$ across URL path parameters, query parameters, JSON request bodies, form data, or delete operations.

### 3. 3-Tier AI Text Generation Client (`ms3_user/services/gemini_client.py` & `ai_text.py`)
All scattered inline AI calls across MS3 were consolidated into a centralized client with a cascading fallback:
1. **Tier 1 (Cloud Gemini):** Calls Google Gemini using `x-goog-api-key` header with a 10s timeout. Configured with model fallbacks (`GEMINI_MODEL=gemini-3.5-flash-lite`, fallback to `gemini-flash-lite-latest`, `gemini-3.1-flash-lite`).
2. **Tier 2 (Local MS2 Qwen):** If Gemini fails (503/404/quota/timeout), automatically routes to local MS2 `POST /api/v1/llm/generate`.
3. **Tier 3 (Canned Offline Text):** If all models are offline, returns deterministic fallback text.

### 4. Real-Time Macro Telemetry & Event Streaming
* **Canonical Synchronization (`shared/macro_sync.py`):** Replaced divergent macro payloads with a single canonical sync function called by MS1, MS3, and the PostgreSQL trigger.
* **DELETE-Aware Database Trigger (`shared/alembic/versions/002_ms3_regional.py`):** Automatically recalculates today's daily totals on `INSERT`, `UPDATE`, and `DELETE` on `meal_logs`, ensuring deleting a meal updates Redis immediately.
* **Server-Sent Events (SSE) Stream (`ms3_user/services/live_stream.py`):** Exposes `GET /api/v1/user/stream` for real-time macro telemetry updates directly to mobile clients with a 120s gateway read timeout.

### 5. Datasets & Database Seeding
* Added `shared/seeders/seed_fast_food.py`: Successfully seeds **3,355 fast food items across 8 major chains** into PostgreSQL (`recipes` table with `brand` and `dietary_tag`).
* Verified database totals: **1,886 foods** and **4,586 recipes** (3,451 Vegetarian, 606 Non-Vegetarian, 372 Vegan, 157 Jain).

---

## 5. Verified Empirical Results (From `docs/results.md`)

Live benchmarks run on the physical scale and test matrix demonstrate dramatic improvements:

### Database Audit: Pre-LLM vs. Post-LLM (Production PostgreSQL Logs)
* **Scale Weight Stability:** Pre-LLM suffered from extreme unconstrained negative spikes (`-4,606.5 g`, `-1,420.4 g`, `13,001 g`). Post-LLM has **0% negative records**, clamped to verified additions (`150.0 g`, `180.0 g`) via the $\Delta \ge 0.5\text{g}$ delta threshold.
* **"Unknown" Food Rate:** Dropped from **~65%** under the old system to **< 12%** (limited strictly to deliberate network timeout tests).
* **Macro Calculation:** Replaced static 40.1 kcal dummy fallbacks with dynamic proportional calculations: $\text{Nutrient} = (\text{Weight} / 100) \times \text{Nutrient}_{100\text{g}}$.
* **Source Attribution:** Every meal record is attributed to `esp32_yolo`, `esp32_qwen_vlm`, or `llm-timeout`.

### 7-Image Benchmark Matrix with Custom 123-Class `best.pt`
* **Apple (`appleTest.png`):** YOLO 42.9% (<50%) $\rightarrow$ Qwen 95.0% $\rightarrow$ **Apple [QWEN] 93.6 kcal** (via DB)
* **Banana (`banana-trial.jpg`):** YOLO 78.3% ($\ge$50%) $\rightarrow$ Fast-Path $\rightarrow$ **Banana [YOLO] 106.8 kcal** (61 ms)
* **Tomato (`tomato-trial.jpg`):** YOLO 83.1% ($\ge$50%) $\rightarrow$ Fast-Path $\rightarrow$ **Tomato [YOLO] 17.1 kcal** (60 ms)
* **Watermelon (`watermelon-trial.jpg`):** YOLO greenchutney 42.2% (<50%) $\rightarrow$ Qwen 97.0% $\rightarrow$ **Watermelon [QWEN] 105.0 kcal**
* **Sweet Potato (`sweet-potat-test.jpg`):** YOLO 0.0% Miss $\rightarrow$ Qwen 97.0% $\rightarrow$ **Sweet Potato [QWEN] 180.6 kcal**
* **Idli (`IDLI.jpg`):** YOLO 52.8% ($\ge$50%) $\rightarrow$ Fast-Path $\rightarrow$ **Idli [YOLO] 210.0 kcal** (45 ms)
* **ESP32 Plate (`esp32.jpg`):** YOLO bell pepper 38.5% (<50%) $\rightarrow$ Qwen 95.0% $\rightarrow$ **Bell Pepper [QWEN] 30.0 kcal**
* **Pipeline Success Rate:** **100.0% (7/7 correct)** with the hybrid architecture vs. 42.8% with YOLO alone.

---

## 6. Test Suite & Verification Status

Run these commands in WSL2 to confirm system health:

```bash
cd /home/harsh/Nutrix
source .venv/bin/activate

# 1. Unit Tests for MS3 (159 passed, 2 skipped)
PYTHONPATH=. pytest ms3_user/tests/ -v

# 2. Unit Tests for API Gateway (46 passed)
PYTHONPATH=. pytest gateway/tests/ -v

# 3. Unit Tests for MS1 & MS2 (27 passed)
PYTHONPATH=. pytest ms1_cv/tests/ ms2_llm/tests/ -v

# 4. Check Dataset Seeding Integrity
PYTHONPATH=. python scripts/verify_seed.py
```

---

## 7. Master System Runbook (Starting All Services)

To run the complete NutriX ecosystem, open separate terminal tabs in WSL2:

### Step 1: Start Infrastructure Containers
```bash
cd /home/harsh/Nutrix
docker compose up -d postgres redis
```

### Step 2: Start Microservices (5 Separate Tabs)
* **Tab 1: MS2 Local VLM (Port 8003) — Start First (no `--reload`)**
  ```bash
  cd /home/harsh/Nutrix && source .venv/bin/activate
  PYTHONPATH=. uvicorn ms2_llm.main:app --host 0.0.0.0 --port 8003
  ```
* **Tab 2: MS1 Vision & Ingestion (Port 8001)**
  ```bash
  cd /home/harsh/Nutrix && source .venv/bin/activate
  PYTHONPATH=. uvicorn ms1_cv.main:app --host 0.0.0.0 --port 8001 --reload
  ```
* **Tab 3: MS3 User & Regional Analytics (Port 8002)**
  ```bash
  cd /home/harsh/Nutrix && source .venv/bin/activate
  PYTHONPATH=. uvicorn ms3_user.main:app --host 0.0.0.0 --port 8002 --reload
  ```
* **Tab 4: API Gateway (Port 8000)**
  ```bash
  cd /home/harsh/Nutrix && source .venv/bin/activate
  PYTHONPATH=. uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload
  ```
* **Tab 5: MS4 Multi-Agent Engine (Port 8004 — Health Stub)**
  ```bash
  cd /home/harsh/Nutrix && source .venv/bin/activate
  PYTHONPATH=. uvicorn ms4_agents.main:app --host 0.0.0.0 --port 8004 --reload
  ```

### Step 3: Global Health Verification
```bash
for p in 8000 8001 8002 8003 8004; do
  printf "%-6s" "$p"
  res=$(curl -sf -m 2 localhost:$p/health)
  if [ -n "$res" ]; then
    echo "$res" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('service', 'unknown'), d.get('status', 'unknown'))"
  else
    echo "DOWN"
  fi
done
```

---

## 8. Immediate Next Steps & Open Tasks for Phase 6

When starting the next session, consult **`docs/tasks/tasks5.md`** for minor leftovers and **`docs/MASTER_PLAN.md`** for Phase 6.

### Primary Focus: Phase 6 (MS4 Multi-Agent Clinical Guardian — Port 8004)
1. **Agent Architecture (`ms4_agents/`):** Refer to `docs/AGENTIC-architecture_forPaper.md` for the formal tuple specifications ($\mathcal{A} = \langle \mathcal{S}, \mathcal{O}, \mathcal{A}_c, \mathcal{T}, \mathcal{R} \rangle$).
2. **Tier 2A: Autonomous Outlier Guardian:** Consume Redis stream `user:{id}:macro_stream`, detect macro violations, trigger alert events.
3. **Tier 2B: Multi-Agent Clinical MDT:** Nephrologist, Endocrinologist, Dietitian debate agents for clinical rationale synthesis.
4. **Tier 3: Autonomic Meta-Auditor:** Calculate Faithfulness Score ($S_{\text{faith}}$) against ICMR/USDA ground truth, self-heal system prompts in `system_prompt_registry` when $S_{\text{faith}} < 0.70$.
5. **Deterministic Optimization:** Wrap LLM recommendations in Google OR-Tools Linear Programming solvers for meal plan calorie constraints.

### Minor Housekeeping Leftovers:
* Clean up untracked temporary files (`file:test_api`, `file:test_new_api`).
* Delete legacy unused folder `ms3_user/NutriX-main/` after final confirmation.
* Resume Phase 3 HitL per-user LoRA adapters (`docs/tasks/tasks3.md` 3.8–3.10) if requested.

---

### Reference File Map
* **API Specifications:** [`docs/API_CONTRACT.md`](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/API_CONTRACT.md)
* **Mobile App Handoff:** [`docs/APP_HANDOFF.md`](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/APP_HANDOFF.md)
* **Empirical Results:** [`docs/results.md`](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/results.md)
* **System Architecture:** [`docs/MASTER_ARCHITECTURE.md`](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/MASTER_ARCHITECTURE.md)
* **Master Roadmap:** [`docs/MASTER_PLAN.md`](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/MASTER_PLAN.md)
* **Phase 5 Checklist:** [`docs/tasks/tasks5.md`](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/tasks/tasks5.md)
* **Hardware Scale Runbook:** [`docs/testing/PIPELINE_1_HARDWARE.md`](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/testing/PIPELINE_1_HARDWARE.md)
