# NutriX — Mid-Semester Live Demonstration & Replay Runbook

> **Document:** `docs/trial_midSem.md`  
> **Date:** August 26, 2026  
> **Status:** Verified & Working End-to-End  
> **Target Scope:** ESP32-S3 Smart Scale $\rightarrow$ FastAPI Gateway (Port 8000) $\rightarrow$ MS1 Vision Service (Port 8001) $\rightarrow$ Custom YOLO (`best.pt`) $\rightarrow$ PostgreSQL Relational Store $\rightarrow$ Redis In-Memory Cache $\rightarrow$ ESP32 OLED Display & Real-Time Web Image Viewer.

---

## 1. System Architecture & Live Data Flow

```mermaid
sequenceDiagram
    autonumber
    participant Scale as 📱 ESP32-S3 Scale (HX711 + OV2640 + OLED)
    participant GW as 🔀 API Gateway (Port 8000)
    participant MS1 as 🎯 MS1: CV & Ingestion (Port 8001)
    participant YOLO as 🧠 Custom YOLOv8 (best.pt)
    participant PG as 🗄️ PostgreSQL (meal_logs)
    participant RD as ⚡ Redis (user:1:macros)
    participant Browser as 💻 Web Browser (Live Viewer)

    Note over Scale: User places food (e.g., Bell Pepper) & presses Button (GPIO 9)
    Scale->>GW: POST /api/v1/ingest/weight-frame<br/>Headers: [Device-Token, User-ID]<br/>Payload: multipart [weight=38.3g, image=JPEG]
    Note over GW: Validates Device-Token & routes to MS1
    GW->>MS1: Proxies multipart stream
    MS1->>YOLO: Runs inference on frame buffer
    YOLO-->>MS1: Returns class: "bell pepper" (78.4% conf) + bbox
    MS1->>PG: Queries foods/nutrients table & calculates calories (38.3 kcal)
    MS1->>PG: INSERT INTO meal_logs (user_id=1, food_name="Bell Pepper", calories=38.3, weight_g=38.3)
    MS1->>RD: Recalculates today's total & SET user:1:macros:2026-08-26
    MS1->>MS1: Annotates frame with Bounding Box & saves to dataset/live_captures/latest_annotated.jpg
    MS1-->>GW: Returns JSON: {"food_label": "Bell Pepper", "calories": 38.3, "confidence": 78.4, "weight_g": 38.3}
    GW-->>Scale: HTTP 200 OK Response
    Note over Scale: OLED instantly displays:<br/>"Bell Pepper | 38.3g | 38.3 kcal | Conf: 78.4%"
    Note over Browser: User visits http://localhost:8001/captures/annotated to see live detection
```

---

## 2. Prerequisites & Environment Setup

### Network & Hardware Map
- **Host Laptop (Backend Services):** Windows 11 with WSL2 (Ubuntu)
  - **Local Wi-Fi IP:** `192.168.29.232` (or current LAN IPv4)
  - **WSL2 Internal IP:** Run `ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}'` (e.g. `172.25.48.117`)
- **ESP32 Client Device:** Freenove ESP32-S3 with HX711 24-bit ADC + OV2640 Camera + SSD1306 OLED + Push Button (GPIO 9).

### Environment Configuration (`.env`)
The root `.env` file must contain:
```dotenv
POSTGRES_USER=nutrix
POSTGRES_PASSWORD=nutties
POSTGRES_DB=nutrix_db
DATABASE_URL=postgresql://nutrix:nutties@localhost:5432/nutrix_db
REDIS_URL=redis://localhost:6379/0
DEVICE_TOKEN=NutriX_ESP32_SECURE_TOKEN
```

---

## 3. Step-by-Step Live Replication Guide

Follow these exact steps in order:

### Step 1: Start Docker Database & Cache Containers
In your WSL2 terminal:
```bash
cd /home/harsh/Nutrix
docker compose up -d postgres redis
```
*Verify containers are running:*
```bash
docker ps
```
*(You should see `nutrix-postgres` on port 5432 and `nutrix-redis` on port 6379).*

---

### Step 2: Configure Windows Port Forwarding (One-Time / per Reboot)
Because WSL2 runs inside an isolated virtual network, incoming Wi-Fi traffic to `192.168.29.232:8000` must be forwarded to WSL2.

1. Open **PowerShell as Administrator** on Windows.
2. Find WSL2 internal IP:
   ```powershell
   wsl -d Ubuntu -- bash -c "ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}'"
   ```
   *(e.g., `172.25.48.117`)*
3. Add the portproxy & firewall rule:
   ```powershell
   netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=172.25.48.117
   netsh advfirewall firewall add rule name="NutriX Gateway 8000" dir=in action=allow protocol=TCP localport=8000
   ```

---

### Step 3: Terminal 1 — Start MS1 (Vision Service on Port 8001)
In WSL2:
```bash
cd /home/harsh/Nutrix
source .venv/bin/activate
PYTHONPATH=. uvicorn ms1_cv.main:app --host 0.0.0.0 --port 8001 --reload
```
*Expected log output:*
```text
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

### Step 4: Terminal 2 — Start API Gateway (Front Door on Port 8000)
In a second WSL2 terminal tab:
```bash
cd /home/harsh/Nutrix
source .venv/bin/activate
PYTHONPATH=. uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload
```
*Expected log output:*
```text
Initializing API Gateway...
MS1 CV URL: http://localhost:8001
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

---

### Step 5: Flash & Start the ESP32-S3 Smart Scale
1. Open the `.ino` firmware sketch in Arduino IDE.
2. Ensure Wi-Fi credentials and IP are configured:
   ```cpp
   const char *ssid = "YOUR_WIFI_SSID";
   const char *password = "YOUR_WIFI_PASSWORD";
   const char *SERVER_HOST = "192.168.29.232"; // Host laptop IP
   const uint16_t SERVER_PORT = 8000;
   const char *DEVICE_TOKEN = "NutriX_ESP32_SECURE_TOKEN";
   ```
3. Upload sketch to **ESP32-S3** and open **Serial Monitor** at `115200` baud.
4. Scale OLED will display `SYSTEM READY | Press button GPIO 9`.

---

### Step 6: Trigger the Demo & Observe Live Results

1. Place food (e.g. Bell Pepper, Apple, Roti) on the scale.
2. **Press the button on GPIO 9**.
3. **Observe the complete system outputs:**
   - **ESP32 OLED:** Updates to show:
     ```text
     Bell Pepper
     Weight: 38.3 g
     Calories: 38.30 kcal
     Conf: 78.4%
     ```
   - **Web Browser:** Open [http://localhost:8001/captures/annotated](http://localhost:8001/captures/annotated) to view the live JPEG with the green YOLO bounding box and calorie banner!
   - **PostgreSQL Database:** Run `PYTHONPATH=. python scripts/show_db_logs.py` or inspect via DBeaver `meal_logs` table.
   - **Redis Live Cache:** Run `PYTHONPATH=. python scripts/show_redis_cache.py` or `docker exec -it nutrix-redis redis-cli GET "user:1:macros:YYYY-MM-DD"`.

---

## 4. Errors Encountered & Exact Root Causes and Fixes

| # | Error Message / Symptom | Root Cause | Exact Solution Applied |
|---|---|---|---|
| **1** | `ERROR: Could not connect to API Gateway` on ESP32 Serial Monitor | WSL2 network isolation: Windows host received port 8000 traffic from LAN but did not forward it to WSL2 virtual adapter. | Ran `netsh interface portproxy add v4tov4 listenport=8000 ... connectaddress=<WSL_IP>` in Admin PowerShell and added Windows Firewall rule. |
| **2** | `PermissionError: [Errno 13] Permission denied: '/home/dataset'` | In `cv_engine.py`, `os.path.join(..., "../../../dataset/pending")` resolved 3 levels up to `/home/dataset` instead of `/home/harsh/Nutrix/dataset`. | Fixed project root path resolution to `os.path.join(os.path.dirname(__file__), "../")`. |
| **3** | `sqlite3.OperationalError: no such table: foods` | SQLite fallback database did not have tables migrated when Postgres was disconnected. | Wrapped DB query in safe `try/except` block in `ms1_cv/main.py` and provided an immediate nutritional dictionary fallback. |
| **4** | `FATAL: password authentication failed for user "nutrix"` | `shared/db.py` was defaulting password to `changeme` and attempting to resolve container hostname `postgres:5432` instead of `localhost:5432` outside Docker. | Updated `shared/db.py` to auto-parse root `.env` (`nutties`) and dynamically map `@postgres:` $\rightarrow$ `@localhost:`. |
| **5** | `Redis connection failed (Error -3 ... Temporary failure in name resolution)` | `REDIS_URL` in `.env` was `redis://redis:6379/0` which is only resolvable inside Docker container network. | Updated `shared/redis_client.py` to auto-replace `redis://redis:` with `redis://localhost:` when running on the host. |

---

## 5. Live Inspection & Verification Toolset

### Tool 1: Real-Time Browser Image Viewer
- **Annotated Stream:** [http://localhost:8001/captures/annotated](http://localhost:8001/captures/annotated)
- **Raw Camera JPEG:** [http://localhost:8001/captures/latest](http://localhost:8001/captures/latest)

### Tool 2: PostgreSQL Database Log Viewer
```bash
PYTHONPATH=. python scripts/show_db_logs.py
```
*Queries the `meal_logs` table in PostgreSQL and displays formatted rows.*

### Tool 3: Redis In-Memory Cache Viewer
```bash
PYTHONPATH=. python scripts/show_redis_cache.py
```
*Queries key `user:1:macros:YYYY-MM-DD` and displays running daily calories and macro breakdown.*

### Tool 4: Direct Database Queries via Docker
```bash
# PostgreSQL meal logs
docker exec -it nutrix-postgres psql -U nutrix -d nutrix_db -c "SELECT id, food_name, weight_g, calories, created_at FROM meal_logs ORDER BY id DESC LIMIT 10;"

# Redis raw keys & value
docker exec -it nutrix-redis redis-cli KEYS "*"
docker exec -it nutrix-redis redis-cli GET "user:1:macros:2026-08-26"
```

---

## 6. Step-by-Step Clean Shutdown Guide

When finished demonstrating:

### Step 1: Stop Running Python Microservices
- In **Terminal 1 (MS1)**: Press `Ctrl + C`
- In **Terminal 2 (Gateway)**: Press `Ctrl + C`

### Step 2: Stop Docker Containers
In WSL2 terminal:
```bash
cd /home/harsh/Nutrix
docker compose down
```
*(To preserve database data, do not use `-v`; volumes remain saved).*

### Step 3: Clean up Windows Port Forwarding (Optional)
In Windows Admin PowerShell:
```powershell
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0
```
