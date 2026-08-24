# WACV 2027 Experiment Plan: Core-to-Regional Computer Vision Evaluation

**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  
**Scope:** Realistic WACV 2027 Experimental Roadmap Using ONLY the Existing Core 123-Class Image Dataset (56,147 images).

> [!IMPORTANT]
> **Experimental Constraint:** The separate Regional project contains 217 food classes but HAS NO IMAGE DATASET and NO TRAINED CV MODEL. All experiments proposed below rely strictly on the 56,147 images already available in the Core platform repository.

---

## 1. Prioritized Experimental Roadmap

### P0 — Necessary for WACV Submission (Core Technical & Regional Baseline)

1. **Experiment P0-1: 123-Class Global Object Detection Baseline**
   * **Objective:** Establish formal benchmark results across all 123 Core visual classes.
   * **Dataset:** `dataset/custom_training_data/` (51,535 train, 2,484 valid, 2,128 test).
   * **Metrics to Report:** Precision, Recall, mAP@50 (58.78%), mAP@50-95 (40.56%), Box Loss, Class Loss, DFL Loss across 30 epochs.
   * **Evidence Source:** Existing run [runs/nutrix_custom_model-2/results.csv](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.csv).

2. **Experiment P0-2: 30-Class Indian Regional Visual Subset Benchmark**
   * **Objective:** Isolate detection accuracy on prepared Indian regional dishes vs. global produce.
   * **Subset Selection:** 30 prepared regional dish/beverage classes (`aloogobi`, `aloomasala`, `bhatura`, `bhindimasala`, `biryani`, `chole`, `coconutchutney`, `dal`, `dosa`, `dumaloo`, `fishcurry`, `ghevar`, `greenchutney`, `gulabjamun`, `idli`, `jalebi`, `kebab`, `kheer`, `kulfi`, `lassi`, `muttoncurry`, `onionpakoda`, `palakpaneer`, `poha`, `rahar ko daal`, `rajmacurry`, `rasmalai`, `samosa`, `shahipaneer`, `whiterice`).
   * **Expected Outcome:** Measure whether complex mixed-ingredient Indian dishes (curries/biryani) exhibit lower mAP than solid produce (fruit/veg).

3. **Experiment P0-3: Semantic Concept Consolidation & Label De-duplication Ablation**
   * **Objective:** Quantify evaluation penalty caused by duplicate concept classes in `data.yaml`.
   * **Consolidation Mapping:**
     * Merge `brinjal` (ID 22) + `eggplant` (ID 46) $\rightarrow$ `eggplant_consolidated`
     * Merge `capsicum` (ID 12) + `bell pepper` (ID 28) $\rightarrow$ `bell_pepper_consolidated`
   * **Execution:** Update `data.yaml` label mappings and re-evaluate validation mAP@50 to measure true visual accuracy without label noise.

---

### P1 — Strongly Recommended (Cuisine & Augmentation Deep Dives)

4. **Experiment P1-1: 5-Cuisine Hierarchy Classification Evaluation**
   * **Objective:** Evaluate visual detection performance grouped into 5 regional cuisine buckets supported by the Core dataset.
   * **Cuisine Groups:**
     * **Punjabi (10 classes):** `chole`, `bhatura`, `palakpaneer`, `rajmacurry`, `shahipaneer`, `lassi`, `kulfi`, `aloogobi`, `bhindimasala`, `kebab`.
     * **South Indian (5 classes):** `dosa`, `idli`, `coconutchutney`, `biryani`, `whiterice`.
     * **Maharashtrian / Gujarati (4 classes):** `poha`, `onionpakoda`, `samosa`, `jalebi`.
     * **Rajasthani (2 classes):** `ghevar`, `jalebi`.
     * **Bengali (3 classes):** `rasmalai`, `fishcurry`, `dumaloo`.
   * **Metrics:** Macro-averaged Precision, Recall, and mAP per cuisine group.

5. **Experiment P1-2: Top-Down Rotational Augmentation Ablation Study**
   * **Objective:** Prove the scientific value of $360^\circ$ rotational invariance (`degrees: 180.0`) and zero perspective distortion (`perspective: 0.0`) for fixed overhead camera scale settings.
   * **Comparative Groups:**
     * *Baseline:* YOLOv8 default augmentations (`degrees: 0.0`, `perspective: 0.0005`).
     * *NutriX Settings:* Top-down augmentations (`degrees: 180.0`, `perspective: 0.0`, `flipud: 0.5`).
   * **Hypothesis:** Overhead plate camera accuracy improves significantly under full rotational invariance.

6. **Experiment P1-3: Per-Class Visual Ambiguity & Confusion Analysis**
   * **Objective:** Categorize confusion matrix errors (`confusion_matrix.png`) into:
     1. Raw vs. Prepared dish confusion (e.g. `chickpeas` vs `chole`, `potato` vs `aloomasala`).
     2. Visually similar liquid/curry confusion (`dal` vs `rajmacurry` vs `muttoncurry`).

---

### P2 — Optional (End-to-End System & Edge Performance)

7. **Experiment P2-1: End-to-End Visual Nutrition Prediction Error**
   * **Objective:** Pipeline detection outputs directly into `nutrition_engine.py` and measure calorie/macronutrient prediction error (MAE in grams/kcal) against ground-truth recipe nutrition from `recipes.xlsx`.

8. **Experiment P2-2: Hardware Edge Latency Benchmarking**
   * **Objective:** Benchmark frame capture and inference latency across hardware setups (GPU vs CPU vs ESP32-CAM HTTP link).
