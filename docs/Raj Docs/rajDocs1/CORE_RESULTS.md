# WACV 2027 Technical Audit: Core Measured Results

**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  
**Scope:** Measured Quantitative Metrics, Precision/Recall, mAP Scores, Loss Curves, and Per-Class Performance.

> [!IMPORTANT]
> **Audit Strictness:** All metrics presented in this document represent measured values extracted directly from `runs/nutrix_custom_model-2/results.csv` and `runs/class_accuracies.txt`. No unmeasured metrics have been computed post-hoc.

---

## 1. Overall System Object Detection Results

* **Model Evaluated:** YOLOv8n fine-tuned on NutriX 123-class dataset (`nutrix_custom_model-2`)
* **Evaluation Dataset:** Validation split (`valid/images`, 2,484 images)
* **Evidence File:** [runs/nutrix_custom_model-2/results.csv](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.csv)
* **Status:** `[MEASURED]`

| Metric Identifier | Final Value (Epoch 30) | Peak Measured Value | Epoch of Peak | Evidence File |
| :--- | :--- | :--- | :--- | :--- |
| **Precision (B)** | **0.7108 (71.08%)** | 0.7167 (71.67%) | Epoch 28 | `results.csv` (Col 6) |
| **Recall (B)** | **0.5132 (51.32%)** | 0.5232 (52.32%) | Epoch 16 | `results.csv` (Col 7) |
| **mAP@50 (B)** | **0.5878 (58.78%)** | **0.5932 (59.32%)** | **Epoch 27** | `results.csv` (Col 8) |
| **mAP@50-95 (B)** | **0.4056 (40.56%)** | **0.4056 (40.56%)** | **Epoch 30** | `results.csv` (Col 9) |
| **Validation Box Loss** | **1.1489** | 1.1489 (Min) | Epoch 30 | `results.csv` (Col 10) |
| **Validation Class Loss**| **0.9931** | 0.98998 (Min) | Epoch 24 | `results.csv` (Col 11) |
| **Validation DFL Loss** | **1.4436** | 1.4436 (Min) | Epoch 30 | `results.csv` (Col 12) |

---

## 2. Benchmark Epoch Progression Trajectory

Extracted from `results.csv`:

```
Epoch  1 | P: 0.3650 | R: 0.2251 | mAP50: 0.1628 | mAP50-95: 0.0735
Epoch  5 | P: 0.4639 | R: 0.3941 | mAP50: 0.4229 | mAP50-95: 0.2608
Epoch 10 | P: 0.6283 | R: 0.4625 | mAP50: 0.5239 | mAP50-95: 0.3487
Epoch 15 | P: 0.6408 | R: 0.5126 | mAP50: 0.5759 | mAP50-95: 0.3858
Epoch 20 | P: 0.6752 | R: 0.5078 | mAP50: 0.5825 | mAP50-95: 0.3965
Epoch 25 | P: 0.6937 | R: 0.5164 | mAP50: 0.5924 | mAP50-95: 0.4033
Epoch 27 | P: 0.7062 | R: 0.5190 | mAP50: 0.5932 | mAP50-95: 0.4044  <-- Peak mAP50
Epoch 30 | P: 0.7108 | R: 0.5132 | mAP50: 0.5878 | mAP50-95: 0.4056  <-- Peak mAP50-95
```

---

## 3. Class-Level Measured Results Breakdown

Extracted from [runs/class_accuracies.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/class_accuracies.txt):

### 3.1 Top 15 Highest Performing Dishes & Food Classes

| Class ID | Class Name | Precision (P) | Recall (R) | mAP@50 | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 67 | **jalebi** | 0.9551 | 0.9744 | **0.9914** | `[MEASURED]` |
| 84 | **onionpakoda** | 0.9074 | 0.9801 | **0.9907** | `[MEASURED]` |
| 40 | **corn** | 0.9508 | 0.9554 | **0.9824** | `[MEASURED]` |
| 74 | **lettuce** | 0.8101 | 1.0000 | **0.9801** | `[MEASURED]` |
| 88 | **pattypan squash** | 0.9075 | 0.9339 | **0.9715** | `[MEASURED]` |
| 93 | **poha** | 0.9367 | 0.9143 | **0.9663** | `[MEASURED]` |
| 86 | **palakpaneer** | 0.9495 | 0.9778 | **0.9636** | `[MEASURED]` |
| 11 | **beet** | 0.7916 | 0.9497 | **0.9595** | `[MEASURED]` |
| 30 | **cauliflower** | 0.8959 | 0.9007 | **0.9555** | `[MEASURED]` |
| 83 | **onion** | 0.9009 | 0.8927 | **0.9376** | `[MEASURED]` |
| 38 | **chole** | 0.7992 | 0.9167 | **0.9340** | `[MEASURED]` |
| 7 | **avocado** | 0.9370 | 0.7942 | **0.9298** | `[MEASURED]` |
| 116 | **vegetable marrow** | 0.7231 | 0.9525 | **0.9270** | `[MEASURED]` |
| 16 | **bitter gourd** | 1.0000 | 0.5453 | **0.9268** | `[MEASURED]` |
| 42 | **dal** | 0.9264 | 0.8387 | **0.9239** | `[MEASURED]` |
| 15 | **biryani** | 0.8415 | 0.8258 | **0.9234** | `[MEASURED]` |
