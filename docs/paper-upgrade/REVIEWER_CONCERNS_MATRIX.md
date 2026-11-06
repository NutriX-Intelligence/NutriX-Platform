# Reviewer Concerns → Status Matrix (Round 2, Submission 3455)

Status key: ✅ addressed with evidence · 🟡 partially / evidence exists but thin · ⏸ standby (reason given) · ❌ not addressed yet.
Evidence references point to [`BEFORE_AFTER_REPORT.md`](BEFORE_AFTER_REPORT.md) (§) and [`EVALUATION_PLAN.md`](EVALUATION_PLAN.md) (T#).

## Meta-review (AC muk5)

| Concern | Status | What we can say |
|---|---|---|
| No end-to-end image → meal plan evaluation | 🟡 | Image → YOLO/VLM → canonical name → DB macros → `meal_logs` → Redis is implemented and demonstrated on 7 images (§3.2); a labelled 229-image run is scripted (T2). Image → *meal plan* is still not evaluated (T6). |
| Barcode / OCR untested | ❌ | Moved to MS3, no quantitative results. T4. |
| Knowledge layer / normalization unmeasured | 🟡 | Mechanism now exists in code and is describable (below). Accuracy of name→canonical mapping is unmeasured (T5). |
| Normalization method not described | ✅ (writing task) | Describe `shared/food_lookup.py`: normalise → exact name → alias table → trusted-brand partial → (miss) LLM text lookup → Atwater guard → persist as "LLM Inferred". |
| Detection numbers hard to interpret (imbalance) | 🟡 | Unchanged. New ablation is stratified per class and reports Indian vs other subsets with bootstrap CIs (T2). |
| Meal-planning results weak | ❌ | Unchanged (T6). |

## Reviewer Qmr2 (3, Borderline Reject)

| # | Concern | Status | Response |
|---|---|---|---|
| 1 | Imbalanced val/test; Indian-subset gap uninterpretable | 🟡 | Detector numbers stay; state that the post-LLM claim is about pipeline output. Ablation reports per-subset accuracy (T2). Document the split criterion (merged Roboflow splits, no stratification — `CV_DATASET_AND_LEAKAGE.md`). |
| 2 | Barcode/OCR unevaluated | ❌ | T4 |
| 3 | Regional knowledge layer unvalidated | 🟡 | T5 (alias/canonical mapping accuracy + macro error vs ICMR) |
| 4 | Meal planning weak; feasibility drops 50→40 % with larger pools | ❌ | T6: report recipes available per pool, infeasibility causes, objective formulation |
| 5 | No quantitative comparison with other systems | 🟡 | VLM-only vs YOLO vs hybrid on the same images (T2) is a real, matched comparison. Comparison to NutrifyAI/commercial apps not done. |
| 6 | No variance / CIs | ✅ for new work | Ablation uses 2,000-sample bootstrap CIs and a paired CI for hybrid − YOLO. Old tables remain point estimates. |
| m1 | Split criterion unspecified | ✅ (writing) | Inherited from the three Roboflow sources, merged by `scripts/download_and_combine_datasets.py`; not re-stratified. |
| m2 | Recipes per pool vs 9,139 | ❌ | T6 |

## Reviewer GHiW (2, Weak Reject)

| # | Concern | Status | Response |
|---|---|---|---|
| 1 | No end-to-end eval; no ablation of knowledge layer / canonical representation | 🟡 | T2 (end-to-end identification) + T5 ablation: hybrid *without* alias/DB lookup (raw VLM name → macros) vs with it. |
| 2 | Why YOLOv8n? No alternative detector or pretrained-VLM comparison on the same resources | 🟡 | VLM-only baseline on identical images with latency and VRAM (T2, §3.2): fast path ≈50 ms / 0.15 GB vs ≈2.3 s / 4.2 GB. Argument: YOLO is the cheap gate, VLM the safety net. Other detectors ⏸ (needs retraining). |
| 3 | Coverage claims unsupported (37 zero-val classes; 217 knowledge concepts; 2 synonym groups) | 🟡 | The open-vocabulary fallback is precisely what removes dependence on the 123 classes: T2 splits "classes with 0 val images" out. Broader synonym evaluation: T5. |
| 4 | Planning: no baseline, no instance protocol, objective/infeasible handling unclear | ❌ | T6 |
| m1 | Fig. 3 font too small | ❌ | Regenerate (`Raj Docs/rajDocsFinal/generate_figure*.py`) |
| m2 | Abstract says 56,147 trained images; Table 2 lists 51,535 | ✅ (writing) | Train = 51,535; 56,147 is train+val+test. Fix the abstract. |

## Reviewer ybHw (1, Reject)

| # | Concern | Status | Response |
|---|---|---|---|
| 1 | Canonical normalization not described | ✅ (writing) | See meta-review row; code is `shared/food_lookup.py` + `ms2_llm/validation.py`. |
| 2 | 123/217 classes small; a handcrafted mapping would suffice | 🟡 | The VLM emits *free-form* names (open vocabulary), so a fixed handcrafted 123→217 table no longer covers the output space; the alias + partial lookup is needed. Back this with T5 (fraction of VLM names resolved by each lookup tier). |
| 3 | No end-to-end evaluation | 🟡 | As above. |
| 4 | Claims hard to follow; need UX description | 🟡 | Use the §3.2 table as the worked example (scale frame → label → macros → log). Add a figure of the Flow-1/Flow-2 sequence from `MASTER_ARCHITECTURE.md`, corrected per §6 of the report. |
| m1 | Concrete example image → plan | 🟡 | Example exists up to `meal_logs`/daily summary; plan step missing. |
| m2 | Commercial apps comparison | ❌ | Survey needed (SnapCalorie, MyFitnessPal, Cal AI, etc.) — do not cite without checking current features. |

## What we should NOT claim
* That the detector improved.
* "0 % regional accuracy" before / "100 % accuracy" after (n = 7, one wrong/ambiguous item, no CI).
* That VLM macros are accurate — they are mostly flagged; the DB supplies the numbers.
* That negative-weight elimination is an LLM effect.
* HitL / per-user adaptation results — implemented but paused.
