# AGENTS.md — Mandatory Agent Execution Directives for NutriX

> **STOP & READ BEFORE ANY ACTION:**  
> The **ONLY** authoritative workspace and execution runtime for NutriX is **WSL2 (Ubuntu)** at `/home/harsh/Nutrix`.  
> Windows `C:\` or `C:\MAIN\Project\CalCount` is **NEVER** the primary codebase or execution environment.

---

## Non-Negotiable Agent Rules

### 1. File Access & Editing
- **Always read and edit files via WSL UNC path**:  
  `\\wsl.localhost\Ubuntu\home\harsh\Nutrix\...`
- Do **NOT** edit files in `C:\MAIN\Project\CalCount` thinking they are the active environment.
- Any new scripts, documentation, or modifications must reside in `\\wsl.localhost\Ubuntu\home\harsh\Nutrix`.

### 2. Command Execution Environment
- **Always execute shell commands inside WSL2**:  
  `wsl.exe -d Ubuntu -- bash -c "cd /home/harsh/Nutrix && source .venv/bin/activate && <COMMAND>"`
- Never run Python, Uvicorn, Pytest, or Alembic directly in Windows PowerShell / CMD.
- The virtual environment is `/home/harsh/Nutrix/.venv`.
- Always prefix Python executions with `PYTHONPATH=.`.

### 3. Service Ports & Architecture
- **Gateway**: Port 8000 (`gateway.main:app`)
- **MS1 CV & Ingestion**: Port 8001 (`ms1_cv.main:app`)
- **MS3 User & Analytics**: Port 8002 (`ms3_user.main:app`)
- **MS2 LLM Nutrition**: Port 8003 (`ms2_llm.main:app`)
- **MS4 Multi-Agent**: Port 8004 (`ms4_agents.main:app`)
- **PostgreSQL**: Port 5432 (`docker compose up -d postgres redis`)
- **Redis**: Port 6379

### 4. Testing Hygiene
- Before running test suites or ingestion demos, reset session data:  
  `PYTHONPATH=. python scripts/reset_test_session.py`
- Follow [`docs/testing/PIPELINE_1_HARDWARE.md`](file:///\\wsl.localhost\Ubuntu\home\harsh\Nutrix\docs\testing\PIPELINE_1_HARDWARE.md) for physical scale tests.
- Follow [`docs/testing/PIPELINE_2_SOFTWARE.md`](file:///\\wsl.localhost\Ubuntu\home\harsh\Nutrix\docs\testing\PIPELINE_2_SOFTWARE.md) for webcam/image tests.

### 5. Documentation Reference
- Full environment instructions: [`docs/DEV_ENVIRONMENT_RULES.md`](file:///\\wsl.localhost\Ubuntu\home\harsh\Nutrix\docs\DEV_ENVIRONMENT_RULES.md)
