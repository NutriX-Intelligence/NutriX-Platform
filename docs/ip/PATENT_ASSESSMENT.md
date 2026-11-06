# NutriX — Feature Inventory and Patentability Assessment (India)

> **CONFIDENTIAL. Do not commit or push this file.** The repo's remote is `github.com/Nutrix-Intelligence/Nutrix-Platform`; if that
> repository is public, anything pushed there is a public disclosure that can destroy novelty. Keep this file local and give it only to
> your patent agent.
>
> **This is an engineering assessment, not legal advice.** Indian patent law has several exclusions that bite software-heavy
> inventions like this one. Take this document to a registered Indian patent agent (or your college's IPR cell) before filing anything.

Prepared 2026-10-31 from the repository at commit `a076b2e` plus uncommitted changes, `MASTER_ARCHITECTURE.md`, `MASTER_TESTING_PIPELINE.md`
and the hardware photo you shared.

---

## 0. What I could and could not inspect (read this first)

| Item | State |
|---|---|
| ESP32 firmware | **Now read**: `esp32-code/MaruWebServer_test1.ino`. It does **manual button capture**, not the automatic σ < 0.5 g / 500 ms stability trigger the architecture document describes. That rule is **documented only**. |
| **CAD model** | Only the six-view **image** and the hardware block diagram were provided (no STL/STEP in the repo). I describe the geometry from the image (§3). The agent will need the actual files with dimensions. |
| MS4 multi-agent system (Guardian, Clinical MDT, Meta-Auditor) | **Stub.** `ms4_agents/main.py` is 11 lines (health only). The `S_faith` score and the agent tiers exist in the architecture document and paper, not in code. |
| Per-user YOLO head adapters (shared frozen backbone, ~400 KB heads, dynamic head swap) | **Documented, not implemented.** `cv_engine.py` has no head swapping. `ms1_cv/retrain_yolo.py` is a plain CPU fine-tune from `yolov8n.pt` (and still imports from the old `backend.` path). A `user_adapters` table exists in `shared/models.py`. |
| HitL confirm flow | Paused (documented in `AI_CONTEXT.md`). `hitl_engine.py` writes a YOLO annotation from a correction but is not wired into MS1 any more. |
| Multi-item plate building (add ingredient, weigh, identify, repeat) | `MealSession` exists, but `ms1_cv/main.py` creates a **new session on every request**, so each scan is treated as a single item. Not exercised end to end. |
| "Oil absorption" in the Homely Builder | Claimed in the architecture doc; I found **no absorption logic** in `homely_meals_engine.py` (only oil nutrient rows). Do not claim it. |

**Why this matters:** a patent must be *enabled*, meaning someone skilled can build what is claimed from your description. Features
that exist only as diagrams are weak claims and can be attacked. §6 lists small builds that turn the best "documented only" ideas
into working, measured ones.

---

## 1. India: the rules that decide what is patentable here

| Provision | What it means for NutriX |
|---|---|
| **Sec. 3(k)**: a mathematical or business method, a computer programme *per se*, or algorithms are not inventions | The biggest hurdle. Pure software ideas (a scoring formula, a planner, a classifier) will be rejected unless claimed as a *technical process with a technical effect* or tied to hardware. See the 2017 *Guidelines for Examination of Computer Related Inventions* and the Delhi High Court decisions *Ferid Allani v. Union of India* (2019) and *Microsoft Technology Licensing v. Assistant Controller* (2023) on "technical effect"; have your agent confirm current practice. |
| **Sec. 3(m)**: a mere scheme, rule or method of performing a mental act | Rule tables (diet rules, substitution lists) look like this. |
| **Sec. 3(i)**: methods of medical treatment / diagnosis of humans | Clinical alerts, "diagnostic agent", treatment-style recommendations are exposed. Keep claims on data-processing, not on treating a patient. |
| **Sec. 3(p)**: traditional knowledge, or aggregation of known properties of traditionally known components | Jain / Sattvic / Ayurvedic rules and regional dish knowledge fall here. Do not rely on them as the inventive step. |
| **Sec. 3(f)**: mere arrangement of known devices each working in a known way | A load cell + camera + microcontroller on a kitchen scale is exposed unless the *combination* gives a new technical result. |
| Novelty / inventive step / sufficiency (Secs. 2(1)(j), 10(4)) | Needs a prior-art search first (§7). |
| **Prior disclosure (Secs. 29–32)** | India has only a **narrow grace period** (Sec. 31, limited cases). Treat any publication as fatal. **Your WACV submission, any arXiv posting, a public GitHub repo, demos, and the resubmitted paper are all possible prior disclosures.** Tell the agent every date. File **before** anything further goes public. |
| **Sec. 39** | An Indian resident normally must file first in India (or get permission) before filing abroad. |
| Ownership | A college project: check your institution's IP policy before anything else. The college, a guide, or co-authors may have rights. **Inventors are not the same as paper authors**: inventors are those who conceived the claimed features. |

Related, cheaper protections that actually suit parts of this project: **Designs Act 2000** (appearance of the scale, from the CAD),
**copyright** (software, documents, dataset compilation), **trademark** (the NutriX name), **trade secret** (trained weights, prompt
registry text, alias/synonym tables, diet-rule knowledge base).

---

## 2. Complete feature inventory

Status key: ✅ built (I read the code) · 🟡 built, only skimmed / partly exercised · 📄 documented only · ❓ not in repo.

### Hardware and edge
| # | Feature | Status | Notes |
|---|---|---|---|
| H1 | Smart scale: single load cell + HX711 24-bit ADC + ESP32-S3 with OV2640 camera + SSD1306 OLED + capture button, built in a custom enclosure (CAD) | ✅ photo, CAD image, firmware | See §3 |
| H2 | Articulated overhead camera arm: a column at a rear corner with a hinged joint and a tilted boom that points the camera down at the platter; fixed, repeatable geometry | ✅ CAD image / photo (a 3D-printed arm in the photo prototype) | Fixed top-down view justifies the training choices (`perspective=0`, 180° rotation, vertical flips) |
| H3 | Raised circular platter on a centre-mounted single load cell with standoffs, in a square base with a rocker power switch and a rear service/battery panel | ✅ CAD image | |
| H4 | **Manual capture on button press**: read a fresh averaged weight (5 samples), then capture a frame | ✅ firmware | The automatic stability trigger (σ < 0.5 g for 500 ms) is **not** in the firmware (📄) |
| H5 | **Fresh-frame capture**: discard the buffered (stale) frame, wait 50 ms, then take a new frame so the image matches the weight at the moment of the press (double-buffered PSRAM frame buffers) | ✅ firmware | A small but real timing/synchronisation technique |
| H6 | **Streaming multipart upload**: header fields, weight part and image part with a pre-computed `Content-Length`; the JPEG is streamed from the frame buffer in 4 KB chunks, so no full body is built in RAM; one atomic request carries weight + image + device token + user id | ✅ firmware | |
| H7 | On-device result display: name, weight, kcal, confidence parsed from the JSON reply; continuous live weight on the OLED between captures | ✅ firmware / photo | The photo shows "Popcorn / 80.4 g / **0.00 kcal** / Conf 95.0%" (see §3) |
| H8 | HX711 start-up diagnostic (ready-timeout check, tare, test reading) and calibration factor | ✅ firmware | Tare only at boot |
| H9 | Camera live-view web server on the device | ✅ firmware | Freenove example server; useful for aiming the camera |
| H10 | Device identity: the sketch sends its **MAC address** as `User-ID` plus a device token | ✅ firmware | The server falls back to account 1 for a non-numeric id when `AUTO_CREATE_DEV_USER=true` |
| H11 | Camera set to QVGA (320×240) JPEG, quality 12, 10 MHz clock | ✅ firmware | Low resolution: relevant to how well the VLM can recognise small items |

### Gateway and security
| # | Feature | Status |
|---|---|---|
| G1 | Single front door; device-token auth for scales, JWT for the app; injects `X-User-ID` | 🟡 |
| G2 | Scale-to-account binding by numeric `User-ID` header with no scale login; auto-create dev user | ✅ |
| G3 | Per-route timeouts, request-id propagation, aggregated `/health/all` | 🟡 |

### MS1: vision and ingestion
| # | Feature | Status |
|---|---|---|
| V1 | YOLOv8n 123-class detector (same checkpoint as the paper, md5 verified) | ✅ |
| V2 | Confidence gate (`YOLO_CONF_THRESHOLD`) deciding fast path vs fallback | ✅ |
| V3 | **Suppressed-class rule**: known over-predicted classes (lassi, kulfi) are treated as unidentified **and the detector's guess is withheld from the VLM** so it cannot anchor the answer | ✅ `cv_engine.py`, `main.py` |
| V4 | Weight-delta guard: changes under 0.5 g (including negative tare) are ignored, nothing logged | ✅ `cv_engine.py:149` |
| V5 | Provenance tag on every log: `esp32_yolo` / `esp32_qwen_vlm` / `llm-timeout` | ✅ |
| V6 | Explicit failure mode: MS2 unreachable gives 0 kcal and `llm-timeout`, never an invented value | ✅ |
| V7 | Low-confidence frames saved to `dataset/pending` for later labelling | ✅ |
| V8 | Annotated image rendering (box or banner) for live inspection | ✅ |
| V9 | Multi-item incremental plate sessions (delta attribution per added item) | 🟡 class exists, unused per request |
| V10 | HitL one-tap confirm, auto YOLO annotation, adapter retrain | 📄 / paused |
| V11 | Per-user shared-backbone + head-adapter swapping | 📄 not implemented |

### MS2: local VLM and nutrition service
| # | Feature | Status |
|---|---|---|
| L1 | Local Qwen3-VL-2B, resident in 6 GB VRAM with YOLO (≈4.4 GB total); no cloud call in the scan path | ✅ |
| L2 | One call returns label **and** per-100 g macros as strict JSON | ✅ |
| L3 | **Energy-consistency guard**: |4P+4C+9F − kcal| / kcal ≤ 0.25, range bounds, P+C+F ≤ 100 g; flagged macros are never stored | ✅ `validation.py` |
| L4 | **Repair-or-reject rule**: if kcal disagrees with its own macro grams by a moderate ratio (0.5–2×) or kcal is 0, recompute kcal from the grams; beyond that, flag and reject | ✅ `validation.py` (uncommitted) |
| L5 | Name-only second pass when the full JSON answer collapses to "unknown" | ✅ `ms2_llm/main.py` |
| L6 | Runtime-editable prompt registry (DB, cached 60 s) so prompts can be patched without restart | ✅ `prompts.py` |
| L7 | Audit row for every vision/lookup call (confidence, latency, flagged) | ✅ |
| L8 | Text lookup endpoint: DB first, then model, then persist | ✅ |

### Knowledge layer (shared)
| # | Feature | Status |
|---|---|---|
| K1 | **Tiered canonical lookup**: normalise, exact name, alias, trusted-brand partial match | ✅ `food_lookup.py` |
| K2 | **Self-growing, provenance-tagged food base**: model-inferred foods saved as brand "LLM Inferred" with an alias row; next lookup is a plain DB hit; auditable | ✅ |
| K3 | Empty-nutrient duplicate rows cannot shadow a complete row (`_first_with_macros`) | ✅ (uncommitted) |
| K4 | ~1,880 foods from ICMR/INDB, USDA, UK/US tables, regional recipes | 🟡 count unverified (tasks4 4.0.4 unchecked) |
| K5 | Fast-food dataset (3,355 items / 8 chains) | 🟡 |

### MS3: user, analytics, planning
| # | Feature | Status |
|---|---|---|
| U1 | **Canonical macro payload writer** used by MS1, MS3 and a DB trigger; totals recomputed from `meal_logs` so they stay correct after inserts **and deletes** | ✅ `macro_sync.py`, Alembic 002 |
| U2 | Postgres `NOTIFY` trigger, Redis key + pub/sub + stream (for agents), SSE live dashboard with heartbeat and polling fallback | ✅ / 🟡 |
| U3 | Daily-summary: consumed / target / remaining / percent from Redis, DB fallback | 🟡 |
| U4 | Indian-context dietary classifier: vegan, vegetarian, **Jain, Sattvic**, eggetarian, halal, keto, FODMAP, allergens, clean-label (E-numbers) with substitution knowledge base | 🟡 `classification_engine.py` (1,066 lines) |
| U5 | Recipe retagging: declared tag kept unless ingredients contradict it, then the safer classifier tag wins | ✅ `recipe_tagging.py` |
| U6 | Meal-plan MIP (OR-Tools / SCIP): one recipe per slot, macro and fibre targets, soft-penalty fallback so a plan always exists | 🟡 `optimization_engine.py` |
| U7 | Plan-candidate gate: per-slot calorie windows and condiment/spice-mix filter so a planner cannot pick "rasam powder" or a whole-batch total as a meal | ✅ `meal_candidates.py` |
| U8 | Adaptive calorie target: weight trend + 7-day adherence gate, bounded ±100–200 kcal steps | ✅ `adaptive_planner.py` |
| U9 | Recipe ranker + rule-based explanation engine (no LLM) | 🟡 |
| U10 | Barcode resolver: curated cache, OpenFoodFacts, search scraper, Gemini estimate; healthier/cheaper alternatives under diet filters | 🟡 `barcode_service.py` (1,062 lines) |
| U11 | Nutrition-label OCR (local OCR / Gemini) with field parser | 🟡 |
| U12 | Homely meal builder: household units (katori, tbsp) to grams, fuzzy ingredient match, per-user community-meal visibility (mine / pending / approved / rejected per viewer) | ✅ / 🟡 |
| U13 | Health scorer (0–100) with ICMR/Codex-style reference values | 🟡 |
| U14 | Centralised Gemini client with retries, offline fallback to MS2 | 🟡 |
| U15 | Optional ML recipe-score model (XGBoost/RandomForest) | 🟡 |

### Agent layer (MS4) and client
| # | Feature | Status |
|---|---|---|
| A1 | Tier 2A Guardian: condition-specific thresholds (diabetic, hypertensive, post-surgical, calorie-restricted) on the live macro stream | 📄 |
| A2 | Tier 2B Clinical MDT: diagnostic, intervention (LP), drafting agents, dietitian sign-off | 📄 |
| A3 | Tier 3 Meta-Auditor: faithfulness score S_faith, patches the prompt registry when hallucination is detected | 📄 (the registry it would patch exists, L6) |
| A4 | Tier 1 NL-to-tool orchestrator | 📄 |
| C1 | Flutter app: Riverpod, JWT in Keystore, biometric re-lock with a flag to avoid false lock on camera launch | 📄 (separate app repo) |

---

## 2B. Design-stage features (not built), written up so they can go into a provisional specification

You asked to include these. A provisional can describe them as **further embodiments**, but a claim needs a description detailed enough for a
skilled person to build it, so each entry says what would be described. The **complete** specification (within 12 months) should claim only
what is built and measured by then; unbuilt ideas can still be reserved by describing them now. Do not describe anything in the filing as
"implemented" or "tested" unless it is.

| # | Feature (design only) | What to describe | Why it could matter | Caution |
|---|---|---|---|---|
| P1 | **Automatic stable-weight capture** | A moving window of load-cell samples; capture fires when the standard deviation stays below a limit (0.5 g) for a set time (500 ms); rejects hand movement and settling; ignores negative or tare events on the device | Removes the button; avoids blurred or mistimed frames; ties image capture to a physical event | Common in scales; novelty only in what the capture then feeds (A-1) |
| P2 | **Multi-item plate session** | Keep a session across presses; each new stable weight minus the previous total is attributed to the item identified in that frame; an unidentified item is stored as a placeholder (code exists: `unidentified_item`, last stable weight advanced) and resolved later; session ends when the platter returns to zero | Builds a whole plate item by item with a single camera and scale; per-item nutrition without segmentation of mixed plates | Needs a working demo (B-2) |
| P3 | **One-tap confirmation (HitL)** | The VLM's candidate is pushed to the phone as "We think this is X, confirm or edit"; the confirmed label becomes a training label with an **automatic bounding box** (the detector's fallback box, or a centred default box); image moved from `pending` to `trained` (code: `hitl_engine.py`) | Cheap, user-specific labelling without manual annotation | Part of A-3 |
| P4 | **Per-user detection head adapters** | A shared backbone (layers 0–9) loaded once; per-user small heads (~400 KB) stored in `user_adapters` with class mappings and a version; selected by account id at inference; fall back to the global head when none exists or confidence is low; head-only training (`freeze=10`) in seconds | Personalised models for many users on one GPU with no per-user model copy | **A-3**; adapters are known in ML, so claim the loop and show measured gains |
| P5 | **Drift-triggered retraining** | When a food repeatedly falls below the confidence gate, move its pending frames to the training set and run a short head fine-tune automatically | Self-improving detector | Needs P3/P4 first |
| P6 | **Tier 1 orchestrator agent** | Natural-language request to a typed tool call (`query_macros`, `log_meal`, `get_daily_summary`, `recommend_recipes`, `generate_meal_plan`) and NL-to-SQL over the user's own data | Voice/text logging and queries | Software only (Sec. 3(k)) |
| P7 | **Tier 2A guardian agent** | Condition profiles (diabetic, post-surgical, hypertensive, calorie-restricted) with warning and critical thresholds evaluated continuously on the live macro stream; escalation L1 push, L2 database alert, L3 handoff after 24 h uncorrected | Real-time, per-condition monitoring tied to the scale's measurements | **Sec. 3(i)** (medical diagnosis/treatment) and 3(k); claim as data monitoring with an automatic technical response, not as treating a patient |
| P8 | **Tier 2B clinical team (diagnostic → intervention → drafting)** | 30-day log and weight trend analysis produces a deficit vector; a linear program minimises the weighted absolute deviation from targets; a drafting step writes a report for dietitian sign-off | Closed loop from measurements to a computed plan | 3(i), 3(k); a standard LP |
| P9 | **Tier 3 meta-auditor with faithfulness score** | S_faith = weighted relative agreement of predicted macros with reference tables (weights protein 0.35, energy 0.30, carbs 0.20, fat 0.15); below 0.70 the system patches the runtime prompt registry with grounded constraints (LLM), triggers detector retraining (CV drift), or isolates the database record; runs on a 15-minute cycle | A closed-loop correction of a generative model using ground-truth tables; the registry it patches already exists (L6) | **B-4**; build a minimal version first |
| P10 | **Hybrid deterministic/stochastic agent split** | Deterministic components (solver, detector, fuzzy string normalisation, BMR/TDEE) carry numbers; stochastic components (LLM) only classify intent and write text | Limits hallucination exposure | Architectural principle, hard to claim alone |
| P11 | **Offline retry queue for failed VLM calls** | Queue unresolved captures and re-resolve them later, back-filling the log | No lost scans on outages | Small build |
| P12 | **Dashboard with device status, live graph and alerts** (the block diagram's 5th block) | Live weight and history, captured images, device online/offline, alerts and notifications | Operator visibility | Partly present (SSE summary); device status not built |
| P13 | **Barcode capture from the same camera** | Decode a barcode in the frame before running the food classifier and resolve the product | One device for packaged and fresh food | MS3 already resolves barcodes from an uploaded image; not wired to the scale |

**Which of these are worth including:** P4 + P3 + P5 (the personalisation loop), P9 (the faithfulness loop), P1 + P2 (the weight-gated capture and
sequential attribution). P6–P8 are the weakest in India (Sec. 3(k) and 3(i)); describe them briefly as further embodiments only.

---

## 3. The hardware: photo, CAD image, block diagram and firmware

**Prototype photo.** A retrofitted commercial kitchen scale (cream base, green platter) with the ESP32-S3 camera board at the top of a
vertical gold 3D-printed pillar, an HX711 board and OLED glued into the base compartment, and a separate red push-button module. The OLED
reads *Popcorn, Weight 80.4 g, Calories 0.00 kcal, Conf 95.0 %*.

**CAD (six-view image).** A purpose-built enclosure, which is a stronger design/utility position than the retrofit in the photo. What the
views show (verify against the real files):
* A **square base with rounded corners** and a lip, hollow inside; a flat bottom with a small rectangular cut-out and a corner screw hole (service access).
* A **raised circular platter** with a central fixing point and four screws around it, sitting on **standoffs** (red pads at the edges) over the base: consistent with a centre-mounted single load cell with a floating platter.
* A **rocker power switch** (red, I/O) and a **dark rectangular module** (battery/charger or connector block) on the top-front corner area; a rear panel with slots and a connector or screw terminals.
* An **articulated camera arm**: a vertical column at the rear-right corner, a hinged elbow near the top, and a tilted boom that carries the camera board and points it down and inward at the platter (the top view shows the camera at the upper-right of the platter).
* Overall shape: low and compact, camera arm taller than the base is wide.

**Hardware block diagram (the 5-block figure).** Sensing (load cell → HX711 over DOUT/SCK; OV2640 over DVP) → ESP32-S3 → OLED over I²C →
Wi-Fi → REST API with database and image storage → web/phone dashboard. **Fix before using it in a filing or paper**, because patent drawings
must match the embodiment:
* It labels the display "TFT Display (SSD1306)"; the SSD1306 is an **OLED**.
* It shows weight in **kg** and a **"Stable"** status; the firmware shows **grams** and has **no stability detection**.
* It lists "Fetch configuration / data (GET)"; the firmware makes **no GET** call.
* It omits the **capture button**, the **local GPU services (YOLO, VLM, nutrition database)** and the **canonical nutrition/Redis/app path** that make the
  system novel. A filing drawing should show those blocks and the weight-and-image flow into the classifier gate.

**Firmware facts that change earlier statements.**
* Capture is by **button press only**; no auto-trigger and no stability test. The "σ < 0.5 g for 500 ms" rule in `MASTER_ARCHITECTURE.md` is not implemented.
* `User-ID` is the **MAC address**, not a numeric account id, so scans reach account 1 only through the server's `AUTO_CREATE_DEV_USER` fallback (`ms1_cv/main.py`, `_resolve_scale_user`). `MASTER_TESTING_PIPELINE.md` assumed a numeric `USER_ID` constant; it has been corrected.
* The gateway accepts the `.env` `DEVICE_TOKEN` **and** a hard-coded legacy token (`gateway/middleware/device_auth.py`); the sketch uses the legacy one. That is a security weakness for later (anyone who reads the sketch can authenticate); not an IP matter.
* The sketch waits only **10 s** for the server reply; the VLM's first call can take about 8 s, so a slow scan may show "API timeout" on the OLED although the meal was logged.
* The sketch contains the **Wi-Fi password in plain text** and the server IP; do not commit it (the folder `esp32-code/` is untracked and **not** git-ignored).

Observations that matter for IP and for your demo:
* **The OLED shows 0.00 kcal.** A confidence of exactly 95.0 % is what the VLM self-reports by default, so this looks like the VLM named
  popcorn but no macros were resolved (database miss and the model's macros flagged or the lookup failed). Do not use this frame as a
  success example; fix the path (§6) or use another capture.
* In the CAD the **camera column appears to be fixed to the base, beside the platter, not to the platter**. If true, the camera's mass and
  vibration never load the weighing element, so the tare and reading are unaffected by the camera and arm adjustments. That is a specific
  technical effect and the best basis for a hardware claim. Confirm it with the real CAD (how the column is fixed, clearance to the
  platter, whether the elbow angle is adjustable, and the camera's field of view and standoff over the platter).
* The photo prototype has no enclosure, shield or calibration mark; the CAD is the real design. If the CAD includes glare/shadow shielding,
  cable routing, tilt limits or a calibration mark on the platter, list them for the agent.
* Photos like this are **dated evidence of reduction to practice**. Keep originals with metadata, plus git history and any lab notes.

---

## 4. Patentability ranking

**Honest summary:** the strongest candidate is not any single algorithm but the **system-level combination** of a weighing scale, camera and local
edge/server inference with specific safeguards around a generative model. Pure planner, scoring and rule-table features are weak in India
(Sec. 3(k), 3(m), 3(p)). Several of the most technical ideas are not built yet.

### Tier A: worth a prior-art search and a provisional filing

**A-1. Weight-triggered hybrid food identification with a local VLM fallback and anti-anchoring suppression** (V2, V3, L1, K1; built)
* *Problem:* detectors over-predict certain classes and give no answer for unseen foods; generative models hallucinate and, if shown the detector's guess, repeat its mistake.
* *What is new (the combination):* (1) on a weighing device, a stable-weight event triggers capture; (2) a first classifier result is accepted only above a confidence gate **and** only if its class is not on a per-class distrust list; (3) otherwise a second, open-vocabulary model on the same device class labels the frame, **and the first model's guess is deliberately withheld when its class is on the distrust list** (anti-anchoring); (4) the label is mapped to a canonical food by tiered lookup; (5) the measured weight multiplies per-100 g values to give the meal's nutrients.
* *Technical effect for Sec. 3(k):* reduces unidentified and wrongly-identified captures; bounded latency (≈50 ms fast path, ≈2.3 s fallback); fits in 6 GB VRAM beside the detector with no cloud call.
* *Evidence you have:* 7-image benchmark (3 of 4 detector failures rescued, all calories from the DB), VRAM and latency numbers, lassi/kulfi case.
* *Risks:* crowded prior art on camera + scale calorie trackers and on LLM food recognition; the novelty is in the safeguards and the combination, so claim those specifically. 3(f) risk if claimed as "scale + camera + model" only.
* *Strengthen with:* an ablation of hint vs no-hint on distrusted classes (a measured anti-anchoring effect).

**A-2. Plausibility-gated acceptance and repair of generative-model nutrition values** (L3, L4, K2; built)
* *What is new:* a machine-checkable physical-consistency test on model output (energy from macro grams, bounded range, mass ≤ 100 g per 100 g), with a **repair-or-reject rule** (recompute energy from macro grams when the discrepancy is within a ratio band, otherwise reject), and a persistence rule that **only accepted values are written back** to the food base, tagged by provenance, so the knowledge base grows without absorbing hallucinations.
* *Technical effect:* data-integrity control of a stochastic component; prevents contaminating a persistent store.
* *Risks:* a formula plus a rule is a Sec. 3(k) target; claim it as part of the system in A-1 (device captures, model infers, validator gates, store updates), not stand-alone. Atwater factors (4/4/9) are well known; the novelty is the gating/repair/persist flow.
* *Strengthen with:* data on how many model outputs the guard rejected and the error with and without it (in your benchmark 5 of 7 were flagged; sweet potato 320 vs ≈86 kcal/100 g).

**A-3. Per-user lightweight adapter personalisation on a shared frozen backbone, bootstrapped by a VLM suggestion** (V10, V11; **documented only**)
* *What is new (the combination):* a VLM proposes a label for a low-confidence frame; a one-tap confirmation turns it into an automatic bounding-box annotation; only a small detection head is retrained (backbone frozen); the head (hundreds of KB) is stored per user and swapped onto one resident backbone at inference by account id, with fallback to the global head.
* *Technical effect:* thousands of personalised models with one backbone in GPU memory; seconds to retrain; no full-model copies.
* *Risks:* head swapping / adapters / LoRA are known in ML, so inventive step rests on the **end-to-end loop** (VLM suggestion → annotation → head-only retrain → per-user swap on a scale) and on measured gains. **Not implemented**, so enablement is weak today.
* *Do:* build a minimal version (§6) before filing, or file a provisional that describes it as an embodiment and complete it within 12 months.

### Tier B: possible, needs the right framing or more work

**B-1. Camera-scale hardware: enclosure, floating platter and articulated camera arm** (H1–H3, CAD). Two routes:
* **Designs Act registration** of the scale's external form from the CAD: cheap, fast, protects appearance only. **File it before you publish any photo or CAD** (the CAD image and photo shown to me are not public yet; keep them that way).
* **Utility patent on the arrangement**: faces Sec. 3(f) (arrangement of known devices) unless you claim a specific technical result. The candidate result is **mechanical decoupling**: a weighing platter carried by a single centre load cell, and a camera arm fixed to the **base** (not the platter) so the camera's mass and arm adjustments do not change the weight reading, while the hinged boom gives a fixed, repeatable view geometry (field of view and standoff matched to the platter) that the model training relies on. Back it with a measurement (e.g. tare/reading drift while moving the arm) before relying on it.

**B-2. Weight-gated capture with delta guard and sequential-item weight attribution** (H4, V4, V9, plus the documented stability trigger). A stable-weight auto-capture is common in scales, so novelty is low, and it is **not in the firmware today**. It becomes interesting only if you **build and demonstrate** the incremental plate method (identify each added item, attribute the weight delta to it, carry the running total across presses) end to end.

**B-5. Weight-image synchronisation on a camera scale** (H5, H6). Read the load cell, flush the camera's buffered frame, capture a fresh one, and send weight and image in one atomic streamed multipart request so the stored image always corresponds to the measured weight; the result returns on the same connection and is shown on the device. Embedded engineering, individually common, so novelty is weak alone. Mention it as a dependent feature of A-1; it supports the technical-effect story (no stale-frame mismatch between photo and weight).

**B-3. Single-writer canonical macro synchronisation** (U1, U2). Several writers (scale service, app service, DB trigger) produce one canonical payload; totals are **recomputed from the source of truth** after insert and delete; one change fans out to a cache, a pub/sub channel, an agent stream and an SSE feed, with a polling fallback. Software architecture, so Sec. 3(k) is the obstacle; weak unless tied to a measured latency/consistency effect. Better kept as copyright / trade secret.

**B-4. Self-healing prompt registry with an external ground-truth faithfulness loop** (L6, A3; registry built, auditor **not built**). Measure the model's numeric faithfulness against reference composition tables, and when it drops below a threshold, automatically write grounded constraints into a runtime prompt store that the inference service re-reads without restart. A closed-loop control idea with a plausible technical effect, but only the registry half exists. Build a minimal auditor first.

### Tier C: protect another way (copyright / trade secret), patent unlikely in India

| Feature | Why weak |
|---|---|
| Indian dietary classification and substitution tables (Jain, Sattvic, halal, FODMAP) (U4, U5) | Rules over knowledge: Sec. 3(m) and 3(p) (traditional knowledge). Keep the curated rule data as a trade secret and database compilation under copyright. The "safer classifier wins" contradiction rule is a nice quality control but is a rule, not a technical process. |
| Meal-plan MIP, plan-candidate gate, adaptive target controller (U6, U7, U8) | Mathematical/optimisation methods and business logic: Sec. 3(k). SCIP/OR-Tools are standard; the gate and the stepped controller are domain rules. |
| Barcode/label resolver and healthier/cheaper alternatives (U10, U11) | Aggregation of existing services and heuristics. |
| Household-unit conversion and community-meal visibility (U12) | Lookup tables and access-control logic; unit tables are traditional/common knowledge. |
| Health score, recipe ranker, explanation engine (U9, U13) | Scoring formulas. |
| Scale-to-account binding by header and device token (G2) | Common IoT pattern. |
| Flutter app features, biometric re-lock flag (C1) | Standard mobile patterns. |

### Tier D: not protectable as inventions
Using YOLOv8, Qwen3-VL, OR-Tools, Redis, FastAPI; the 123-class dataset (copyright/licence only, and it merges three third-party Roboflow
sets, so check their licences); the paper's normalisation idea in the abstract; Mifflin-St Jeor targets.

**Licensing flag (not patent law, but it affects commercialising):** Ultralytics YOLOv8 is under **AGPL-3.0**. Shipping it in a product
generally means releasing your source or buying an enterprise licence. Check this before any commercial plan.

---

## 5. Suggested claim skeletons (prose only, for the agent to refine)

**A-1 (system):** A food-measuring apparatus comprising a load cell, a camera arranged to image the weighing surface, and a processor
configured to: capture a weight and an image when the weight is stable; run a first classifier on the image; accept its result only when its
confidence exceeds a threshold and its class is not on a stored list of distrusted classes; otherwise submit the image to a second,
open-vocabulary model **without** the first classifier's class when that class is on the list; map the second model's label to a canonical
food through successive exact-name, alias and restricted partial matching; obtain per-unit-mass nutrient values from a stored food record
and multiply by the measured weight; and record the result with a tag identifying which classifier produced the label.
*Dependents:* the confidence-and-distrust gate values; recording a failure tag and zero nutrients when the second model is unavailable;
the weight-change guard; the hardware geometry from the CAD; the same flow on a local GPU with both models resident.

**A-2 (method):** receiving nutrient values for a food from a generative model; testing that energy equals a weighted sum of macronutrient
masses within a tolerance and that masses and energy lie within bounds; when the discrepancy lies within a ratio band, replacing the energy
with the sum from the macronutrient masses; otherwise rejecting; writing only accepted values to the food store with a provenance
attribute, and returning them on later lookups of the same or an alias name.

**A-3 (system, after it is built):** as described in Tier A-3, with the head storage, head selection by account id with fallback, and the VLM-seeded annotation step.

---

## 6. Small builds that strengthen the filings (do these before the provisional is finalised)

| # | Build / measurement | Strengthens | Effort |
|---|---|---|---|
| 1 | Hint vs no-hint ablation on the suppressed classes (and a few other low-confidence cases): how often does the VLM repeat the detector's wrong class when shown it? | A-1 anti-anchoring: gives a measured technical effect | Small |
| 2 | Log guard outcomes: share of VLM macros rejected/repaired, and error vs DB with and without the guard | A-2 | Small (data already partly in the benchmark JSON) |
| 3 | Implement per-user head adapter: freeze backbone, train head only, save ~400 KB, swap at inference; measure VRAM, retrain time, accuracy gain on a user's own foods | A-3 (turns "documented" into "built") | Medium |
| 4 | Minimal Meta-Auditor: compute faithfulness against the DB for logged VLM values and write a constraint into the prompt registry | B-4 | Medium |
| 5 | Wire multi-item sessions (keep the session across presses) and demo adding three items | B-2 | Small–medium |
| 6 | Fix the **0.00 kcal** path seen on the OLED (popcorn): when the DB misses and the model's macros are flagged, the lookup should still produce a value or the OLED should show "unknown kcal" rather than 0 | Demo quality and honesty of the claims | Small |
| 7 | Keep the CAD files (STEP/STL) privately with dimensions, camera field of view and standoff, arm angle range and a parts list; redraw the block diagram to match the real system (§3) | Everything hardware; Design registration | Small |
| 9 | Implement the automatic stable-weight trigger in the firmware (window σ < 0.5 g for 500 ms) and measure false triggers | P1 / B-2 | Small |
| 10 | Measure whether moving the camera arm or camera mass changes the weight reading (tare drift test) | B-1 mechanical decoupling claim | Small |
| 11 | Send a numeric account id as `User-ID`, raise the reply timeout to ≥ 15 s (40 s recommended), keep credentials out of the source (a `secrets.h` that is git-ignored) | Reliability, and avoids leaking the Wi-Fi password | Small |
| 12 | Keep dated records: photos with metadata, signed and dated lab notes, git history | Inventorship and reduction to practice | Ongoing |

---

## 7. Filing plan for India (discuss each point with a registered patent agent)

1. **Before anything else:** decide who the inventors and applicants are, and read your college's IP policy. Do not publish, push, post or demo
   anything new until the first filing is made. List every past disclosure with a date (WACV submission and any public availability of it,
   GitHub repository visibility, arXiv, presentations, social posts).
2. **Prior-art search** (a few hours): Indian Patent Advanced Search System (InPASS), Google Patents, Espacenet. Search terms to try: smart
   kitchen scale camera food recognition calorie; weight-triggered image capture food; vision-language model nutrition estimation; hallucination
   guard nutrient energy consistency; per-user adapter detection head; food detector fallback multimodal model.
3. **Provisional specification** (Form 2, provisional) covering A-1, A-2, A-3 and B-4 with the technical effect data from §6, then the **complete
   specification within 12 months**. Consider a PCT filing only if you plan to commercialise abroad; Sec. 39 applies.
4. **Design registration** for the scale form from the CAD, filed **before** publishing photos or the CAD.
5. **Costs and speed:** ask the agent about fee concessions for students, startups or small entities and about expedited examination, and
   whether your college's IPR cell or a government scheme funds filing. I have not quoted fees because they change.
6. **Other protection now:** copyright notices in the code and docs; register the NutriX trademark after a clearance search; mark prompts,
   alias tables and rule knowledge as trade secrets (restrict repo access, do not publish them in the paper).
7. **Order of disclosure:** patent filing first, then the paper resubmission, then the open-sourcing decision.

---

## 8. One-page answer

* **Best to patent (India):** A-1 hybrid identification system with anti-anchoring and DB-grounded macros; A-2 plausibility-gated acceptance/repair
  and write-back; A-3 per-user adapter loop (build it first).
* **Hardware:** Design registration for the enclosure and camera-arm form (from the CAD) before any publication; a utility claim only if you can show the
  mechanical decoupling (camera fixed to the base, platter on a single load cell) with a measurement.
* **Cheap and fitting:** Design registration, copyright, trademark, trade secrets for the knowledge data.
* **Do not expect to patent:** planner, health score, diet rule tables, barcode/OCR chain, adaptive targets, app features, use of YOLO/Qwen/OR-Tools.
* **Biggest risks:** Sec. 3(k)/3(f) (software and known-device arrangement), earlier public disclosure (paper, GitHub), and unbuilt features
  (agents, adapters) that cannot support claims yet.
