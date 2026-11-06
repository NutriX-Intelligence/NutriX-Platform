# NutriX — Master Testing Pipeline (college session)

One file to follow top to bottom. It does not repeat the detailed steps; it sequences them and links to:
[`PIPELINE_1_HARDWARE.md`](PIPELINE_1_HARDWARE.md) (scale, phone, tunnel, firmware) = **P1**,
[`PIPELINE_2_SOFTWARE.md`](PIPELINE_2_SOFTWARE.md) (no hardware) = **P2**.

All commands run in WSL Ubuntu unless marked **[PowerShell]**. Every Python command is `PYTHONPATH=. python ...` with the venv active:
```bash
cd /home/harsh/Nutrix && source .venv/bin/activate
```

**Goal of the session:** (1) prove the system works end to end, (2) capture evidence for the paper: the before/after behaviour, latency, and
GPU numbers, (3) collect a few real scale photos/logs. Everything is saved into one folder (Phase 5).

Time budget: preflight 15 min · software tests 30 min · hardware 45 min · evidence 30 min.

---

## Phase 0 — The day before (at home, on a normal network)

| ☐ | Task | Why |
|---|---|---|
| ☐ | `docker compose up -d postgres redis` then `bash scripts/preflight_check.sh` → **0 FAIL** | catches broken env/model/DB before you travel |
| ☐ | Run the full software flow once at home (Phase 2–3) | proves nothing depends on today's luck |
| ☐ | Fix any `[WARN] MS2 prompts missing`: `python shared/seeders/seed_prompts.py` | MS2 uses these rows |
| ☐ | Install **cloudflared** and **ngrok**, add the ngrok authtoken, create the free ngrok domain (Phase 4B-A) | campus firewalls often block Cloudflare |
| ☐ | Charge laptop; bring charger, USB-C data cable, the scale, phone | |
| ☐ | Open `esp32-code/MaruWebServer_test1.ino` and read **"Firmware reality check"** (Phase 5): Wi-Fi name/password and server IP are hard-coded for your home network and **must be changed and re-flashed at college** | P1 §8 |
| ☐ | Know the laptop **hotspot** fallback (P1 §6.5); test the scale joins it (2.4 GHz) | venue Wi-Fi may block the ESP32 |
| ☐ | Make sure the test photos exist: `ls inference_outputs/*.jpg inference_outputs/*.png` (7 benchmark images + `latest_raw.jpg`) | used in Phases 3–4 |
| ☐ | Do NOT git-commit `.env` or paste the token/Gemini key anywhere | |

Known state when this was written: the benchmark was run with threshold **0.5** but `.env` currently has `YOLO_CONF_THRESHOLD=0.7`.
Pick one deliberately. For paper numbers use 0.5 (matches the report); say which you used.

---

## Phase 1 — Arrive and bring the stack up

```bash
cd /home/harsh/Nutrix && source .venv/bin/activate
docker compose up -d postgres redis
bash scripts/preflight_check.sh
```
Go / no-go:

| Preflight result | Action |
|---|---|
| 0 FAIL | continue |
| FAIL docker | start Docker Desktop, wait 30 s, rerun |
| FAIL user 1 | `python scripts/create_dev_user.py` |
| FAIL CUDA / deps | stop: fix before anything else (`pip install -r requirements.txt ms1_cv/... ms2_llm/... ms3_user/...`, P1 §3.3) |
| WARN foods small | `python shared/seeders/run_all_seeders.py` then `python scripts/verify_seed.py` |
| WARN prompts | `python shared/seeders/seed_prompts.py` |

Schema (safe to repeat): `alembic upgrade head`. Clean state: `python scripts/reset_test_session.py --user-id 1`.

Start four terminals (details: P1 §4). **MS2 first, no `--reload`:**

| Terminal | Command | Ready when |
|---|---|---|
| A MS2 | `PYTHONPATH=. uvicorn ms2_llm.main:app --host 0.0.0.0 --port 8003` | `curl -s localhost:8003/health` shows vlm `ok` (~35 s) |
| B MS1 | `PYTHONPATH=. uvicorn ms1_cv.main:app --host 0.0.0.0 --port 8001 --reload` | `Application startup complete` |
| C MS3 | `PYTHONPATH=. uvicorn ms3_user.main:app --host 0.0.0.0 --port 8002 --reload` | same |
| D Gateway | `PYTHONPATH=. uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload` | same |

Then: `bash scripts/preflight_check.sh --services` → expect 0 FAIL (MS4 warn is normal).
Send **one throwaway request** to MS2 so the first real test isn't a cold start (Phase 3, test A with the banana image).

---

## Phase 2 — Unit tests (2 min, no GPU needed)

```bash
mkdir -p docs/paper-upgrade/results/college_run && R=docs/paper-upgrade/results/college_run
PYTHONPATH=. pytest ms1_cv/tests ms2_llm/tests gateway/tests tests/test_eval_fallback_ablation.py -q -p no:warnings 2>&1 | tee $R/01_unit_tests.txt
PYTHONPATH=. pytest ms3_user/tests -q -p no:warnings 2>&1 | tee $R/02_ms3_tests.txt
```
Expected: all pass (38 + 6 verified earlier for MS1/MS2/eval helpers; gateway and MS3 counts are whatever the suites hold).
Any failure → note it, don't block the demo unless it's MS1/MS2.

---

## Phase 3 — Software pipeline tests (P2 §6, test matrix)

Use `--no-browser`. Save every run with `tee`.

```bash
R=docs/paper-upgrade/results/college_run
# A. YOLO-known food → fast path (also the warm-up call)
PYTHONPATH=. python scripts/dev_capture.py --image inference_outputs/banana-trial.jpg --weight 120 --no-browser | tee $R/03A_yolo_banana.txt
# B. YOLO unsure → VLM rescue (the paper's core behaviour)
PYTHONPATH=. python scripts/dev_capture.py --image inference_outputs/watermelon-trial.jpg --weight 350 --no-browser | tee $R/03B_vlm_watermelon.txt
PYTHONPATH=. python scripts/dev_capture.py --image inference_outputs/sweet-potat-test.jpg --weight 210 --no-browser | tee $R/03B_vlm_sweetpotato.txt
# E/F. text lookup: DB hit, then a miss that is persisted, then the DB hit on repeat
PYTHONPATH=. python scripts/test_ms2.py --lookup banana | tee $R/03E_lookup_hit.txt
PYTHONPATH=. python scripts/test_ms2.py --lookup "murgh makhani" | tee $R/03F_lookup_miss.txt
PYTHONPATH=. python scripts/test_ms2.py --lookup "murgh makhani" | tee $R/03F_lookup_repeat.txt
```
**D. MS2 down → graceful failure (the "failure is explicit" claim):** stop Terminal A (Ctrl+C), run:
```bash
PYTHONPATH=. python scripts/dev_capture.py --image inference_outputs/watermelon-trial.jpg --weight 350 --no-browser | tee $R/03D_ms2_down.txt
```
Expect HTTP 200, `Macro Source: llm-timeout`, 0 kcal. Then **restart Terminal A and wait for `ok`** before continuing.

Pass criteria:

| Test | Must see |
|---|---|
| A | `Identified By: yolo`, `Macro Source: db`, latency well under 1 s |
| B | `Identified By: qwen`, label correct by eye, `Macro Source: db` or `qwen3-vl-2b`, ~2–4 s |
| E/F | hit `source: db` quickly; first `murgh makhani` = LLM source, repeat = `db` (this reproduces the "miss → persist → hit" claim; if the first is already `db`, it was cached from an earlier run: use another unusual dish name) |
| D | `llm-timeout`, 0 kcal, no crash |

Gateway / auth / user journey (optional, P2 §6 "User journey" and "Through the API Gateway"): run those blocks as written and keep the
output with `tee $R/04_gateway_journey.txt`. Key checks: no token → 401, bad token → 401, no `User-ID` → 400, other user's data → 403.

---

## Phase 4 — Evidence for the paper

### 4.1 Refresh the 7-image benchmark (recommended)
This script loads its **own** copy of Qwen (~4.2 GB). With MS2 also loaded the 6 GB GPU runs out of memory, so **stop Terminal A (MS2) first**.
```bash
R=docs/paper-upgrade/results/college_run
nvidia-smi --query-gpu=memory.used --format=csv,noheader          # should be small before you start
PYTHONPATH=. python scripts/evaluate_post_llm.py 2>&1 | tee $R/05_benchmark_console.txt
cp inference_outputs/post_llm_benchmark_results.json $R/05_benchmark.json
```
Then restart MS2 in Terminal A if you need it again. Before you quote it:
* `esp32.jpg` has ground truth "Carrot/Apple/Tomato (Scale Plate)" in the script; correct it by eye or exclude that image.
* The script records YOLO confidence 0.0 for unidentified frames; that is expected, not a bug in the run.
* "paneer butter masala" will say `source: db` if it was saved before. That is fine; do not claim a speed-up from it.
* The script uses threshold 0.5 on purpose.

### 4.2 Detector provenance (10 s, strengthens "the detector is unchanged")
```bash
md5sum backend/services/ingestion/best.pt ms1_cv/nutrix_yolo_custom.pt runs/nutrix_custom_model-2/weights/best.pt | tee $R/06_weights_md5.txt
```
Verified earlier: all three hashes are identical (`c2c66870…`), i.e. the deployed detector is the paper's checkpoint.

### 4.3 Resource numbers (with MS1 + MS2 running and one VLM call done)
```bash
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv | tee $R/07_gpu.txt
curl -s localhost:8003/health | tee $R/07_ms2_health.json
```

### 4.4 Database proof (read-only; paste into the report)
```bash
docker exec nutrix-postgres psql -U nutrix -d nutrix_db -c "SELECT source, count(*) n, round(sum(calories)::numeric,1) kcal FROM meal_logs GROUP BY source ORDER BY n DESC;" | tee $R/08_sources.txt
docker exec nutrix-postgres psql -U nutrix -d nutrix_db -c "SELECT id, log_date, food_name, round(weight_g::numeric,1) w, round(calories::numeric,1) kcal, source FROM meal_logs ORDER BY id;" | tee $R/08_meal_logs_all.txt
docker exec nutrix-postgres psql -U nutrix -d nutrix_db -c "SELECT count(*) AS foods_total, count(*) FILTER (WHERE brand='LLM Inferred') AS llm_inferred FROM foods;" | tee $R/08_foods.txt
```
This verifies the "pre-LLM vs post-LLM rows" and the "foods count" that `docs/results.md` claims and that the earlier report marked **UNVERIFIED**.
Do not run `scripts/reset_test_session.py --all-dates` or `cleanup_test_data.py --apply` before this: they delete the history.

### 4.5 Optional, only if time: labelled comparison
Needs MS2 running. **Read the caveat first:** the public test labels contain errors, and the script currently scores the VLM's raw name without the
alias lookup, so it understates the VLM. Use it as an exploratory number, not a headline.
```bash
PYTHONPATH=. python scripts/eval_fallback_ablation.py --limit 30 | tee $R/09_ablation_30.txt
```
Skip this phase if short on time; the paper summary does not depend on it.

---

## Phase 4B — Tunnel initialization (Cloudflare and ngrok)

Only the **phone app** needs a tunnel. The scale talks to the laptop directly over the LAN (P1 §7). Both tools run on **Windows**
(**[PowerShell]**), not in WSL. Start the gateway (Terminal D, port 8000) first; a tunnel to a dead port just says `connection refused`.

### A. One-time install and sign-in (do this at home, on a normal network)

| Tool | Install **[PowerShell]** | Account needed? | One-time setup |
|---|---|---|---|
| Cloudflare | `winget install Cloudflare.cloudflared` | No (quick tunnels are anonymous) | none. Open a **new** PowerShell window, check `cloudflared --version` |
| ngrok | `winget install ngrok.ngrok` | **Yes**, free account at ngrok.com | `ngrok config add-authtoken <YOUR_AUTHTOKEN>` (token is on dashboard.ngrok.com → *Your Authtoken*; treat it as a password, never paste it in a doc or chat) |

ngrok extra step, also at home: dashboard → **Domains** → create the free static domain. Write down the exact name shown
(ends in `.ngrok-free.dev` or `.ngrok-free.app`). It never changes, so the app only needs it entered once.

Check both are ready:
```powershell
cloudflared --version
ngrok version
ngrok config check          # should say the config is valid and has an authtoken
```

### B. At college: which one works on this network? (30 seconds)
Cloudflare needs outbound TCP **7844**. Many campus firewalls block it. ngrok uses ordinary HTTPS (443).
```powershell
Test-NetConnection region1.v2.argotunnel.com -Port 7844    # TcpTestSucceeded : True  → Cloudflare will work
Test-NetConnection connect.ngrok-agent.com    -Port 443     # TcpTestSucceeded : True  → ngrok will work
```
(If a hostname does not resolve in your region, skip the check and simply try starting the tunnel; a block shows up as repeated
connection retries within about 20 s.)

| Result | Use |
|---|---|
| ngrok works (either result for Cloudflare) | **ngrok**: fixed URL, set once |
| only Cloudflare works | Cloudflare: URL changes every start |
| neither works | laptop hotspot, no tunnel (P1 §6.5): ESP32 + phone join the laptop's hotspot, app uses `http://192.168.137.1:8000` |

### C. Start the tunnel (pick one)

**ngrok (preferred, fixed URL)**
```powershell
ngrok http --domain=<your-domain> 8000
# <your-domain> exactly as the dashboard shows it, e.g. something.ngrok-free.dev  (no https://, no extra suffix)
```
App server link: `https://<your-domain>`

**Cloudflare (random URL each time)**
```powershell
cloudflared tunnel --url http://localhost:8000
```
It prints `https://<random-words>.trycloudflare.com`. Copy it. **It is new on every start.**
If it dies and you restart it, the URL changes and the app must be updated (then rebuild the handoff zip, P1 §6.3).

Keep the window open for the whole session. Do not run both at once; they are alternatives.

### D. Verify (from the phone, on mobile data or the college Wi-Fi, not via the laptop)
1. Open `<tunnel-url>/health/all` in the phone browser → JSON list of services (ngrok free may show a one-time "Visit Site" page: tap through).
2. Log in from the app as `dev@nutrix.dev`.
3. Scan on the scale → total updates in the app (Phase 5).

| Symptom | Fix |
|---|---|
| `connection refused` in the tunnel window | gateway not running; start Terminal D |
| ngrok `ERR_NGROK_4018` / authentication failed | the authtoken was never added: run `ngrok config add-authtoken …` |
| ngrok "domain not found / not reserved" | domain typed differently from the dashboard, or the free domain was not created |
| Cloudflare keeps retrying / no URL printed | port 7844 blocked → use ngrok or the hotspot |
| App gets HTML instead of JSON (ngrok) | add request header `ngrok-skip-browser-warning: any` in the app, or open the URL once in a browser |
| Cloudflare URL changed | update the app link; rebuild zip with `scripts/make_app_handoff.py --base-url <new url>` (P1 §6.3) |

Add the final tunnel URL to your Phase 6 notes so it lands in the evidence folder (do **not** save the authtoken).

---

## Phase 5 — Hardware session (P1 §5–§9)

Order matters: confirm the software path first (Phase 3 passed), then add the radio and the phone.

| ☐ | Step | Reference | Pass |
|---|---|---|---|
| ☐ | Network: pick **one** of: venue Wi-Fi, or laptop hotspot (P1 §6.5) | P1 §6.5 | scale and phone on the same network |
| ☐ | Windows IP + WSL IP + portproxy + firewall **[PowerShell, Admin]** | P1 §7 | phone browser loads `http://<HOST_WIFI_IP>:8000/health` |
| ☐ | Tunnel for the app: choose and start per **Phase 4B**; phone opens `<url>/health/all` | Phase 4B, P1 §6 | JSON shows |
| ☐ | Reset test data: `python scripts/reset_test_session.py --user-id 1` | P1 §3.5 | |
| ☐ | Firmware (see **Firmware reality check** below): set `ssid`/`password`/`SERVER_HOST` for the network you are on, then flash; Serial 115200 | P1 §8 | OLED "SYSTEM READY", Serial shows the ESP32 IP |
| ☐ | Scan a known food (apple/banana) | P1 §9 | OLED name+kcal, `HTTP 200`, row in `show_db_logs.py`, `source=esp32_yolo` |
| ☐ | Scan an item YOLO should not know / poor light | P1 §9.1 | 3–6 s, `source=esp32_qwen_vlm` |
| ☐ | Phone app login `dev@nutrix.dev`; totals match the scale | P1 §9 | app total = `show_redis_cache.py` total |
| ☐ | Photograph the setup + OLED + app + the terminal | — | for the paper figure |

### Firmware reality check (`esp32-code/MaruWebServer_test1.ino`, read on 2026-10-31)

| Fact in the sketch | What it means at college |
|---|---|
| `ssid` / `password` / `SERVER_HOST` are fixed to your **home** network and the laptop's home IP | Change all three to the college network (or to the laptop hotspot: `SERVER_HOST` = `192.168.137.1` normally) and **re-flash**. The ESP32 needs a **2.4 GHz** network. Check the new laptop IP with `ipconfig` (P1 §7.1). |
| Wi-Fi password is stored in plain text in the file | Do **not** commit or share the file. Prefer moving credentials to a git-ignored `secrets.h`. |
| `User-ID` = the board's **MAC address**, not `1` | Meals reach account 1 only because the server maps a non-numeric id to account 1 when `AUTO_CREATE_DEV_USER=true` (preflight checks this). To bind a different account, change the sketch to send that numeric id. |
| Device token is `NutriX_ESP32_SECURE_TOKEN` | The gateway accepts it as a built-in legacy token as well as the `.env` token, so it works. (Security note: that built-in token should be removed later.) |
| Capture is by **button press only** (GPIO 3 in the sketch); weight is the average of 5 reads at the press | There is no automatic stability trigger. Wait 1–2 s for the number on the OLED to settle before pressing. |
| Scale is **tared once at boot** | Power the scale on with an **empty platter**. Re-tare by resetting the board. |
| Reply wait is **10 s** | The first VLM call can take ~8 s: if the OLED says "API timeout" but the meal appears in `show_db_logs.py`, that is the cause. Warm up MS2 with a Phase 3 call first, or raise the timeout in the sketch to 30–40 s. |
| Camera is **QVGA (320×240)** | Small items may be hard to recognise. Fill the frame, use good light, and check `http://localhost:8001/captures/latest`. |
| The camera also runs a **live-view web server** on the board | Open `http://<ESP32 IP>/` from the laptop to aim the camera. |
| Sketch pins: button 3, OLED SDA 1 / SCL 2, HX711 DOUT 42 / SCK 41 | If wiring differs from your build, fix the constants before flashing. |

Save logs:
```bash
PYTHONPATH=. python scripts/show_db_logs.py | tee $R/10_hw_db_logs.txt
PYTHONPATH=. python scripts/show_redis_cache.py | tee $R/10_hw_redis.txt
cp inference_outputs/latest_raw.jpg $R/10_hw_latest_raw.jpg 2>/dev/null
```
Also copy `http://localhost:8001/captures/annotated` (browser, save image) for each interesting scan.

**Collect 10–20 real scale photos** with their true food and weight written down (a note on your phone is fine). That is the cleanest
"real-world" test set for later and avoids the public-label noise.

---

## Phase 6 — Wrap up

```bash
ls $R                                   # confirm all files exist
cd /home/harsh/Nutrix && git status --short   # review; do NOT commit .env
```
Shutdown (P1 §12): Ctrl+C services (MS2 first frees ~4 GB), stop tunnel, `docker compose down` (never `-v`), **[PowerShell Admin]**
`netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0`.

**Bring back to Claude** to build the final report: everything in `docs/paper-upgrade/results/college_run/`, plus
`docs/paper-upgrade/results/FINAL_RESULTS_SUMMARY.md`. Tell it which threshold you used and which images had ambiguous ground truth.

---

## If something breaks (fast table)

| Symptom | First action |
|---|---|
| Preflight FAIL docker | start Docker Desktop; `docker compose up -d postgres redis` |
| MS2 never reaches `ok` | read Terminal A; check `VLM_MODEL_PATH`; check free VRAM with `nvidia-smi` |
| CUDA out of memory | stop the benchmark/other GPU process; or `VLM_KEEP_LOADED=false` in `.env`, restart MS2 |
| Benchmark script OOM | MS2 is still running: stop it (Phase 4.1) |
| `llm-timeout` on a normal scan | MS2 down or loading: `curl localhost:8003/health` |
| `401` from scale | `DEVICE_TOKEN` in sketch ≠ `.env` |
| `400 Missing User-ID` | firmware not sending the header |
| Meal logged, app doesn't show it | scale `User-ID` ≠ logged-in account id (P1 §2) |
| ESP32 can't connect | WSL IP changed: redo P1 §7; or use the hotspot |
| App cannot reach the backend | tunnel stopped or URL changed (P1 §6.3), or switch to ngrok/hotspot |
| Negative/huge totals | `reset_test_session.py --user-id 1` (but only after Phase 4.4) |
