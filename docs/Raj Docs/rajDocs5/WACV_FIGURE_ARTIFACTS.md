# WACV 2027 — Research Figure Artifacts & Reproducibility Report

**Target Conference:** IEEE/CVF Winter Conference on Applications of Computer Vision (WACV 2027)  
**Paper Target Track:** Applications (Food Science & Nutrition)  
**System Evaluated:** NutriX Platform 123-Class Food Perception Model  
**Checkpoint Evaluated:** `runs/nutrix_custom_model-2/weights/best.pt`  
**Dataset Path:** `dataset/custom_training_data/` (56,147 images: 51,535 train, 2,484 val, 2,128 test)  

---

## 1. FIGURE 2: QUANTITATIVE BENCHMARK EVALUATION (2-PANEL)

**Rendered Figure Files:**
* High-Resolution Raster (300 DPI): [docs/rajDocs4/wacv_figures/figure2_quantitative.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs4/wacv_figures/figure2_quantitative.png)
* Vector PDF (Publication Quality): [docs/rajDocs4/wacv_figures/figure2_quantitative.pdf](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs4/wacv_figures/figure2_quantitative.pdf)

```
+----------------------------------------------------+----------------------------------------------------+
| (a) Validation Class Distribution                  | (b) Rotational Invariance Robustness (N=200)       |
| Top-25 Represented Classes + Category Brackets     | Metrics at 0°, 90°, 180°, 270° (<1.2% Variance)    |
+----------------------------------------------------+----------------------------------------------------+
```

---

### Panel (a): Validation Class Distribution (123-Class Detector)

* **Generating Script:** [docs/rajDocs4/fast_distribution.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs4/fast_distribution.py) (and [analyze_distribution.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs4/analyze_distribution.py))
* **Primary Source CSV:** [docs/rajDocs4/class_distribution.csv](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs4/class_distribution.csv)
* **Summary Statistics File:** [docs/rajDocs4/class_distribution_statistics.csv](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs4/class_distribution_statistics.csv)
* **Distribution Summary Log:** [docs/rajDocs4/validation_brackets_summary.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs4/validation_brackets_summary.txt)

#### Representation Brackets Breakdown (123 Total Classes)
* **> 20 Validation Images (51 classes):** Well-represented food categories (e.g., `avocado`, `eggplant`, `beans`, `broccoli`, `chole`, `biryani`, `dal`, `dosa`, `palakpaneer`, `jalebi`, `onionpakoda`, `poha`).
* **5–20 Validation Images (5 classes):** Moderately represented (`egg`, `gulabjamun`, `kebab`, `pumpkin -farsi-`, `samosa`).
* **< 5 Validation Images (30 classes):** Rare/tail ingredients (e.g., `bitter gourd`, `black beans`, `brinjal`, `buff meat`, `capsicum`, `chicken`, `chickpeas`, `green lentils`, `papaya`, `red beans`).
* **0 Validation Images (37 classes):** Unrepresented in validation split (e.g., `apple`, `banana`, `bread`, `cherry`, `grape`, `orange`, `strawberry`, `watermelon`).

#### Top 25 Represented Classes in Validation Split

| Rank | Class ID | Class Name | Validation Images | Validation Annotations (Instances) | Train Images | Test Images | Total Images |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | 7 | `avocado` | **164** | 581 | 5,014 | 141 | 5,319 |
| 2 | 46 | `eggplant` | **155** | 423 | 4,008 | 134 | 4,297 |
| 3 | 10 | `beans` | **148** | 261 | 3,922 | 129 | 4,199 |
| 4 | 24 | `broccoli` | **100** | 198 | 2,752 | 96 | 2,948 |
| 5 | 38 | `chole` | **70** | 72 | 1,421 | 68 | 1,559 |
| 6 | 83 | `onion` | **65** | 205 | 1,643 | 61 | 1,769 |
| 7 | 97 | `radish` | **65** | 215 | 1,589 | 59 | 1,713 |
| 8 | 113 | `tomato` | **62** | 246 | 1,612 | 58 | 1,732 |
| 9 | 61 | `greenchutney` | **61** | 66 | 1,280 | 54 | 1,395 |
| 10 | 29 | `carrot` | **59** | 242 | 1,489 | 52 | 1,600 |
| 11 | 120 | `whiterice` | **56** | 59 | 1,198 | 51 | 1,305 |
| 12 | 94 | `potato` | **55** | 244 | 1,388 | 49 | 1,492 |
| 13 | 12 | `bell pepper` | **54** | 229 | 1,356 | 48 | 1,458 |
| 14 | 39 | `coconutchutney` | **53** | 57 | 1,120 | 47 | 1,220 |
| 15 | 51 | `garlic` | **51** | 199 | 1,294 | 45 | 1,390 |
| 16 | 41 | `cucumber` | **48** | 147 | 1,180 | 43 | 1,271 |
| 17 | 86 | `palakpaneer` | **45** | 45 | 988 | 42 | 1,075 |
| 18 | 13 | `bhatura` | **44** | 87 | 962 | 40 | 1,046 |
| 19 | 42 | `dal` | **44** | 45 | 954 | 39 | 1,037 |
| 20 | 14 | `bhindimasala` | **43** | 45 | 920 | 38 | 1,001 |
| 21 | 44 | `dumaloo` | **43** | 44 | 915 | 38 | 996 |
| 22 | 15 | `biryani` | **42** | 45 | 895 | 37 | 974 |
| 23 | 50 | `fishcurry` | **41** | 41 | 870 | 36 | 947 |
| 24 | 82 | `muttoncurry` | **40** | 40 | 850 | 35 | 925 |
| 25 | 84 | `onionpakoda` | **40** | 40 | 845 | 35 | 920 |

---

### Panel (b): Rotational Invariance Robustness Evaluation

* **Generating Script:** [docs/rajDocs4/eval_rotational_robustness.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs4/eval_rotational_robustness.py)
* **Primary Source CSV:** [docs/rajDocs4/rotational_robustness_results.csv](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs4/rotational_robustness_results.csv)
* **Sample Size:** $N = 200$ reproducible non-empty validation plate images.
* **Evaluation Condition:** Geometric rotation applied to raw pixel matrices with corresponding ground-truth bounding box transformation:
  * $0^\circ$: $(x, y, w, h)$
  * $90^\circ$: $(1 - y, x, h, w)$
  * $180^\circ$: $(1 - x, 1 - y, w, h)$
  * $270^\circ$: $(y, 1 - x, h, w)$

#### Empirical Numerical Results Across Rotational Angles

| Rotation Angle | Evaluated Images | Precision (P) | Recall (R) | mAP@50 | mAP@50-95 | Absolute mAP@50 Variance |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$0^\circ$ (Baseline Overhead)** | 200 | **0.8710** | **0.8432** | **0.8924** | **0.5983** | **Baseline (0.0%)** |
| **$90^\circ$ (Clockwise)** | 200 | **0.8604** | **0.8343** | **0.8911** | **0.5968** | **$-0.13\%$** |
| **$180^\circ$ (Inverted)** | 200 | **0.8808** | **0.8268** | **0.8875** | **0.5928** | **$-0.49\%$** |
| **$270^\circ$ (Counter-Clockwise)** | 200 | **0.8706** | **0.8157** | **0.8804** | **0.5952** | **$-1.20\%$** |

> **Scientific Conclusion:** The maximum variance in mAP@50 across full $360^\circ$ spatial rotation is strictly $\le 1.20\%$, providing empirical proof of **Plate Rotational Invariance** achieved by fine-tuning with `degrees: 180.0` and `perspective: 0.0`.

---

## 2. FIGURE 3: QUALITATIVE FOOD PERCEPTION & ERROR TAXONOMY

**Rendered Figure Files:**
* Composite 7-Panel Grid (300 DPI): [docs/rajDocs4/wacv_figures/figure3_qualitative.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs4/wacv_figures/figure3_qualitative.png)
* Vector Composite PDF: [docs/rajDocs4/wacv_figures/figure3_qualitative.pdf](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs4/wacv_figures/figure3_qualitative.pdf)
* Primary Qualitative Report: [docs/rajDocs4/WACV_QUALITATIVE_ANALYSIS.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs4/WACV_QUALITATIVE_ANALYSIS.md)
* Extraction Script: [docs/rajDocs4/extract_qualitative_errors.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs4/extract_qualitative_errors.py)

---

### Detailed Qualitative Examples Inventory

#### (a) Correct High-Confidence Detection
* **Source Image Path:** `dataset/custom_training_data/valid/images/palak-paneer-recipe-5-_jpg.rf.b15d2eb0d0bdd215bf0646f01bf2aa2e.jpg`
* **Prediction Image Path:** `docs/rajDocs4/wacv_figures/qualitative/1_high_conf_correct.jpg`
* **Ground-Truth Class:** `palakpaneer` (Class ID 86)
* **Ground-Truth Bounding Box $[x_c, y_c, w, h]$:** `[0.6391, 0.6969, 0.5328, 0.3602]`
* **Predicted Class:** `palakpaneer` (Class ID 86)
* **Prediction Confidence:** **0.8792 (87.92%)**
* **Predicted Bounding Box $[x_c, y_c, w, h]$:** `[0.6386, 0.7134, 0.5834, 0.4717]` (IoU = 0.764)
* **Failure / Success Category Explanation:** Ideal localization and classification. The dark spinach-gravy texture with paneer cubes is accurately detected with high confidence under standard kitchen overhead lighting.

---

#### (b) Background False Positive Detection
* **Source Image Path:** `dataset/custom_training_data/valid/images/images-23-_jpg.rf.119409f30e02fc363828dc6099e86270.jpg`
* **Prediction Image Path:** `docs/rajDocs4/wacv_figures/qualitative/2_false_positive.jpg`
* **Ground-Truth Class:** `None` (Unannotated background table surface / cutting board)
* **Ground-Truth Bounding Box $[x_c, y_c, w, h]$:** `None`
* **Predicted Class:** `potato` (Class ID 94) & `garlic` (Class ID 51)
* **Prediction Confidence:** `potato`: **0.6367**, `garlic`: **0.2240**
* **Predicted Bounding Box $[x_c, y_c, w, h]$:** `potato`: `[0.4875, 0.3289, 0.5731, 0.5700]`, `garlic`: `[0.0532, 0.2223, 0.1064, 0.2162]`
* **Failure / Success Category Explanation:** Background false alarm. Irregular surface shading and textured background countertop woodgrain were misclassified as a raw potato with 63.67% confidence.

---

#### (c) Missed Detection (False Negative)
* **Source Image Path:** `dataset/custom_training_data/valid/images/images_jpg.rf.9c793985e464ad8a7ca5a62f358d0432.jpg`
* **Prediction Image Path:** `docs/rajDocs4/wacv_figures/qualitative/3_missed_detection.jpg`
* **Ground-Truth Class:** `farsi ko munta` (Class ID 47, 2 instances)
* **Ground-Truth Bounding Boxes $[x_c, y_c, w, h]$:** 
  * Box 1: `[0.4539, 0.5172, 0.6656, 0.7562]`
  * Box 2: `[0.6305, 0.6742, 0.4906, 0.5828]`
* **Predicted Class:** `No Detection`
* **Prediction Confidence:** `N/A` (All candidate proposals fell below threshold $\tau = 0.15$)
* **Failure / Success Category Explanation:** Under-represented rare class. `farsi ko munta` has only 2 validation images in the entire dataset, leading to complete missed detection due to severe class imbalance.

---

#### (d) Visually Similar Food Confusion
* **Source Image Path:** `dataset/custom_training_data/valid/images/-10_jpg.rf.557762ad8ef05ae3d44e9ff2469bedaf.jpg`
* **Prediction Image Path:** `docs/rajDocs4/wacv_figures/qualitative/4_visually_similar_confusion.jpg`
* **Ground-Truth Class:** `beans` (Class ID 10)
* **Ground-Truth Bounding Box $[x_c, y_c, w, h]$:** `[0.5719, 0.5000, 0.8531, 1.0000]`
* **Predicted Class:** `pea` (Class ID 89)
* **Prediction Confidence:** **0.7478 (74.78%)** (Multiple sub-pod detections ranging 0.15 to 0.75)
* **Predicted Bounding Box $[x_c, y_c, w, h]$:** `[0.6005, 0.4941, 0.7959, 0.9882]`
* **Failure / Success Category Explanation:** Inter-class morphological confusion. Green bean pods with round internal seed bumps were misclassified as `pea` due to high visual texture and color similarity.

---

#### (e) Duplicate Semantic Label Confusion
* **Source Image Path:** `dataset/custom_training_data/valid/images/img67_jpg.rf.fcd8c8004f87aea93605c97972cbbd2c.jpg`
* **Prediction Image Path:** `docs/rajDocs4/wacv_figures/qualitative/5_duplicate_semantic_confusion.jpg`
* **Ground-Truth Class:** `capsicum` (Class ID 28)
* **Ground-Truth Bounding Box $[x_c, y_c, w, h]$:** `[0.5414, 0.5164, 0.9172, 0.9672]`
* **Predicted Class:** `bell pepper` (Class ID 12)
* **Prediction Confidence:** **0.3567 (35.67%)**
* **Predicted Bounding Box $[x_c, y_c, w, h]$:** `[0.4988, 0.5115, 0.9572, 0.9718]` (IoU = 0.912)
* **Failure / Success Category Explanation:** Taxonomy noise & duplicate concept class IDs. The model localized the vegetable with 91.2% IoU but was penalized during un-normalized validation because the dataset labeled the image as `capsicum` while the model predicted its exact synonym `bell pepper`.

---

#### (f) Crowded Multi-Object Plate Detection
* **Source Image Path:** `dataset/custom_training_data/valid/images/-71_jpg.rf.4dfd1c56d135d5ad454170d7065b4e8c.jpg`
* **Prediction Image Path:** `docs/rajDocs4/wacv_figures/qualitative/6_crowded_plate.jpg`
* **Ground-Truth Class:** `bell pepper` (Class ID 12, 3 instances)
* **Ground-Truth Bounding Boxes $[x_c, y_c, w, h]$:**
  * Box 1: `[0.2356, 0.3834, 0.4062, 0.2548]`
  * Box 2: `[0.6575, 0.3894, 0.4495, 0.4255]`
  * Box 3: `[0.4327, 0.6082, 0.3942, 0.4976]`
* **Predicted Class:** `bell pepper` (Class ID 12, 4 instances detected)
* **Prediction Confidences:** `0.8485`, `0.8367`, `0.7533`, `0.2006`
* **Predicted Bounding Boxes $[x_c, y_c, w, h]$:**
  * Box 1: `[0.6597, 0.3958, 0.4705, 0.4373]` (Conf = 0.8485)
  * Box 2: `[0.4286, 0.6179, 0.4576, 0.4922]` (Conf = 0.8367)
  * Box 3: `[0.2394, 0.3818, 0.4200, 0.2906]` (Conf = 0.7533)
  * Box 4: `[0.8316, 0.4474, 0.3192, 0.3923]` (Conf = 0.2006)
* **Failure / Success Category Explanation:** Multi-item boundary handling. The model successfully separated 3 overlapping bell peppers with confidences $\ge 0.75$, with an additional low-confidence proposal on the boundary.

---

#### (g) Low-Confidence True Positive Detection
* **Source Image Path:** `dataset/custom_training_data/valid/images/images-21-_jpg.rf.3b38d0318c3c2796567020034cf3a6d1.jpg`
* **Prediction Image Path:** `docs/rajDocs4/wacv_figures/qualitative/7_low_confidence.jpg`
* **Ground-Truth Class:** `beans` (Class ID 10)
* **Ground-Truth Bounding Box $[x_c, y_c, w, h]$:** `[0.6844, 0.6852, 0.4125, 0.2828]`
* **Predicted Class:** `beans` (Class ID 10)
* **Prediction Confidence:** **0.1749 (17.49%)**
* **Predicted Bounding Box $[x_c, y_c, w, h]$:** `[0.6853, 0.6919, 0.5139, 0.3368]` (IoU = 0.672)
* **Failure / Success Category Explanation:** Threshold sensitivity. The object is correctly identified and localized (IoU = 0.672), but poor contrast and lighting reduced the prediction score to 17.49%, highlighting the need for dynamic thresholding or active learning correction.

---

## 3. COMMANDS TO REPRODUCE ALL ARTIFACTS

To reproduce all numerical values, tables, and figures from scratch:

```bash
# 1. Reproduce Dataset Distribution & Statistics (Experiment 2)
python docs/rajDocs4/fast_distribution.py

# 2. Reproduce Indian Dish Subset Evaluation (Experiment 1)
python docs/rajDocs4/eval_indian_subset.py

# 3. Reproduce Semantic Label Normalization (Experiment 3)
python docs/rajDocs4/eval_semantic_normalization.py

# 4. Reproduce Rotational Invariance Robustness (Experiment 4)
python docs/rajDocs4/eval_rotational_robustness.py

# 5. Reproduce Qualitative Error Extraction & Cropped Images (Experiment 5)
python docs/rajDocs4/extract_qualitative_errors.py

# 6. Render Publication Figures 2 and 3 (PNG & Vector PDF)
python docs/rajDocs4/generate_wacv_figures.py
```
