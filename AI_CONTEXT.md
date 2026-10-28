# NutriX Project: Master AI Handover Context

> **📋 MASTER PROMPT FOR NEW AI CHAT**
> Copy and paste the following prompt along with this file to start your new chat:
> 
> *"You are an expert AI assistant working on the NutriX project. NutriX is a smart nutrition tracking platform consisting of an ESP32 edge scale and a 4-tier microservice backend running on WSL2 (Ubuntu). Your primary source of truth is the attached `AI_CONTEXT.md` file. Read it thoroughly to understand the architecture, environment rules, and our current progress on Phase 3 (Computer Vision Ingestion). Never run commands automatically if they modify the system; instead, provide the commands for me to run. Our immediate next step is to continue with the pending tasks in `docs/tasks/tasks3.md`, specifically building the Per-User YOLO Adapters and Human-in-the-Loop (HiTL) pipeline. Let's get started!"*

---

Welcome to the NutriX project! This document serves as the **Master AI Context File** to provide full architectural details, historical context, and the project's current state to any new AI assisting with development.

> **⚠️ CRITICAL ENVIRONMENT DIRECTIVE:** 
> The entire active codebase and execution runtime is **WSL2 (Ubuntu)** located at `\\wsl.localhost\Ubuntu\home\harsh\Nutrix`.
> - **NEVER** edit or run code in `C:\MAIN\Project\CalCount`. Windows is just the host machine.
> - **Python Virtual Environment:** Always run commands inside `/home/harsh/Nutrix` using `source .venv/bin/activate` and prefixing with `PYTHONPATH=.`.
> - **Database Start:** Run `docker-compose up -d postgres redis` to spin up the infrastructure.

---

## 1. Master Architecture Overview
*(Extracted from `docs/MASTER_ARCHITECTURE.md`)*

NutriX is an end-to-end cognitive dietary tracking and clinical informatics ecosystem comprising four integrated microservices and four core tiers:

1. **Edge Telemetry Tier**: An ESP32-S3 physical smart scale equipped with an HX711 24-bit ADC weight sensor and an OV2640 camera module. It detects weight stabilization and captures high-resolution food frames automatically.
2. **Cloud Microservices Engine (4 Containers)**:
   - **MS1: CV & Ingestion Service (Port 8001, GPU)**: Handles scale uploads, YOLOv8 object detection (123 classes), and OpenCV barcode decoding.
   - **MS2: LLM Nutrition & Vision Service (Port 8003, GPU)**: Hosts local Qwen2.5/LLaMA models for text-to-nutrition generation AND pre-HitL image vision inference on unidentified items.
   - **MS3: User & Analytics Service (Port 8002, CPU)**: Manages User Auth, Profiles (PostgreSQL writes), Recipe Engine, OR-Tools meal planning, and fast daily dashboard reads (Redis).
   - **MS4: Multi-Agent System (MAS) Service (Port 8004, CPU/LLM Orchestration)**: Runs all 4 agent tiers (Tier 1 Orchestrator, Tier 2A Outlier Guardian, Tier 2B Clinical MDT, Tier 3 Meta-Auditor).
3. **Multi-Agent System (MAS) Framework**: A 4-tier autonomous agent layer operating over async Redis Streams and PostgreSQL trace logs.
4. **Client Interface Tier**: A cross-platform Flutter application (Android ARM64 + Web).

### Key Architectural Concepts:
- **API Gateway (Port 8000)**: Serves as the single authenticated front door. Routes scale payload (multipart form data) to MS1 and application traffic to MS3.
- **Dynamic Head Swapping (MS1)**: YOLOv8 uses a Shared Frozen Backbone with Per-User Adapter Heads (~400KB) to recognize user-specific kitchen items without VRAM exhaustion.
- **Pre-HitL LLM Vision Fallback**: If YOLO confidence is <80%, MS1 passes the image to MS2 for vision inference, returning an AI candidate suggestion for 1-tap user confirmation on the Flutter app, triggering lightweight adapter retraining.

---

## 2. Master Implementation Plan & Progress
*(Extracted from `docs/MASTER_PLAN.md`, `docs/plans/`, and `docs/tasks/`)*

The project is divided into 10 phases. We have extensively documented our progress in `docs/tasks/tasks1.md` and `tasks2.md`, all of which are **100% completed**.

- **Phase 0 (Repo Setup)**: Complete. Docker-compose, env templates, and repo scaffolding.
- **Phase 1 (Data & Database)**: Complete. PostgreSQL schemas, Alembic migrations, dataset seeders (ICMR/USDA), and Redis Pub/Sub syncing.
- **Phase 2 (API Gateway)**: Complete. FastAPI router, JWT Auth, Device-Token validation, and async proxying.
- **Phase 3 (MS1: CV & Ingestion)**: Nearly Complete. Live OpenCV processing, YOLOv8 inference, DB macro fetching.
- **Phases 4-10**: Pending/In-Progress (LLM service integration, Multi-Agent System, Flutter App, ESP32 Firmware finalization, End-to-End integration).

---

## 3. Key Accomplishments & Recent Fixes
During recent sessions, we significantly upgraded the **Database Ingestion** and **Macro Accuracy** in MS1:

1. **Exact Macros & Alias Integration**:
   - Replaced old hardcoded calorie heuristics with highly precise macros.
   - **`wholeFoods.xlsx`**: Master dataset of canonical foods (Kcal, Protein, Carbs, Fat per 100g).
   - **`foodAliases.xlsx`**: Maps 201+ regional synonyms (e.g., "seb" -> "Apple") to canonical names.
2. **Master Seeder Refactor**:
   - `scripts/seed_yolo_classes.py` now uses Pandas to perform a strict **Upsert** into PostgreSQL (`foods`, `food_nutrients`, `food_aliases`). Even if a YOLO Generic class existed, its macros are now forcefully updated to the precise Excel values.
3. **MS1 Logic Rewrite (`ms1_cv/main.py`)**:
   - MS1 now executes a 3-step hierarchical database lookup for macros:
     1. Exact Canonical Name match.
     2. Exact Alias Name match.
     3. Partial match (restricted to `brand IN ('Whole Food', 'YOLO Generic')`).
   - *Fix applied:* Unidentified items (0% YOLO confidence) now correctly search the database for macros rather than relying on a lazy 100kcal fallback.
4. **Dependency Fixes**:
   - Fixed a failing GitHub CI test by appending `python-multipart>=0.0.9` to `ms1_cv/requirements.txt` and the root `requirements.txt`.

---

## 4. Key File Locations & Scripts
- **`ms1_cv/main.py`**: The ingestion API endpoints (e.g., `/api/v1/ingest/weight-frame`). Handles weight calculation and DB macro fetching.
- **`ms1_cv/cv_engine.py`**: Handles OpenCV parsing and the YOLOv8 model inference.
- **`shared/models.py`**: SQLAlchemy ORM models (`Food`, `FoodNutrient`, `FoodAlias`, `MealLog`, `User`).
- **`shared/db.py`**: Postgres connection logic and `.env` parsing.
- **`scripts/seed_yolo_classes.py`**: Master script to populate DB from Excel datasets.
- **`scripts/dev_capture.py`**: **CRITICAL CLI SCRIPT** used to mock ESP32 hardware and send test images/weights to MS1 for testing CV logic.
- **`scripts/show_db_logs.py` & `scripts/show_redis_cache.py`**: Utility scripts to instantly view the latest database and cache states in the terminal.
- **`dataset/ms3_datasets/`**: Directory containing the `wholeFoods.xlsx` and `foodAliases.xlsx` master datasets.

## 5. Extensive Documentation (`docs/`)
For deep dives, rely heavily on the `docs/` folder:
- **`MASTER_ARCHITECTURE.md` / `MASTER_PLAN.md`**: The absolute sources of truth for the system design and roadmap.
- **`AGENTIC-architecture_forPaper.md`**: Extremely detailed breakdown meant for compiling the final project thesis or research paper.
- **`SYSTEM_AUDIT_REPORT.md` / `CHALLENGES_AND_DECISIONS.md`**: Historical context on bugs, refactoring, and why certain architectural decisions were made (e.g., PostgreSQL vs SQLite, Redis Streams vs Pub/Sub).
- **`testing/PIPELINE_2_SOFTWARE.md`**: Instructions to start the MS1 & Gateway servers and test the system locally via `dev_capture.py`.
- **`testing/PIPELINE_1_HARDWARE.md`**: Instructions for flashing the ESP32 and testing physical hardware scale integration.
- **`tasks/` & `plans/`**: Execution checklists for each Phase. **Note: `docs/tasks/tasks3.md` reflects our exact progress on Phase 3.**

---

## How to Proceed
If you are the new AI picking up this chat:
1. Always read `AI_CONTEXT.md` and reference `docs/MASTER_PLAN.md` when planning the next phase.
2. **Phase 5 (MS3 integration, `docs/tasks/tasks5.md`) is now the focus**: the new MS3 lives in `ms3_user/` (entry `ms3_user.main:app`, routes in `routes.py`, served at `/api/v1/...` and the legacy paths; JWT `sub` = user id; shared schema in `shared/models.py` + Alembic `002`; Redis writes only through `shared/macro_sync.py`; Gemini stays in MS3). Phase 4 (MS2) is done: **Phase 4: MS2** (`docs/tasks/tasks4.md`): Qwen3-VL-2B (transformers, local HF cache via `VLM_MODEL_PATH`) is the fallback when YOLO can't identify a food (conf below `YOLO_CONF_THRESHOLD`, default 0.5, or class in `YOLO_SUPPRESSED_CLASSES` = lassi/kulfi). Phase 3's Per-User YOLO Adapters and HiTL pipeline (`docs/tasks/tasks3.md`) are paused; HitL is skipped for now, so Qwen's label is logged directly. Run MS2 without `--reload` (4 GB model).
3. Ensure you test any MS1 API changes locally using `scripts/dev_capture.py` while running the FastAPI servers in the background.
4. **⚠️ DO NOT RUN EVERY COMMAND AUTOMATICALLY.** Instead of executing all scripts yourself, provide the exact commands to the user, and they will run them on their end.
