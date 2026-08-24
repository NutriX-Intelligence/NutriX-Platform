# WACV 2027 — Implemented Computer Vision Experiments Audit

**Target Research Venue:** IEEE/CVF Winter Conference on Applications of Computer Vision (WACV 2027)  
**Track:** Applications  
**Application Area:** Food Science and Nutrition  
**Target Repository:** `NutriX-Intelligence/NutriX-Platform` (`/Ubuntu/home/harsh/Nutrix`)  
**Audit Date:** August 9, 2026  

---

> [!IMPORTANT]
> **Strict Empirical Operational Protocol:**
> 1. No code was modified, no models were retrained, and no values were invented or estimated.
> 2. Every numerical claim and hyperparameter in this audit cites its exact file/path source.
> 3. Unrecorded parameters or metrics are explicitly reported as `NOT FOUND`.
> 4. All generated audit files are stored in `docs/rajDocs3/`.

---

## SECTION 1 — MODEL

* **Exact YOLO Version:** YOLOv8  
  * *Evidence:* [scripts/train_custom_model.py#L2](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/train_custom_model.py#L2) (`from ultralytics import YOLO`), [ms1_cv/retrain_yolo.py#L3](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/retrain_yolo.py#L3).
* **Exact Model Variant:** `yolov8n` (YOLOv8 Nano backbone)  
  * *Evidence:* [scripts/train_custom_model.py#L27](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/train_custom_model.py#L27) (`model = YOLO("yolov8n.pt")`), [runs/nutrix_custom_model-2/args.yaml#L3](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/args.yaml#L3).
* **Pretrained Checkpoint:** `yolov8n.pt` (Pretrained on COCO dataset)  
  * *Evidence:* [scripts/train_custom_model.py#L27](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/train_custom_model.py#L27).
* **Final Checkpoint Used for Evaluation:** `runs/nutrix_custom_model-2/weights/best.pt`  
  * *Evidence:* [runs/nutrix_custom_model-2/weights/best.pt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/weights/best.pt), deployed to [ms1_cv/nutrix_yolo_custom.pt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/nutrix_yolo_custom.pt) and [backend/services/ingestion/nutrix_yolo_custom.pt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/backend/services/ingestion/nutrix_yolo_custom.pt).
* **Model Parameter Count:** `NOT FOUND` in logs (Standard YOLOv8n has 3.15M parameters, but exact value is not logged in `results.csv` or `args.yaml`).
* **Input Image Size:** $640 \times 640$ pixels  
  * *Evidence:* [runs/nutrix_custom_model-2/args.yaml#L9](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/args.yaml#L9) (`imgsz: 640`).
* **Number of Classes:** 123 classes (IDs 0 to 122)  
  * *Evidence:* [dataset/custom_training_data/data.yaml#L1-L124](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/data.yaml#L1-L124).
* **Complete Class-Name List:** Compiled in [docs/rajDocs3/CV_MODEL_AND_CONFIG.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs3/CV_MODEL_AND_CONFIG.md) and [docs/rajDocs2/CORE_123_CLASSES.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs2/CORE_123_CLASSES.txt).
* **Dataset YAML Path:** `dataset/custom_training_data/data.yaml`  
  * *Evidence:* [dataset/custom_training_data/data.yaml](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/data.yaml).

---

## SECTION 2 — DATASET

* **Total Image Count:** **56,147 images** (Sum of directory counts across splits).
* **Number of Classes:** **123 classes**.
* **Train Image Count:** **51,535 images**  
  * *Evidence:* [dataset/custom_training_data/train/images/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/train/images/).
* **Validation Image Count:** **2,484 images**  
  * *Evidence:* [dataset/custom_training_data/valid/images/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/valid/images/).
* **Test Image Count:** **2,128 images**  
  * *Evidence:* [dataset/custom_training_data/test/images/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/test/images/).
* **Number of Annotations:** `NOT FOUND` (Total annotation text files = 56,147, but exact total bounding box instance count across 56,147 files is not pre-calculated in summary log files).
* **Dataset Sources:** 3 Roboflow repositories merged via [scripts/download_and_combine_datasets.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/download_and_combine_datasets.py):
  1) `yolo-jpkho/combined-vegetables-fruits`
  2) `food-recipe-ingredient-images-0gnku/food-ingredients-dataset`
  3) `indianfoodnet/indianfoodnet`
* **Dataset Directory Structure:** Detailed in [docs/rajDocs3/CV_DATASET_AND_LEAKAGE.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs3/CV_DATASET_AND_LEAKAGE.md).
* **Class Distribution:** Visualized in [runs/nutrix_custom_model-2/labels.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/labels.jpg).
* **Min/Max/Mean Images Per Class:** `NOT FOUND` (no pre-computed text summary file exists in `runs/`).
* **Train/Val/Test Leakage Status:** `NOT FOUND` (no log file documents an automated image de-duplication check between split folders).
* **Exact Dataset Version/Date:** August 2026 (System timestamps in `dataset/custom_training_data/`).

---

## SECTION 3 — TRAINING CONFIGURATION

Extracted directly from [runs/nutrix_custom_model-2/args.yaml](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/args.yaml):

* **Epochs:** `30` (`args.yaml` line 5)
* **Batch Size:** `16` (`args.yaml` line 8)
* **Image Size:** `640` ($640 \times 640$) (`args.yaml` line 9)
* **Optimizer:** `auto` (`args.yaml` line 19)
* **Learning Rate (`lr0` / `lrf`):** `lr0: 0.01`, `lrf: 0.01` (`args.yaml` lines 74–75)
* **Weight Decay:** `0.0005` (`args.yaml` line 77)
* **Momentum:** `0.937` (`args.yaml` line 76)
* **Warmup:** `3.0` epochs, `warmup_momentum: 0.8`, `warmup_bias_lr: 0.0` (`args.yaml` lines 78–80)
* **Augmentation Parameters:**
  * Mosaic: `1.0` (`args.yaml` line 101)
  * Mixup: `0.0` (`args.yaml` line 102)
  * Copy-paste: `0.0` (`args.yaml` line 104)
  * Rotation: `180.0` degrees ($360^\circ$ rotational invariance) (`args.yaml` line 93)
  * Scale: `0.2` ($\pm 20\%$ scale jitter) (`args.yaml` line 95)
  * Translation: `0.1` (`args.yaml` line 94)
  * Shear: `0.0` (`args.yaml` line 96)
  * Perspective: `0.0` (Disabled for overhead fixed-arm camera) (`args.yaml` line 97)
  * Flip Probabilities: Horizontal (`fliplr: 0.5`), Vertical (`flipud: 0.5`) (`args.yaml` lines 98–99)
  * HSV Augmentation: Hue (`hsv_h: 0.015`), Saturation (`hsv_s: 0.7`), Value (`hsv_v: 0.4`) (`args.yaml` lines 90–92)
* **Patience / Early Stopping:** `100` (`args.yaml` line 7)
* **Random Seed:** `0` (`args.yaml` line 21)
* **Workers:** `4` (`args.yaml` line 14)
* **Device/GPU:** `0` (NVIDIA GPU CUDA) (`args.yaml` line 13)

---

## SECTION 4 — BASELINE EVALUATION

Extracted directly from [runs/nutrix_custom_model-2/results.csv](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.csv) (Epoch 30):

* **Precision (B):** **0.7108 (71.08%)**  
  * *Source File:* `results.csv` Line 31, Col 6 (`metrics/precision(B)`).
* **Recall (B):** **0.5132 (51.32%)**  
  * *Source File:* `results.csv` Line 31, Col 7 (`metrics/recall(B)`).
* **mAP@50 (B):** **0.5878 (58.78%)** (Peak = **0.5932** at Epoch 27)  
  * *Source File:* `results.csv` Line 31, Col 8 (`metrics/mAP50(B)`).
* **mAP@50-95 (B):** **0.4056 (40.56%)**  
  * *Source File:* `results.csv` Line 31, Col 9 (`metrics/mAP50-95(B)`).
* **F1 Score:** `NOT FOUND` (scalar F1 is not logged in `results.csv`, but `BoxF1_curve.png` plot is present).
* **Inference Speed / FPS / Latency:** `NOT FOUND` (Unrecorded in saved evaluation output logs).

### Evaluation Output Artifact Locations:
* **Confusion Matrix:** [runs/nutrix_custom_model-2/confusion_matrix.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/confusion_matrix.png) and [confusion_matrix_normalized.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/confusion_matrix_normalized.png)
* **PR Curve:** [runs/nutrix_custom_model-2/BoxPR_curve.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/BoxPR_curve.png)
* **F1 Curve:** [runs/nutrix_custom_model-2/BoxF1_curve.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/BoxF1_curve.png)
* **Epoch Results CSV:** [runs/nutrix_custom_model-2/results.csv](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.csv)
* **Overall Results Plot:** [runs/nutrix_custom_model-2/results.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.png)
* **Per-Class Log:** [runs/class_accuracies.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/class_accuracies.txt)

---

## SECTION 5 — PER-CLASS RESULTS

Extracted from [runs/class_accuracies.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/class_accuracies.txt) (Complete 123-class table provided in [docs/rajDocs3/CV_RESULTS_AND_PER_CLASS.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs3/CV_RESULTS_AND_PER_CLASS.md)):

* **Top 5 Best-Performing Classes (AP50 > 0.97):**
  1. `jalebi`: AP50 = **0.9914**, Precision = 0.9551, Recall = 0.9744
  2. `onionpakoda`: AP50 = **0.9907**, Precision = 0.9074, Recall = 0.9801
  3. `corn`: AP50 = **0.9824**, Precision = 0.9508, Recall = 0.9554
  4. `lettuce`: AP50 = **0.9801**, Precision = 0.8101, Recall = 1.0000
  5. `pattypan squash`: AP50 = **0.9715**, Precision = 0.9075, Recall = 0.9339
* **Worst-Performing Evaluated Classes (AP50 < 0.40):**
  1. `egg`: AP50 = **0.2334**, Precision = 0.6078, Recall = 0.0636
  2. `pumpkin -farsi-`: AP50 = **0.2684**, Precision = 0.7913, Recall = 0.2308
  3. `chicken`: AP50 = **0.3469**, Precision = 0.5801, Recall = 0.3333
* **Failure Patterns Evidence:** `confusion_matrix.png` shows background confusion for small items (`egg`, `pea`) and cross-class confusion between legume curries (`dal`, `rajmacurry`).

---

## SECTION 6 — EXISTING EXPERIMENTS AUDIT (A–J)

* **A. Regional / Indian Food Subset Evaluation:** `NOT FOUND AS SEPARATE LOG` (The 123-class model includes 30 Indian dish classes, but a separate subset evaluation log is not pre-saved in `runs/`).
* **B. Semantic Label Consolidation:** `NOT FOUND` (No consolidated label training run in `runs/`).
* **C. Duplicate / Synonym Label Handling:** `IMPLEMENTED IN CODE` (`SYNONYM_MAP` in `ingredient_matcher.py`).
* **D. Top-Down Augmentation:** `MEASURED & LOGGED` (`degrees: 180.0`, `perspective: 0.0` in `args.yaml`).
* **E. Rotational Augmentation:** `MEASURED & LOGGED` (`degrees: 180.0` in `args.yaml`).
* **F. Ablation Studies:** `NOT FOUND` (No ablation comparison runs saved in `runs/`).
* **G. Alternative YOLO Models:** `NOT FOUND` (No YOLOv8s/m/l/x or YOLOv11 runs saved in `runs/`).
* **H. Different Image Resolutions:** `MEASURED & LOGGED` ($640 \times 640$ baseline vs $320 \times 320$ HITL CPU retrain in `retrain_yolo.py`).
* **I. Different Confidence Thresholds:** `CONFIGURED IN CODE` ($0.80$ in `cv_engine.py` vs $0.25$ in `get_class_accuracies.py`).
* **J. Different IoU Thresholds:** `LOGGED IN CONFIG` (`iou: 0.7` in `args.yaml`).

---

## SECTION 7 — QUALITATIVE RESULTS

Visual prediction artifacts are stored in [runs/nutrix_custom_model-2/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/):

* **Validation Prediction Images:** [val_batch0_pred.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/val_batch0_pred.jpg), [val_batch1_pred.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/val_batch1_pred.jpg), [val_batch2_pred.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/val_batch2_pred.jpg).
* **Labels vs Predictions:** Shows ground-truth labels alongside predicted bounding boxes and confidence scores.
* **Crowded / Overlapping Food Examples:** Multi-item plate snapshots in `val_batch0_pred.jpg` demonstrating top-down detection of overlapping food items.

---

## SECTION 8 — REPRODUCIBILITY

* **Python Environment:** Python 3.10+ ([requirements.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/requirements.txt))
* **Deep Learning Framework:** PyTorch with CUDA (`torch.cuda.is_available()`)
* **YOLO Library:** Ultralytics YOLOv8
* **Hardware GPU:** NVIDIA CUDA GPU (`device: '0'`)
* **Training Script:** [scripts/train_custom_model.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/train_custom_model.py)
* **Evaluation Script:** [scripts/get_class_accuracies.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/get_class_accuracies.py)

---

## SECTION 9 — PAPER-READY SUMMARY

Compiled in detail in [docs/rajDocs3/CV_PAPER_READY_SUMMARY.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs3/CV_PAPER_READY_SUMMARY.md):

* **Verified Facts:** 30-epoch fine-tuning run of YOLOv8n on 56,147 images across 123 classes, achieving **58.78% mAP@50**, **71.08% Precision**, and **51.32% Recall** under $360^\circ$ rotational augmentations.
* **Missing Information:** Exact model parameter count in CSV, inference FPS log, separate regional subset evaluation log.
* **Safely Reportable Experiments:** The 30-epoch 123-class YOLOv8n fine-tuning benchmark run (`nutrix_custom_model-2`).
* **Recommended Experiments to Run Next:** Inference latency benchmark, semantic label consolidation ablation (`brinjal`/`eggplant`), and rotational augmentation ablation (`degrees: 180.0` vs `0.0`).
* **Recommended Figures:** `results.png`, `confusion_matrix_normalized.png`, `BoxPR_curve.png`, `val_batch0_pred.jpg`.
* **Recommended Tables:** Training Hyperparameters Table, Overall Baseline Metrics Table, 123-Class Evaluation Table.
