Based on the comprehensive technical audits conducted across your entire repository ([docs/rajDocs/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs/), [docs/rajDocs2/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs2/), and [docs/rajDocs3/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs3/)), here is a strategic roadmap of **5 key additions and paper refinements** that will significantly increase your paper's acceptance chances at **WACV 2027 (Applications Track)**.

---

### 1. Frame the Paper as a "Dual-Layer System" (The Core Story)
> [!IMPORTANT]
> **Reviewer Risk:** If reviewers get the impression that you are claiming a 217-class *computer vision detector*, the paper will be rejected immediately because no images exist for 187 of those regional classes.

**The Winning Submission Framing:**  
Title the paper around a **Dual-Layer Architecture**:
* **Layer 1 (Visual Perception Engine):** A 123-class YOLOv8 model trained on 56,147 images with $360^\circ$ rotational invariance and Human-in-the-Loop active adaptation.
* **Layer 2 (Knowledge & Optimization Engine):** A 217-class regional food/recipe taxonomy integrated with ICMR/NIN/USDA databases, an 80+ term culinary synonym index, and a Google OR-Tools SCIP Mixed-Integer Linear Programming (MILP) solver.

---

### 2. Run 3 Quick High-Impact Experiments (Missing Link for Top Scores)

WACV Applications Track reviewers look for ablation studies and quantitative latency metrics. The following 3 experiments can be executed using your existing code and dataset:

#### A. Semantic Label Consolidation Ablation (P0 — High Impact, Easy Execution)
* **Problem:** Currently, `data.yaml` has duplicate visual classes: `brinjal` (ID 22) vs `eggplant` (ID 46) and `capsicum` (ID 12) vs `bell pepper` (ID 28). This artificially lowers your reported mAP (58.78%).
* **Action:** Merge these duplicate class pairs in `data.yaml` and re-run validation ([scripts/get_class_accuracies.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/get_class_accuracies.py)).
* **Impact:** Shows clean dataset engineering, removes label noise, and increases reported mAP@50 score.

#### B. Rotational & Overhead Augmentation Ablation (P0 — Scientific Rigor)
* **Problem:** Reviewers want to know *why* your model works better on top-down food images.
* **Action:** Train a baseline YOLOv8 *without* rotational invariance (`degrees: 0.0`) and compare its mAP against your current model (`degrees: 180.0`, `perspective: 0.0`).
* **Impact:** Provides a clear ablation study proving that $360^\circ$ rotational invariance is critical for overhead scale plate detection.

#### C. End-to-End Latency & Resource Table (P0 — System Performance)
* **Problem:** Applications Track papers require system runtime metrics.
* **Action:** Measure and report:
  1. Inference latency (ms per frame) on GPU, CPU, and ESP32-CAM HTTP GET link.
  2. OR-Tools MILP solve times (in ms) for generating daily meal plans across candidate pool sizes ($N = 50, 100, 300$).
* **Impact:** Completes the system evaluation section required by reviewers.

---

### 3. Report End-to-End Visual Nutrition Prediction Error (MAE)
Instead of treating computer vision and nutrition calculation as isolated components, add a combined metric:
* Take test plate images, pass visual detection outputs into `nutrition_engine.py` / `INDB.xlsx`, and compute **Mean Absolute Error (MAE in kcal and grams)** between visually estimated macros vs. ground-truth plate nutrition.
* This directly connects *Computer Vision $\to$ Food Understanding $\to$ Nutrition Calculation*, perfectly matching WACV's Food Science & Nutrition application scope.

---

### 4. Address Dataset Quality & Leakage Head-On
Reviewers heavily scrutinize custom web-scraped datasets. In your paper:
* Explicitly document the 3 Roboflow source datasets (`combined-vegetables-fruits`, `food-ingredients-dataset`, `indianfoodnet`) merged by `download_and_combine_datasets.py`.
* Explicitly state how train/val/test splits were constructed (51,535 train / 2,484 valid / 2,128 test).
* Mention that class consolidation was applied to prevent duplicate label confusion.

---

### 5. Leverage Your Existing Rich Visual Artifacts
You already have publication-ready figures in your repository:
* **Figure 1 (System Pipeline):** Architectural diagram from [docs/ArchitectureDiagrams.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/ArchitectureDiagrams.md).
* **Figure 2 (Training Curves):** 8-panel loss & mAP progression plot from [runs/nutrix_custom_model-2/results.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.png).
* **Figure 3 (Confusion Matrix):** 123-class normalized matrix from [runs/nutrix_custom_model-2/confusion_matrix_normalized.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/confusion_matrix_normalized.png).
* **Figure 4 (Qualitative Detections):** Bounding box predictions from [runs/nutrix_custom_model-2/val_batch0_pred.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/val_batch0_pred.jpg).

---

### Summary Checklist for Paper Preparation

| Task | Priority | Purpose / Reviewer Impact |
| :--- | :--- | :--- |
| **Dual-Layer Framing** | **P0** | Prevents rejection due to missing 217-class regional images. |
| **Semantic Class Consolidation** | **P0** | Removes class ID noise (`brinjal`/`eggplant`) and boosts mAP. |
| **Rotational Augmentation Ablation** | **P0** | Proves the necessity of $360^\circ$ plate rotational invariance. |
| **Latency & Solve Time Table** | **P0** | Fulfills WACV Applications Track system benchmark requirements. |
| **Visual Nutrition MAE Metric** | **P1** | Demonstrates real-world food science utility. |