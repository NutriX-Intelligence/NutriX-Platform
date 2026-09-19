# NutriX Developer & Agent Execution Rules (WSL Environment Mandate)

> **CRITICAL DIRECTIVE FOR ALL DEVELOPERS AND AI AGENTS:**  
> The **sole source of truth and execution environment** for the NutriX project is **WSL2 (Ubuntu)** at `/home/harsh/Nutrix`.  
> Under **NO circumstances** should commands be executed in Windows `C:\` or code edited exclusively in `C:\MAIN\Project\CalCount`.

---

## 1. Ground Truth Workspace Paths

| Environment | Path | Role |
|---|---|---|
| **WSL2 (Primary / Source of Truth)** | `/home/harsh/Nutrix` | **Active codebase, git repository, virtual environment, and runtime.** |
| **Windows UNC Access** | `\\wsl.localhost\Ubuntu\home\harsh\Nutrix` | **Path to use for file view/edit/write tools from Windows IDE.** |
| **Windows C: Drive (Mirror / Stale)** | `C:\MAIN\Project\CalCount` | **DO NOT USE AS PRIMARY.** May be out-of-sync or missing WSL virtualenv/dependencies. |

### Strict Rule on File Access:
- When viewing, editing, or creating files, **always use the WSL UNC path**:  
  `\\wsl.localhost\Ubuntu\home\harsh\Nutrix\<relative_path>`
- Never assume a file modified on `C:\MAIN\Project\CalCount` will reflect inside WSL unless explicitly synced or checked.

---

## 2. Command Execution Mandate

All commands (Python, Uvicorn, Pytest, Alembic, Docker, Git) **MUST** be run inside the WSL Ubuntu environment.

### Format for Shell Execution:
Always invoke commands through `wsl.exe`:
```bash
wsl.exe -d Ubuntu -- bash -c "cd /home/harsh/Nutrix && source .venv/bin/activate && <COMMAND>"
```

### Prohibited Actions:
- ❌ **DO NOT** run `python script.py` directly in Windows PowerShell / Command Prompt (Windows Python lacks required Linux packages, CUDA/torch configs, database drivers, and the `.venv`).
- ❌ **DO NOT** run `uvicorn` in Windows.
- ❌ **DO NOT** run `pytest` in Windows.
- ❌ **DO NOT** use Windows paths (`C:\...`) in Linux bash strings.

### The Single Exception:
- ✅ **Windows-only Host Hardware/Network Commands**:
  - `ipconfig` (checking laptop Wi-Fi IP)
  - `netsh interface portproxy ...` (configuring port forwarding from Windows Wi-Fi to WSL2 IP)
  - `python scripts\dev_capture.py --webcam` (only when laptop webcam is needed and WSL2 lacks USB video passthrough, which POSTs over localhost to WSL MS1).

---

## 3. Python Virtual Environment (`.venv`) Activation

The project virtual environment is located at `/home/harsh/Nutrix/.venv`.

### Standard Execution Template:
Every Python execution command must:
1. Navigate to project root: `cd /home/harsh/Nutrix`
2. Activate `.venv`: `source .venv/bin/activate`
3. Set Python path: `export PYTHONPATH=.`

```bash
# Example: Running MS1 Vision Service
wsl.exe -d Ubuntu -- bash -c "cd /home/harsh/Nutrix && source .venv/bin/activate && PYTHONPATH=. uvicorn ms1_cv.main:app --host 0.0.0.0 --port 8001 --reload"

# Example: Running Gateway
wsl.exe -d Ubuntu -- bash -c "cd /home/harsh/Nutrix && source .venv/bin/activate && PYTHONPATH=. uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload"

# Example: Running Pytest
wsl.exe -d Ubuntu -- bash -c "cd /home/harsh/Nutrix && source .venv/bin/activate && PYTHONPATH=. pytest tests/ -v"
```

---

## 4. Docker & Database Containers

PostgreSQL and Redis run via Docker containers mapped to host ports.

### Starting Containers:
```bash
# In WSL2:
cd /home/harsh/Nutrix
docker compose up -d postgres redis
```
*(If Docker CLI in WSL points to Docker Desktop, ensure Docker Desktop WSL2 integration is enabled).*

### Container Service Map:
| Service | Container Name | Internal Port | Host Port | Credentials / DB |
|---|---|---|---|---|
| **PostgreSQL** | `nutrix-postgres` | 5432 | `5432` | `nutrix:nutties@localhost:5432/nutrix_db` |
| **Redis** | `nutrix-redis` | 6379 | `6379` | `redis://localhost:6379/0` |

---

## 5. Microservice Port Standards

Each microservice has an assigned port binding:

| Microservice | Internal Port | Entrypoint | Description |
|---|---|---|---|
| **API Gateway** | `8000` | `gateway.main:app` | Central entrypoint, JWT + Device auth, reverse proxy |
| **MS1: CV & Ingestion** | `8001` | `ms1_cv.main:app` | YOLOv8 inference, scale ingest, meal log, Redis sync |
| **MS3: User & Analytics** | `8002` | `ms3_user.main:app` | Profile, macro engines, streak tracking |
| **MS2: LLM Nutrition** | `8003` | `ms2_llm.main:app` | Gemini/Qwen nutritional analysis & OCR |
| **MS4: Multi-Agent** | `8004` | `ms4_agents.main:app` | Clinical guardian, dietitians, behavioral nudges |

---

## 6. Pre-Test Session Protocol (Hygiene Rule)

To prevent test runs from polluting daily aggregates with negative numbers or dirty states:
```bash
wsl.exe -d Ubuntu -- bash -c "cd /home/harsh/Nutrix && source .venv/bin/activate && PYTHONPATH=. python scripts/reset_test_session.py"
```
This resets:
1. Today's `meal_logs` rows in PostgreSQL for user 1.
2. Redis cache key `user:1:macros:YYYY-MM-DD` to `0.0 kcal`.

---

## 7. Pre-Turn Checklist for Agents

Before completing any request or proposing changes, verify:
- [ ] Are file edits applied to `\\wsl.localhost\Ubuntu\home\harsh\Nutrix`?
- [ ] Were bash commands executed inside WSL2 with `.venv` active?
- [ ] Is `PYTHONPATH=.` set for module resolution?
- [ ] Did you check `git status` inside `/home/harsh/Nutrix`?
- [ ] Are clickable links formatted with valid `file://` URIs pointing to WSL paths?
