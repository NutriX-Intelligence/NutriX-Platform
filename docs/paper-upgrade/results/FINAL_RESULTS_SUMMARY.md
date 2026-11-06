# NutriX — Results Summary: Before vs After the VLM Fallback

Purpose: a self-contained evidence summary for rewriting the paper after the WACV Round 2 rejection.
All figures come from the project's own artifacts (sources named per table). Nothing here is estimated.

## 1. Headline

The YOLOv8n detector was **not retrained or changed**. The improvement is at the **system output**: frames the detector cannot
identify are now resolved by a local vision-language model (Qwen3-VL-2B), mapped to a canonical food through a shared
alias/nutrition lookup, and given macros from the nutrition database. Before, those frames were logged as "Unknown" or as a
wrong class.

## 2. Before vs After (system behaviour)

| Aspect | Before (submitted system) | After (current system) |
|---|---|---|
| Detector | YOLOv8n, 123 classes, 58.78 % mAP@50 (81.56 % on 31 Indian classes) | **Same checkpoint** |
| Low-confidence or unrecognised frame | Logged as "Unknown" with a placeholder value | Sent to Qwen3-VL-2B; label recovered |
| Foods outside the 123 classes | Impossible (closed vocabulary) | Open-vocabulary naming, then canonical lookup |
| Known over-predictions (lassi, kulfi) | Logged as predicted | Suppressed and re-identified by the VLM |
| Label to nutrition | Hard-coded sample values / 100 kcal default | Exact name, then alias, then trusted partial match in the nutrition DB; DB miss triggers an LLM lookup that is saved for next time |
| Implausible VLM macros | n/a | Rejected by range checks and an energy-consistency (Atwater) check; flagged values never stored |
| VLM service down | n/a | Logged as `llm-timeout`, 0 kcal, no crash |
| Traceability | One generic source tag | Each log tagged `esp32_yolo`, `esp32_qwen_vlm` or `llm-timeout` |
| Scale noise (negative or huge weights) | Logged | Ignored below a 0.5 g weight change (separate fix, not from the LLM) |

## 3. Benchmark on real images
Source: `inference_outputs/post_llm_benchmark_results.json` (RTX 3050 6 GB laptop GPU, threshold 0.5, run 2026-10-27).

| Image (weight) | YOLO result | Route | Final label | kcal (source) | End-to-end |
|---|---|---|---|---|---|
| Banana (120 g) | banana 78.3 % | YOLO fast path | Banana ✔ | 106.8 (DB) | 66 ms |
| Tomato (95 g) | tomato 83.1 % | YOLO fast path | Tomato ✔ | 17.1 (DB) | 80 ms |
| Idli (150 g) | idli 52.8 % | YOLO fast path | Idli ✔ | 210.0 (DB) | 50 ms |
| Apple (180 g) | not identified | **VLM rescue** | Apple ✔ | 93.6 (DB) | 8.0 s (first call, warm-up) |
| Watermelon (350 g) | wrongly guessed `greenchutney` | **VLM rescue** | Watermelon ✔ | 105.0 (DB) | 2.5 s |
| Sweet potato (210 g) | no detection | **VLM rescue** | Sweet Potato ✔ | 180.6 (DB) | 2.4 s |
| Scale-plate frame | not identified | VLM | Bell Pepper (stated ground truth was "carrot/apple/tomato", so counted wrong) | 30.0 (DB) | 2.1 s |

| Metric (7 images) | Before: YOLO only | After: YOLO + VLM |
|---|---|---|
| Frames that receive a label | 3 / 7 (43 %) | 7 / 7 (100 %) |
| Frames with a correct label | 3 / 7 (43 %) | **6 / 7 (86 %)** |
| Frames YOLO got wrong or missed that the VLM got right | — | 3 of 4 |

Caveat to state in the paper: n = 7, so the 95 % intervals are wide (before about 16–75 %, after about 49–97 %). This
is a demonstration, not a statistical result.

## 4. Cost and resources
Source: same JSON.

| | Value |
|---|---|
| YOLO fast path | 45–61 ms |
| VLM fallback, end to end | about 2.1–2.5 s |
| VLM cold load (once, then stays loaded) | 35.7 s |
| GPU memory, YOLO + Qwen3-VL-2B resident | about 4.4 GB of 6.1 GB (about 1.7 GB free) |
| Runs entirely on a consumer laptop GPU | yes, no cloud calls in this path |

Design consequence: confident detections stay fast (about 50 ms); only uncertain frames pay about 2 s.

## 5. Findings worth highlighting
1. **Identity from the VLM, numbers from the database.** In 5 of 7 runs the VLM's own macro estimate failed the consistency
   check (for example sweet potato 320 kcal/100 g against about 86 in the DB). All reported calories came from the nutrition DB.
   This is the case for the separate "canonical identity + knowledge layer" design.
2. **Open-vocabulary naming exposes label noise and composite dishes.** On a small labelled-test smoke run (10 images), the VLM
   called an image labelled "apple" a **plum** (on visual inspection the photo appears to show plums), and called a bowl labelled
   "almond" **oatmeal** (almonds were only a topping). It names the visible component of dishes
   (aloo-gobi curry → "cauliflower"), which is exactly why a normalisation step to canonical names is required.
3. **Failure is explicit and auditable** rather than silent.

## 6. Limitations to state honestly
* Detector accuracy figures are unchanged, and the validation imbalance (median 3 images per class; 37 classes with none)
  still stands.
* The before/after comparison is on 7 images, and one ground truth is ambiguous.
* A larger labelled comparison (YOLO vs VLM-only vs hybrid) is scripted (`scripts/eval_fallback_ablation.py`) but not yet
  validated: the public test labels contain errors (checked: 2 of 2 disputed images), and the script currently scores the VLM's raw
  name without the alias lookup, so it understates the hybrid.
* Not evaluated: barcode / OCR accuracy, the knowledge layer's mapping accuracy, meal-planner changes (planner unchanged), image-to-meal-plan.
* On standby, by design: per-user adapters and human-in-the-loop retraining (implemented, paused; the VLM supplies the label so
  they are no longer a prerequisite); alternative detectors (would need retraining).

## 7. Tests that pass today
* 38 unit tests for the CV and LLM services (no GPU needed); 6 for the evaluation helpers.
