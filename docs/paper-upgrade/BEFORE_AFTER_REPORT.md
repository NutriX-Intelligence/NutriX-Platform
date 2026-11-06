# NutriX — Before / After Report (WACV Round 2 → Post-LLM System)

> Companion files: [`REVIEWER_CONCERNS_MATRIX.md`](REVIEWER_CONCERNS_MATRIX.md) (every review point → status) and
> [`EVALUATION_PLAN.md`](EVALUATION_PLAN.md) (tests still to run, with commands).
>
> **Before** = the system as submitted (YOLOv8n-only perception; numbers from `docs/Raj Docs/`).
> **After** = Phase 4–5 system (YOLOv8n fast path + Qwen3-VL-2B fallback + shared multi-tier food lookup + MS3).
> Every number below is tagged with where it comes from. Anything I could not trace to an artifact is marked **UNVERIFIED**.

---

## 1. The one-paragraph story (use this in the rebuttal / resubmission)

**The detector was not improved.** The YOLOv8n checkpoint is the *same file* as the submission
(`runs/nutrix_custom_model-2/weights/best.pt`: 58.78 % mAP@50, 40.56 % mAP@50:95 on the 123-class set; 81.56 % mAP@50 on the
31 Indian classes). Reviewers were right that those numbers are hard to interpret (median 3 val images/class, 37 classes with
none) and we have not changed them. What changed is **what happens when the detector is not sure**: instead of logging
"Unknown" (or a wrong class such as lassi/kulfi), the frame is routed to a local vision-language model (Qwen3-VL-2B), its
free-form label is normalised to a canonical food through a shared alias/DB lookup, and macros come from the nutrition DB
(the VLM's own macros are only a persisted last resort). The contribution is therefore **system-level accuracy and coverage
at the pipeline output, not detector accuracy**.

---

## 2. What changed and what did not

| Component | Before (submission) | After | Changed? |
|---|---|---|---|
| YOLOv8n detector (123 classes) | `best.pt`, 58.78 / 40.56 mAP | identical checkpoint (SHA-256 of `backend/services/ingestion/best.pt`, `ms1_cv/nutrix_yolo_custom.pt` and `runs/nutrix_custom_model-2/weights/best.pt` all match) | **No** |
| Low-confidence handling | Logged as `Unknown` with placeholder macros (in the quoted DB rows calories == weight, i.e. a 100 kcal/100 g default, not a flat 40.1 kcal) | Routed to MS2 Qwen3-VL-2B (`/api/v1/llm/vision-infer`) | **Yes (new)** |
| Known YOLO over-predictions | Lassi/Kulfi logged as-is | `YOLO_SUPPRESSED_CLASSES=lassi,kulfi` → treated as unidentified, not passed as hint | **Yes** |
| Confidence gate | 0.3 during testing | `YOLO_CONF_THRESHOLD=0.5` (`ms1_cv/main.py:39`) | **Yes** |
| Label → nutrition mapping | Closed 123-class vocabulary; hard-coded `sample_kcal`, default 100 kcal | `shared/food_lookup.py`: exact name → alias → trusted partial; DB miss → `/llm/lookup`; LLM output persisted as brand "LLM Inferred" | **Yes** |
| Macro guardrails | none | range bounds + Atwater check `|4P+4C+9F−kcal|/kcal ≤ 0.25`; flagged macros never persisted (`ms2_llm/validation.py`) | **Yes** |
| Scale noise | negative / huge weights logged as `Unknown` meals | `status: ignored`, nothing logged (`ms1_cv/main.py`, Phase 4). The `Δweight < 0.5 g` check itself (`ms1_cv/cv_engine.py:149`) has existed **since the initial commit** (`git log -S`), so the Phase 4 change is that ignored events are no longer logged | **Yes — but this is NOT an LLM gain** (see §5) |
| MS2 failure | n/a | MS2 down/timeout → `source="llm-timeout"`, 0 kcal, no crash | **Yes** |
| Provenance | `esp32_smart_scale` for everything | `esp32_yolo` / `esp32_qwen_vlm` / `llm-timeout` in `meal_logs.source` | **Yes** |
| Barcode / OCR | MS1 | Moved to MS3 (OpenFoodFacts → scraper → Gemini; OCR via Gemini/local) | Moved; **still unevaluated** |
| Meal planner (OR-Tools/SCIP) | Table 8: 40–50 % feasibility | Unchanged algorithm, now in MS3 | **No new results** |
| Per-user adapters + HitL retraining | Described in architecture | Code exists (`hitl_engine.py`, `retrain_yolo.py`) but **paused**; Qwen label logged directly | **Standby** (§7) |
| Multi-agent tiers (MS4) | Not in the paper's scope | Scaffold only in this repo state; not evaluated here | **Standby** |

---

## 3. Evidence available today

### 3.1 Detector (unchanged — pre-LLM paper numbers)
Source: `docs/Raj Docs/rajDocs4/WACV_FAST_EVALUATION_RESULTS.md`, `rajDocs5/chatTable.md`.

| Metric | Value |
|---|---|
| 123-class test: P / R / mAP@50 / mAP@50:95 | 71.08 / 51.32 / 58.78 / 40.56 |
| Indian 31-class subset: P / R / mAP@50 / mAP@50:95 | 78.94 / 74.70 / 81.56 / 63.33 |
| Rotation (200 val imgs) mAP@50 at 0/90/180/270° | 89.24 / 89.11 / 88.75 / 88.04 |
| Val coverage | median 3 img/class; 37 classes with 0; 30 with <5 |
| `brinjal` recall vs `eggplant` | 0.00 vs 0.7141 (taxonomy fragmentation) |

### 3.2 Pipeline benchmark (7 real images) — raw artifact `inference_outputs/post_llm_benchmark_results.json`
Run 2026-10-27, RTX 3050 6 GB, `scripts/evaluate_post_llm.py`, threshold 0.5. Values below are copied from the JSON.

| Image | Ground truth | YOLO (status, ms) | Qwen3-VL-2B | Final route | Final label | kcal (macro src) | E2E ms |
|---|---|---|---|---|---|---|---|
| appleTest.png | Apple (180 g) | unidentified, 2,694 (first call, warm-up) | apple | Qwen | Apple ✔ | 93.6 (db) | 8,001 |
| banana-trial.jpg | Banana (120 g) | identified 78.3 %, 61 | banana | YOLO | Banana ✔ | 106.8 (db) | 66 |
| tomato-trial.jpg | Tomato (95 g) | identified 83.1 %, 60 | tomato | YOLO | Tomato ✔ | 17.1 (db) | 80 |
| watermelon-trial.jpg | Watermelon (350 g) | unidentified (`greenchutney`), 79 | watermelon | Qwen | Watermelon ✔ | 105.0 (db) | 2,476 |
| sweet-potat-test.jpg | Sweet potato (210 g) | unidentified (no box), 65 | sweet potato | Qwen | Sweet Potato ✔ | 180.6 (db) | 2,438 |
| IDLI.jpg | Idli (150 g) | identified 52.8 %, 45 | idli | YOLO | Idli ✔ | 210.0 (db) | 50 |
| esp32.jpg | "Carrot/Apple/Tomato (scale plate)" | unidentified (`bell pepper`), 11 | bell pepper | Qwen | Bell Pepper ✘ vs stated GT | 30.0 (db) | 2,070 |

Summary (computed from the table; n = 7, **no statistical power**):

| Metric | Before (YOLO only, abstain below 0.5) | After (hybrid) | 95 % Wilson CI |
|---|---|---|---|
| Frames that receive a label | 3 / 7 (42.9 %) | 7 / 7 (100 %) | before [16 %, 75 %] |
| Frames with a **correct** label | 3 / 7 (42.9 %) | **6 / 7 (85.7 %)** | after [49 %, 97 %] |
| YOLO-accepted frames that were correct | 3 / 3 | 3 / 3 | — |
| Frames rescued by the fallback | — | 3 of 4 correct (the 4th has an ambiguous ground truth) | — |

Latency / resources (JSON `resources`, `cold_load`):

| | Value |
|---|---|
| YOLO fast path | 45–61 ms (warm) |
| Fallback end-to-end | 2.07–2.48 s (warm); 8.0 s on the very first call |
| Qwen cold load | 35.7 s (once, resident afterwards) |
| GPU memory with YOLO + Qwen3-VL-2B | 4,159 MB after load; 4,407 MB during runs; peak allocated 4,203 MB (of 6,144 MB) → ≈1.7 GB headroom |

### 3.3 Qualitative findings that belong in the paper (these are the honest, interesting ones)
1. **The VLM's own macros are not trustworthy; the DB is.** In 5 of 7 runs Qwen's macro JSON was flagged by the Atwater check
   (e.g. sweet potato 320 kcal/100 g vs ≈86 in the DB; apple carbs 24 g/100 g vs 14). Every final calorie value in the table
   came from the DB (`macro_source = db`). The VLM contributes the **identity**, the DB contributes the **numbers**. This is
   exactly the "canonical identity → knowledge layer" decomposition the reviewers asked us to demonstrate.
   Quantified against the DB value actually used (per-100 g kcal, from the JSON): apple 52 vs 52, banana 85 vs 89,
   watermelon 34 vs 30, tomato 45 vs 18, bell pepper 35 vs 20, idli 240 vs 140, sweet potato 320 vs 86 → absolute error
   0–272 %, **median 71 %, mean 84 %**. The Atwater guard flagged 5/7 but *passed* the tomato (2.5×) and pepper (1.75×)
   answers, so it is necessary but not sufficient. The DB is the reference here, not independent ground truth.
   Qwen's self-reported confidence is 95–97 % on nearly every image regardless of correctness: it is not calibrated and
   must not be quoted as accuracy.
2. **Confident YOLO is trusted and cheap.** 3/7 frames never touched the VLM (≈50 ms).
3. **Failure is explicit.** A paused MS2 yields `llm-timeout` / 0 kcal rather than a fabricated value.

---

## 4. Corrections needed in `docs/results.md` before it is quoted anywhere

`docs/results.md` is a useful draft but several statements are **not supported by the artifacts** and would be caught by reviewers:

| Claim in `results.md` | Problem | Fix |
|---|---|---|
| Pre-LLM = "closed vocabulary (80 COCO classes)", "Regional dish accuracy 0.0 %" | The submitted detector is the **123-class** `best.pt` (81.56 % mAP@50 on Indian dishes). The COCO `yolov8n.pt` appeared only through a misconfigured first benchmark run (§8B of that file admits this). | Use §3.1 numbers for "before". Never claim 0 % regional accuracy. |
| "42.9 % / 42.2 % / 38.5 %" YOLO confidences for apple / watermelon / esp32 | The JSON records `0.0` for these (confidence is only stored when status = identified). | Quote the JSON, or re-run and store `fallback_conf`. |
| "100 % Pipeline Success", "100 % accurate classification on all 4 rescued items" | 100 % is *a label was produced*. `esp32.jpg` has stated GT "Carrot/Apple/Tomato" but the pipeline output is bell pepper. | Report 6/7 correct, with CI, and fix/clarify the GT. |
| Query 2 "paneer butter masala … Qwen, 2,200 ms … 1,300× speed-up" | In the JSON both lookups are `source: db` (1.7–2.2 ms): the entry was already persisted. The 2,200 ms miss is not in the artifact. | Re-run on a cleaned DB or drop the speed-up claim. |
| "Unknowns dropped from ~65 % to <12 %" | Not derivable from the JSON; the DB audit behind it is unverified (§5). | Recompute with the SQL in `EVALUATION_PLAN.md` T1. |
| "1,880+ verified entries" | `docs/tasks/tasks4.md` item 4.0.4 (count `foods`) is still unchecked. | Run `SELECT count(*) FROM foods;`. |
| Peak VRAM 4,415 MB, cold load 30.4 s, 150 MB after YOLO | JSON: 4,407 MB observed / 4,203.5 MB allocated, 35.68 s, 0 MB after YOLO. | Use JSON values. |
| "Combined 100 % elimination of negative-weight records" credited to the hybrid | Caused by the 0.5 g delta guard, independent of the LLM. | Present as a separate fix (§5). |

Also note the benchmark JSON predates the latest uncommitted MS2 changes (name-only second pass, kcal recompute in
`ms2_llm/validation.py`, zero-row handling in `shared/food_lookup.py`) — re-run it after those are committed.

---

## 5. Database audit: pre vs post (needs re-verification)

`results.md` §3 lists `meal_logs` rows 1–82. I could not re-query the DB in this session (the query was blocked because it
printed credentials), so treat the rows as **claimed, not verified**. What the code does support:

* Pre-LLM failure modes (negative weights, 13 kg spikes, `Unknown`, lassi/kulfi) are plausible: no delta filter existed, and
  lassi/kulfi are the known over-predicted classes now suppressed.
* **Separate the two fixes** when writing the paper: (a) *weight sanity* (Δ ≥ 0.5 g) removes noise records; (b) *VLM fallback*
  removes Unknown / wrong-class records. Only (b) is an LLM contribution.

---

## 6. Where the architecture document and the code disagree (fix before the paper cites either)

| `MASTER_ARCHITECTURE.md` | Code / tasks |
|---|---|
| Fallback when YOLO < 80 % | `YOLO_CONF_THRESHOLD` default **0.50** |
| Qwen2.5-VL / Gemini Vision / LLaMA 3 | **Qwen3-VL-2B-Instruct**, transformers, bf16; no Gemini in MS2 |
| 10 s MS1→MS2 timeout | `MS2_TIMEOUT_S` = **30 s** |
| Pre-HitL suggestion → user confirms → retrain adapter | HitL **skipped**; Qwen label logged directly |
| Lookup: Postgres → OpenFoodFacts/USDA → LLM | Postgres (exact → alias → partial) → MS2 `/llm/lookup`; OFF/Gemini only in MS3 barcode flow |
| Barcode/OCR in MS1 | Moved to MS3 (Phase 5) |

---

## 7. On standby / not done — and why (state this plainly to reviewers)

| Item | State | Reason |
|---|---|---|
| Detector retraining / class consolidation (brinjal=eggplant, capsicum=bell pepper) | Not done | Deliberately left: the point is that the fallback + canonical lookup fixes the *output* without retraining. Consolidation remains a cheap follow-up. |
| Per-user adapters, HitL confirm, `retrain_yolo.py` | Paused | Phase 3 paused to build MS2 first; the VLM already supplies the label, so HitL is now a quality/personalisation feature, not a prerequisite. |
| Alternative detectors (YOLOv8s/m, RT-DETR) | Not done | Would require retraining; only the VLM-only baseline is cheap (provided by the new ablation script). |
| Barcode / OCR accuracy | Not evaluated | No labelled barcode/label set exists yet (EVALUATION_PLAN T4). |
| Meal-planner feasibility (Table 8) | Not re-run | Planner unchanged; feasibility, pool-size anomaly and baselines still open (T6). |
| Dataset leakage hash check | Not done | `CV_DATASET_AND_LEAKAGE.md`: three merged Roboflow sets, no de-duplication check on record (T7). |
| Commercial-app comparison | Not done | Survey task, not code. |
| MS4 agents | Out of scope of this report | Not exercised or evaluated here. |

---

## 8. Test status (verified this session)

* `pytest ms2_llm/tests ms1_cv/tests` → **38 passed** (no GPU / model / Postgres needed).
* `pytest tests/test_eval_fallback_ablation.py` → **6 passed** (matching, bootstrap CI helpers for the new ablation).
* GPU-dependent evaluation (`scripts/evaluate_post_llm.py`, `scripts/eval_fallback_ablation.py`) was **not run** by me: it needs
  MS2 up and takes GPU time; commands are in `EVALUATION_PLAN.md`.
