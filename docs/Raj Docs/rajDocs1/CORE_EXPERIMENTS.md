# WACV 2027 Technical Audit: Core Experiments Inventory

**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  
**Scope:** Inventory of Completed Model Training Runs, Evaluation Experiments, and Verification Scripts.

---

## 1. Executive Experiment Inventory Table

| Experiment Identifier | Purpose & Objective | Dataset & Model | Primary Configuration | Evidence Artifacts | Reproducibility |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`nutrix_custom_model-2`** | Fine-tune baseline YOLOv8n on 123-class consolidated food dataset with plate-level rotational augmentations. | Dataset: `custom_training_data` (56,147 images)<br/>Model: YOLOv8n (`yolov8n.pt`) | Epochs: 30, Batch: 16, Resolution: 640x640, Device: GPU, `degrees: 180.0`, `perspective: 0.0` | [runs/nutrix_custom_model-2/results.csv](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.csv)<br/>[args.yaml](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/args.yaml)<br/>[confusion_matrix.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/confusion_matrix.png) | Fully Reproducible via [scripts/train_custom_model.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/train_custom_model.py) |
| **`class_accuracies_eval`** | Measure class-wise Precision, Recall, and mAP@50 across all 123 food classes on validation split. | Dataset: `valid/images` (2,484 images)<br/>Model: fine-tuned `nutrix_custom_model-2` | Validation mode, confidence threshold 0.25, IoU 0.7 | [runs/class_accuracies.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/class_accuracies.txt) | Fully Reproducible via [scripts/get_class_accuracies.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/get_class_accuracies.py) |
| **`hitl_active_learning`** | Verify online incremental 1-epoch fine-tuning pipeline on user-corrected misclassifications. | Dataset: `dataset/trained/`<br/>Model: YOLOv8n base | Epochs: 1, Batch: 2, Resolution: 320x320, Device: CPU | [ms1_cv/retrain_yolo.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/retrain_yolo.py)<br/>[hitl_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/hitl_engine.py) | Fully Reproducible via [scripts/run_hitl_interactive.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/run_hitl_interactive.py) |
| **`esp32_edge_inference`** | Test live image frame capture from ESP32-CAM HTTP endpoint and local inference response. | Hardware: ESP32-CAM (`http://192.168.29.134/capture`) | Live GET request, local model evaluation | [scripts/esp32_inference.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/esp32_inference.py) | Hardware Dependent |

---

## 2. Experiment Deep Dives

### 2.1 Experiment 1: 30-Epoch Model Fine-Tuning (`nutrix_custom_model-2`)
* **Objective:** Establish object detection baseline across 123 food classes.
* **Loss Functions Monitored:**
  * Box Loss (`train/box_loss` vs `val/box_loss`): Decreased from 1.608 to 1.186 (train) and 1.770 to 1.149 (val).
  * Class Loss (`train/cls_loss` vs `val/cls_loss`): Decreased from 3.743 to 1.353 (train) and 2.753 to 0.993 (val).
  * Distribution Focal Loss (`train/dfl_loss` vs `val/dfl_loss`): Decreased from 1.855 to 1.446 (train) and 2.246 to 1.444 (val).
* **Metric Evolution:**
  * Epoch 1: Precision = 0.3650, Recall = 0.2251, mAP@50 = 0.1628, mAP@50-95 = 0.0735
  * Epoch 10: Precision = 0.6283, Recall = 0.4625, mAP@50 = 0.5239, mAP@50-95 = 0.3487
  * Epoch 20: Precision = 0.6752, Recall = 0.5078, mAP@50 = 0.5825, mAP@50-95 = 0.3965
  * Epoch 30: Precision = 0.7108, Recall = 0.5132, mAP@50 = 0.5878, mAP@50-95 = 0.4056

### 2.2 Experiment 2: Per-Class Accuracy Evaluation (`class_accuracies.txt`)
* **Objective:** Benchmark per-class detector strengths and identify failure cases.
* **Top-Performing Classes (mAP@50 > 0.95):**
  * `jalebi`: Precision = 0.9551, Recall = 0.9744, mAP@50 = **0.9914**
  * `onionpakoda`: Precision = 0.9074, Recall = 0.9801, mAP@50 = **0.9907**
  * `corn`: Precision = 0.9508, Recall = 0.9554, mAP@50 = **0.9824**
  * `lettuce`: Precision = 0.8101, Recall = 1.0000, mAP@50 = **0.9801**
  * `pattypan squash`: Precision = 0.9075, Recall = 0.9339, mAP@50 = **0.9715**
  * `poha`: Precision = 0.9367, Recall = 0.9143, mAP@50 = **0.9663**
  * `palakpaneer`: Precision = 0.9495, Recall = 0.9778, mAP@50 = **0.9636**
  * `beet`: Precision = 0.7916, Recall = 0.9497, mAP@50 = **0.9595**
  * `cauliflower`: Precision = 0.8959, Recall = 0.9007, mAP@50 = **0.9555**
* **Challenging / Low-Performance Classes:**
  * `egg`: Precision = 0.6078, Recall = 0.0636, mAP@50 = **0.2334**
  * `chicken`: Precision = 0.5801, Recall = 0.3333, mAP@50 = **0.3469**
  * `pea`: Precision = 0.4604, Recall = 0.5238, mAP@50 = **0.4245**
