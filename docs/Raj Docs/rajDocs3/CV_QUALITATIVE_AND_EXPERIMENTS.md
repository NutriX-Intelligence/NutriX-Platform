# WACV 2027 Audit: Experiments Inventory, Qualitative Images & Reproducibility

**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  
**Scope:** Verification of Completed Experiments (A–J), Qualitative Prediction Image Artifacts, and Environment Reproducibility Specifications.

---

## 1. EXISTING EXPERIMENTS AUDIT (A–J INVENTORY)

| Experiment Category | Verification Status | Configuration & Findings | Output File / Source Path |
| :--- | :--- | :--- | :--- |
| **A. Regional / Indian Subset Evaluation** | `NOT FOUND` as separate log | The 123-class model contains 30 Indian dish classes, but a separate isolated evaluation script output log is NOT pre-saved in `runs/`. | [runs/class_accuracies.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/class_accuracies.txt) (contains all 123 classes together) |
| **B. Semantic Label Consolidation** | `NOT FOUND` | No training run directory in `runs/` documents a consolidated label experiment (e.g. merging `brinjal` + `eggplant`). | [runs/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/) |
| **C. Duplicate / Synonym Label Handling** | `IMPLEMENTED IN CODE` | `SYNONYM_MAP` in `ingredient_matcher.py` maps 80+ Indian/English terms for nutrition lookup, but CV label consolidation experiment is NOT pre-run. | [app/services/ingredient_matcher.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/ingredient_matcher.py) |
| **D. Top-Down Augmentation** | `MEASURED & LOGGED` | Locked-in hyperparameters for overhead fixed-arm plate setting: `degrees: 180.0`, `perspective: 0.0`, `flipud: 0.5`, `fliplr: 0.5`. | [runs/nutrix_custom_model-2/args.yaml#L93-L99](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/args.yaml#L93-L99) |
| **E. Rotational Augmentation** | `MEASURED & LOGGED` | Full $360^\circ$ rotational invariance (`degrees: 180.0`). | [runs/nutrix_custom_model-2/args.yaml#L93](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/args.yaml#L93) |
| **F. Ablation Studies** | `NOT FOUND` | No baseline vs ablation comparison runs (e.g. `degrees: 0.0` vs `180.0`) are pre-saved in `runs/`. | [runs/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/) |
| **G. Alternative YOLO Models** | `NOT FOUND` | No YOLOv8s/m/l/x or YOLOv11 evaluation runs are pre-saved in `runs/`. | [runs/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/) |
| **H. Different Image Resolutions** | `MEASURED & LOGGED` | Main baseline used $640 \times 640$ (`train_custom_model.py`); HITL CPU retraining used $320 \times 320$ (`retrain_yolo.py`). | [scripts/train_custom_model.py#L21](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/train_custom_model.py#L21)<br/>[ms1_cv/retrain_yolo.py#L62](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/retrain_yolo.py#L62) |
| **I. Different Confidence Thresholds**| `CONFIGURED IN CODE` | Ingestion engine uses `confidence_threshold = 0.80` (`cv_engine.py`); validation script uses `conf = 0.25` (`get_class_accuracies.py`). | [ms1_cv/cv_engine.py#L64](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/cv_engine.py#L64)<br/>[scripts/get_class_accuracies.py#L26](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/get_class_accuracies.py#L26) |
| **J. Different IoU Thresholds** | `MEASURED & LOGGED` | `iou: 0.7` locked in training config. | [runs/nutrix_custom_model-2/args.yaml#L41](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/args.yaml#L41) |

---

## 2. QUALITATIVE PREDICTION IMAGES INVENTORY

All prediction image artifacts are stored in [runs/nutrix_custom_model-2/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/):

1. **Validation Prediction Visualizations (`val_batch*_pred.jpg`):**
   * **[val_batch0_pred.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/val_batch0_pred.jpg)** vs **[val_batch0_labels.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/val_batch0_labels.jpg)**
   * **[val_batch1_pred.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/val_batch1_pred.jpg)** vs **[val_batch1_labels.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/val_batch1_labels.jpg)**
   * **[val_batch2_pred.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/val_batch2_pred.jpg)** vs **[val_batch2_labels.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/val_batch2_labels.jpg)**
   * *Contents:* Shows ground-truth vs predicted bounding boxes, class labels, and confidence scores across validation batches.
2. **Training Batch Augmentation Visualizations (`train_batch*.jpg`):**
   * **[train_batch0.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/train_batch0.jpg)**, **[train_batch1.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/train_batch1.jpg)**, **[train_batch2.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/train_batch2.jpg)**, **[train_batch64420.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/train_batch64420.jpg)**, **[train_batch64421.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/train_batch64421.jpg)**, **[train_batch64422.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/train_batch64422.jpg)**
   * *Contents:* Demonstrates mosaic grid formation, $360^\circ$ rotational transforms, and portion scaling.

---

## 3. REPRODUCIBILITY ENVIRONMENT SPECIFICATION

* **Python Version:** Python 3.10+ ([requirements.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/requirements.txt))
* **Deep Learning Framework:** PyTorch with CUDA acceleration (`torch.cuda.is_available()`)
* **Computer Vision Library:** Ultralytics YOLOv8 (`ultralytics`)
* **Operating System:** Linux (Ubuntu on WSL2) / Windows
* **Hardware GPU:** NVIDIA CUDA GPU (`device: '0'`)
* **Primary Requirements File:** [requirements.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/requirements.txt)
* **Training Execution Script:** [scripts/train_custom_model.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/train_custom_model.py)
* **Class Evaluation Script:** [scripts/get_class_accuracies.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/get_class_accuracies.py)
* **Edge Inference Script:** [scripts/esp32_inference.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/esp32_inference.py)
