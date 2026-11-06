# Evaluation Plan, Evidence Ledger and Corrections

Companion to [BEFORE_AFTER_REPORT.md](BEFORE_AFTER_REPORT.md) and [REVIEWER_CONCERNS_MATRIX.md](REVIEWER_CONCERNS_MATRIX.md).

> **Cross-reference key.** The report and matrix cite this plan as **T1–T7**. They map to: **T1** = §3 database audit SQL · **T2** = §2.2 Experiment A (labelled ablation) · **T3** = §2.3 Experiment B (rerun the 7-image benchmark; the report does not define T3, this is the closest match) · **T4** = barcode / OCR (§4, rows 6–7) · **T5** = §2.6 Experiment E (knowledge-layer / macro-source ablation) · **T6** = meal planning (§4, row 9) · **T7** = §2.4 Experiment C (cross-split duplicate check). §2.5 (Experiment D, real scale frames in `dataset/pending/`) has no T-number.
Per `AI_CONTEXT.md`, commands that start services, load the GPU model or touch the database are **yours to run**. Only CPU unit tests were run while preparing these documents.

---

## 1. Corrections needed in `docs/results.md`

`docs/results.md` (committed with Phase 4) is a useful draft, but checking it against `inference_outputs/post_llm_benchmark_results.json` and the code shows claims that should not go into a paper as written.

| # | `results.md` says | What the evidence shows | Fix |
|---|---|---|---|
| 1 | Pre-LLM = YOLOv8n with **80 COCO classes**; "Regional Dish Accuracy 0.0 % (Idli, Paneer Tikka, Dosa impossible)" | The pre-LLM system in the paper is the 123-class `best.pt` (81.56 % mAP@50 on 31 Indian classes; `idli` AP50 = 0.913). The COCO model was an accidental first benchmark run, as `results.md` §8B itself admits | Replace the "Pre-LLM" column with the 123-class model. Drop the 0 % claim |
| 2 | Post-LLM "**95–97 % Top-1 accuracy**" on regional dishes | Those numbers are Qwen's **self-reported confidence** (95.0 on nearly every image). Not accuracy; n is 7 | Remove. Report accuracy only from the labelled ablation |
| 3 | "100 % pipeline success, 7/7" | `esp32.jpg` ground truth is "Carrot/Apple/Tomato (Scale Plate)"; both models said "bell pepper". At best 6/7 with one ambiguous | Relabel the image or exclude it; report 6/6 or 6/7 |
| 4 | "Δ ≥ 0.5 g guard … 100 % elimination of negative weights" is a Post-LLM change | `if delta_weight < 0.5` is in `ms1_cv/cv_engine.py` since the initial commit (2026-05-26). Phase 4 added the `ignored` path in `ms1_cv/main.py` so such events are not logged | Attribute to ingestion hardening in Phase 4, not to the LLM |
| 5 | Pre-LLM fallback is "a flat 40.1 kcal" | In the quoted rows calories == weight (40.1 g → 40.1 kcal, 1906.2 → 1906.2): it is a **100 kcal/100 g default** | Say so |
| 6 | YOLO confidences 42.9 % (apple), 42.2 % (watermelon), 38.5 % (esp32) | The JSON records `0.0` for rejected frames, so these values cannot be traced to the committed artifact | Re-run and store `fallback_conf`, or drop the numbers |
| 7 | Cold start "~30.4 s"; post-YOLO "150 MB"; peak "4,415 MB"; baseline RAM 1,378.9 MB | JSON: Qwen load **35.68 s**; post-YOLO **0.0 MB** (YOLO loads lazily on first inference); peak allocated **4,203.5 MB**, per-image `nvidia-smi` **4,407 MB**; baseline RAM 1,363.3 MB | Use the JSON values or re-measure |
| 8 | YOLO latency for apple 2,693.9 ms listed among fast-path figures | That includes lazy model load. Steady-state YOLO is 10–79 ms | Exclude the first call |
| 9 | Text lookup demo: "paneer butter masala" first query = Qwen, 2,200 ms, then "1,300× speedup" | JSON: all three lookups are `source: db` (2.8 / 2.2 / 1.7 ms). The miss path and its latency were not captured (the row had already been persisted) | Delete the food from `foods` and `food_aliases` (LLM Inferred), re-run, store the timing |
| 10 | "Unknowns fell from ~65 % to < 12 %" | 12 % = 1 of 8 post-LLM rows, and that row was a deliberate MS2-down test. The 65 % was not recomputed here | Run the SQL in §3; report counts, not percentages, with n |
| 11 | "1,880+ verified database entries" | `tasks4.md` item 4.0.4 (check the real food count) is still unticked | Run the SQL in §3 |
| 12 | Pre-LLM "identified 3/7 = 42.8 %" | Valid only at the **0.50** threshold, which was introduced together with the VLM (previous value 0.30). At 0.30 some frames are *wrongly identified* instead of `Unknown` (watermelon → greenchutney) | State the threshold; show both |

The benchmark JSON also predates uncommitted edits in `ms2_llm/validation.py`, `ms2_llm/tests/test_validation.py` and `shared/food_lookup.py` (`git status`), so rerun before quoting any VLM number.

---

## 2. Tests: what has run and what to run

### 2.1 Run while preparing these documents (CPU, no GPU/DB writes)
| Suite | Result |
|---|---|
| `ms2_llm/tests` | 34 passed |
| `ms1_cv/tests` + `gateway/tests` | 50 passed |
| `ms3_user/tests` (run alone; it refuses to run next to Postgres-backed suites) | 354 passed, 2 skipped |
| `tests/test_eval_fallback_ablation.py` (new: matcher, bootstrap, sampler helpers) | 6 passed |
| `ms4_agents/tests` | health only (the service is a stub) |

These show the code paths are regression-tested; they are **not** accuracy evidence.

### 2.2 Experiment A: labelled ablation (the one that matters most)
**Purpose:** replace the 7-image anecdote with a measured comparison on the same images: YOLO raw, YOLO + abstain (pre-LLM), VLM only (matched pretrained-VLM baseline for GHiW), and the production hybrid, with 95 % bootstrap CIs and an Indian / other split.

```bash
# Terminal 1: MS2 must be up and loaded (do NOT start a second Qwen: 6 GB GPU)
cd /home/harsh/Nutrix && source .venv/bin/activate
PYTHONPATH=. uvicorn ms2_llm.main:app --port 8003        # no --reload

# Terminal 2: smoke test, then the full run (~229 images, roughly 10-15 min)
cd /home/harsh/Nutrix && source .venv/bin/activate
PYTHONPATH=. python scripts/eval_fallback_ablation.py --limit 10
PYTHONPATH=. python scripts/eval_fallback_ablation.py --per-class 3 --seed 0
```
Outputs go to `docs/paper-upgrade/results/`: `ablation_cache_*.jsonl` (per image) and `ablation_summary_*.json`. Paste the JSON numbers into the table at the end of the report.

Things to know before you trust the output:
- **Image set:** single-item images only (one distinct class in the label file), up to 3 per class from the **test** split. Classes with no single-item test image are skipped (92 of 123 classes are covered, 89 images from the 31 Indian classes by a dry check).
- **Match rule:** exact after normalization, plural and space-less equality, plus a small synonym list (brinjal/eggplant, capsicum/bell pepper, …). Word-subset matches are rejected so "potato" never matches "sweet potato". The list is applied identically to all systems. Report it in the paper as an evaluation convention.
- **Cache vs threshold:** the cache stores which frames fell back **at the threshold used in that run**. To test another threshold (e.g. `--threshold 0.75`, suggested in `results.md`) delete the cache file or use a different seed. A cached run will silently reuse the old decisions.
- **Bias:** the test split comes from the same Roboflow merge as training and no cross-split de-duplication has been run, so YOLO is likely **overstated** and the fallback's benefit **understated**. Read the result as a conservative bound for the fallback. Run Experiment C to bound this.
- **MS2 errors** (non-200) are scored wrong and not retried. If many occur, the results are not comparable; check MS2's log first.

### 2.3 Experiment B: rerun the 7-image benchmark on current code
`evaluate_post_llm.py` loads its **own** Qwen, so stop MS2 first (two copies do not fit in 6 GB).
```bash
cd /home/harsh/Nutrix && source .venv/bin/activate
PYTHONPATH=. python scripts/reset_test_session.py
PYTHONPATH=. python scripts/evaluate_post_llm.py
```
Before running: fix the `esp32.jpg` ground truth in the script, and make the script save the YOLO fallback confidence for rejected frames (item 6 above). To capture the lookup miss path (item 9), first remove the previously persisted `paneer butter masala` row.

### 2.4 Experiment C: cross-split duplicate check (CPU)
Hash (e.g. perceptual hash) the train / valid / test images and count near-duplicates across splits. No such check exists (`CV_DATASET_AND_LEAKAGE.md`: "NOT FOUND"). The result bounds the optimism in Experiment A and answers Qmr2's split-criterion question. If leakage is found, restrict Experiment A to images with no near-duplicate in train.

### 2.5 Experiment D: real scale frames
`dataset/pending/` contains **128** real low-confidence frames from the ESP32 scale (`dataset/live_captures/` has only 2 files). They are unlabelled; labelling 128 single-item images by hand takes about 30 minutes, and it is the only test set that matches deployment. Feed them through the same ablation script (point `DATA`/sampler at a folder of `image + label` pairs, or write the labels to a CSV and add a loader). This is the most convincing evidence for an Applications track and the one most likely to show the fallback's real value.

### 2.6 Experiment E: macro source ablation
For the foods in Experiment A that exist in the DB, compare per-100 g kcal and macros from (i) DB, (ii) Qwen as returned, (iii) Qwen after the Atwater recompute, against ICMR/USDA values. The 7-image benchmark already shows a 71 % median kcal error for raw Qwen macros; this experiment makes that a table with a sample size. It supports the DB-first design and answers GHiW's "ablation of the knowledge layer".

---

## 3. Database audit (read-only; run it yourself)

The previous attempt to run this from the assistant was correctly blocked because the command printed database credentials. Run it from a terminal where you are logged in; the credentials stay inside the container:
```bash
docker exec -it nutrix-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```
```sql
-- 1. Operational failure modes by source
SELECT source,
       count(*)                                           AS rows,
       count(*) FILTER (WHERE weight_g <= 0)              AS nonpositive_weight,
       count(*) FILTER (WHERE weight_g > 3000)            AS implausible_weight,
       count(*) FILTER (WHERE lower(food_name)='unknown') AS unknown,
       count(*) FILTER (WHERE abs(calories - weight_g) < 0.05) AS kcal_equals_weight,  -- the 100 kcal/100 g default
       min(log_date) AS first, max(log_date) AS last
FROM meal_logs GROUP BY source ORDER BY first;

-- 2. Size and provenance of the knowledge layer
SELECT brand, count(*) FROM foods GROUP BY brand ORDER BY 2 DESC;
SELECT count(*) AS aliases FROM food_aliases;

-- 3. How much of the catalogue the VLM has added
SELECT count(*) AS llm_inferred FROM foods WHERE brand = 'LLM Inferred';
```
Report counts with n, split by date range (before/after 2026-10-24), and note that these are uncontrolled test sessions, not a benchmark.

---

## 4. Remaining experiments, ranked

| Priority | Experiment | Effort | Closes |
|---|---|---|---|
| 1 | A: labelled ablation | 15 min compute | End-to-end, VLM baseline, CIs |
| 2 | B: rerun benchmark, fix ground truth | 10 min | Stale / untraceable numbers |
| 3 | C: cross-split dedup | 1–2 h | Split criterion, leakage |
| 4 | D: label and test `dataset/pending/` | ~1 h | Real-world evidence |
| 5 | E: macro-source ablation | 2–3 h | Knowledge-layer ablation |
| 6 | Barcode: 50 barcodes, OFF vs search vs Gemini hit rate | 2 h | Barcode claim |
| 7 | OCR: 30 label photos, field-level accuracy | 3 h | OCR claim |
| 8 | Threshold sweep (0.3 … 0.9) via separate runs | 1 h | Operating point |
| 9 | Meal-plan: explain pool-size anomaly, report recipes per pool | unknown | Qmr2 W4 / GHiW W4 |
| 10 | Alternative detectors | days | GHiW W2 (optional) |
