# Phase 0 — Project Scaffolding & Repo Setup

> **Master Plan Reference:** Phase 0
> **Goal:** A clean monorepo structure that any teammate can clone and `docker-compose up` to run locally.
> **Status:** ✅ Completed

---

## Context

Before any code gets written for any microservice, we need a reliable, consistent project skeleton. Every teammate pulling the repo should be able to:

1. Set their machine's local IP in one `.env` file.
2. Run `docker-compose up` for their assigned service.
3. Have that service immediately talk to the others on the LAN.

This phase has **zero business logic**. It is pure infrastructure skeleton.

---

## Steps

### 0.1 — GitHub Organization Repo
- [x] Create `NutriX-Platform` repository inside the GitHub Organization.
- [x] Set default branch to `main`.
- [x] Add all team members with correct role access (Write / Maintain).
- [x] Create initial branch protection rule: require at least 1 PR review before merging to `main`.

**Notes / Issues:**
- Remote URL configured to point to GitHub Organization: `https://github.com/NutriX-Intelligence/NutriX-Platform.git`.
- Use `git remote set-url origin https://github.com/NutriX-Intelligence/NutriX-Platform.git` followed by `git push -u origin main` to sync local repo to the org.

---

### 0.2 — Define Final Monorepo Folder Structure
- [x] Create the following top-level folder layout inside the repo:

```text
NutriX-Platform/
├── gateway/                  # MS0 — API Gateway (Port 8000)
│   ├── main.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tests/test_health.py
├── ms1_cv/                   # MS1 — CV & Ingestion (Port 8001)
│   ├── main.py
│   ├── cv_engine.py          
│   ├── hitl_engine.py
│   ├── retrain_yolo.py
│   ├── nutrix_yolo_custom.pt
│   ├── yolov8_retrained.pt
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tests/test_health.py
├── ms2_llm/                  # MS2 — LLM Nutrition & Vision (Port 8003)
│   ├── main.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tests/test_health.py
├── ms3_user/                 # MS3 — User & Analytics (Port 8002)
│   ├── main.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tests/test_health.py
├── ms4_agents/               # MS4 — Multi-Agent System (Port 8004)
│   ├── main.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tests/test_health.py
├── shared/                   # Shared utilities (DB models, schemas)
│   ├── models.py             # SQLAlchemy ORM models (used by all services)
│   ├── schemas.py            # Pydantic schemas
│   └── db.py                 # DB session factory
├── dataset/                  # YOLO dataset (existing — keep as-is)
├── scripts/                  # Utility scripts (existing — keep as-is)
├── docs/                     # All architecture + plan docs
├── .env                      # Local secrets (gitignored)
├── .env.example              # Template (committed to repo)
├── docker-compose.yml        # Main orchestration file
├── docker-compose.override.yml # Per-machine IP overrides (gitignored)
└── .github/
    └── workflows/
        ├── ci-ms1.yml
        ├── ci-ms2.yml
        ├── ci-ms3.yml
        ├── ci-ms4.yml
        └── ci-gateway.yml
```

**Notes / Issues:**
- Folders `gateway/`, `ms1_cv/`, `ms2_llm/`, `ms3_user/`, `ms4_agents/`, `shared/`, and `.github/workflows/` generated with barebones entry points.

---

### 0.3 — Root `docker-compose.yml`
- [x] Define all 7 services: `gateway`, `ms1-cv`, `ms2-llm`, `ms3-user`, `ms4-agents`, `postgres`, `redis`.
- [x] All services join a shared Docker network named `nutrix-net`.
- [x] Port mappings:

| Service | Internal Port | External Port |
|---|---|---|
| gateway | 8000 | 8000 |
| ms1-cv | 8001 | 8001 |
| ms2-llm | 8003 | 8003 |
| ms3-user | 8002 | 8002 |
| ms4-agents | 8004 | 8004 |
| postgres | 5432 | 5432 |
| redis | 6379 | 6379 |

- [x] All services inject environment variables from `.env` via `env_file: .env`.
- [x] `postgres` service uses `postgres:16-alpine` image with a named volume `nutrix-pgdata`.
- [x] `redis` service uses `redis:7-alpine` image.
- [x] Each microservice has `depends_on: postgres, redis` except gateway and MS2.
- [x] Add `healthcheck` for postgres and redis.

**Notes / Issues:**
- Root `docker-compose.yml` uses `${VARIABLE_NAME}` syntax for PostgreSQL authentication credentials and healthcheck command.

---

### 0.4 — Per-Service Dockerfile Stubs
- [x] `gateway/Dockerfile`: `FROM python:3.11-slim` → install requirements → `CMD uvicorn gateway.main:app --host 0.0.0.0 --port 8000`
- [x] `ms1_cv/Dockerfile`: `FROM ultralytics/ultralytics:latest` (includes CUDA + PyTorch + YOLOv8) → `CMD uvicorn ms1_cv.main:app --host 0.0.0.0 --port 8001`
- [x] `ms2_llm/Dockerfile`: `FROM python:3.11-slim` + Ollama client → `CMD uvicorn ms2_llm.main:app --host 0.0.0.0 --port 8003`
- [x] `ms3_user/Dockerfile`: `FROM python:3.11-slim` → `CMD uvicorn ms3_user.main:app --host 0.0.0.0 --port 8002`
- [x] `ms4_agents/Dockerfile`: `FROM python:3.11-slim` → `CMD uvicorn ms4_agents.main:app --host 0.0.0.0 --port 8004`

**Notes / Issues:**
- All Dockerfiles copy both service-specific code and `shared/` module into the build context.

---

### 0.5 — `.env.example` File
- [x] Create `.env.example` with all required keys (no real values):

```env
# ── Database ──────────────────────────────────
POSTGRES_USER=nutrix
POSTGRES_PASSWORD=changeme
POSTGRES_DB=nutrix_db
DATABASE_URL=postgresql://nutrix:changeme@postgres:5432/nutrix_db

# ── Redis ─────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ── Auth ──────────────────────────────────────
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24
DEVICE_TOKEN=NutriX_ESP32_SECURE_TOKEN

# ── External APIs ─────────────────────────────
GEMINI_API_KEY=your-gemini-api-key
GOOGLE_CLIENT_ID=your-google-oauth-client-id

# ── Internal Service URLs (for multi-machine) ─
MS1_CV_URL=http://ms1-cv:8001
MS2_LLM_URL=http://ms2-llm:8003
MS3_USER_URL=http://ms3-user:8002
MS4_AGENTS_URL=http://ms4-agents:8004

# ── Ollama (MS2) ──────────────────────────────
OLLAMA_BASE_URL=http://ms2-llm:11434
LLM_MODEL=qwen2.5:7b-instruct
```

- [x] Add `.env` to `.gitignore`.

**Notes / Issues:**
- Generated `.env.example` and local `.env` with initial development values. `.gitignore` contains `.env`.

---

### 0.6 — `docker-compose.override.yml` for Multi-Machine LAN
- [x] Create `docker-compose.override.yml.example` showing how to override internal service URLs for multi-machine:

```yaml
# Copy this to docker-compose.override.yml and fill in real LAN IPs
version: '3.8'

services:
  ms1-cv:
    environment:
      MS2_LLM_URL: http://192.168.1.102:8003   # IP of the machine running MS2
  ms4-agents:
    environment:
      MS2_LLM_URL: http://192.168.1.102:8003
      MS1_CV_URL:  http://192.168.1.101:8001
```

- [x] Add `docker-compose.override.yml` to `.gitignore`.

**Notes / Issues:**
- `docker-compose.override.yml.example` added; `.gitignore` updated to ignore `docker-compose.override.yml`.

---

### 0.7 — Per-Service `requirements.txt`
- [x] `gateway/requirements.txt`: `fastapi`, `uvicorn`, `httpx`, `python-jose`, `python-multipart`, `pytest`
- [x] `ms1_cv/requirements.txt`: `fastapi`, `uvicorn`, `ultralytics`, `opencv-python-headless`, `pyzbar`, `pillow`, `httpx`, `sqlalchemy`, `psycopg2-binary`, `redis`, `pytest`
- [x] `ms2_llm/requirements.txt`: `fastapi`, `uvicorn`, `ollama`, `httpx`, `sqlalchemy`, `psycopg2-binary`, `pytest`
- [x] `ms3_user/requirements.txt`: `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`, `redis`, `alembic`, `httpx`, `pytest`
- [x] `ms4_agents/requirements.txt`: `fastapi`, `uvicorn`, `redis`, `httpx`, `sqlalchemy`, `psycopg2-binary`, `ortools`, `pytest`

**Notes / Issues:**
- Used `opencv-python-headless` in `ms1_cv` to ensure container compatibility without requiring X11/GUI libraries.

---

### 0.8 — GitHub Actions CI Stubs
- [x] Each workflow triggers only on changes to its service folder (path filter):

```yaml
# .github/workflows/ci-ms1.yml
on:
  push:
    paths:
      - 'ms1_cv/**'
      - 'shared/**'
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install deps
        run: pip install -r ms1_cv/requirements.txt
      - name: Run tests
        run: pytest ms1_cv/tests/ -v
```

- [x] Create stub CI files for `gateway`, `ms1_cv`, `ms2_llm`, `ms3_user`, `ms4_agents`.
- [x] Tests folder stub (`tests/test_health.py`) per service.

**Notes / Issues:**
- All 5 workflow files created in `.github/workflows/` (`ci-gateway.yml`, `ci-ms1.yml`, `ci-ms2.yml`, `ci-ms3.yml`, `ci-ms4.yml`).
- Unit test files created in `gateway/tests/`, `ms1_cv/tests/`, `ms2_llm/tests/`, `ms3_user/tests/`, `ms4_agents/tests/`.

---

## Completion Checklist

| Step | Status | Notes |
|---|---|---|
| 0.1 GitHub Repo | ✅ Completed | Configured remote URL & branch tracking guidance |
| 0.2 Folder Structure | ✅ Completed | All service directories, main.py, and shared module created |
| 0.3 docker-compose.yml | ✅ Completed | 7 services, nutrix-net network, healthchecks, env vars |
| 0.4 Dockerfiles | ✅ Completed | Lightweight python & ultralytics Dockerfiles per service |
| 0.5 .env.example | ✅ Completed | Template created + .env populated |
| 0.6 Override file | ✅ Completed | docker-compose.override.yml.example template created |
| 0.7 requirements.txt | ✅ Completed | Isolated dependencies per microservice |
| 0.8 GitHub Actions | ✅ Completed | Path-filtered workflows for all 5 services created |

**Phase 0 is complete when:** `docker-compose up` starts all 7 containers successfully (even if all return a placeholder `{"status": "ok"}` endpoint) and all containers can ping each other by service name.
