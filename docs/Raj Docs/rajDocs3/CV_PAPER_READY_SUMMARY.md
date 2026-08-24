# WACV 2027 Summary: Paper-Ready Audit Findings

**Target Research Venue:** IEEE/CVF Winter Conference on Applications of Computer Vision (WACV 2027)  
**Track:** Applications  
**Application Area:** Food Science and Nutrition  
**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  

---

## A. VERIFIED FACTS (100% Empirically Supported by Repository Artifacts)

1. **Model Architecture:** YOLOv8 Nano (`yolov8n` backbone) fine-tuned on a custom 123-class food dataset for 30 epochs ([runs/nutrix_custom_model-2/args.yaml](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/args.yaml)).
2. **Dataset Size & Split Breakdown:** 56,147 total images across 123 classes: 51,535 train, 2,484 validation, and 2,128 test ([dataset/custom_training_data/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/)).
3. **Dataset Composition:** Consolidated from 3 Roboflow projects (`combined-vegetables-fruits`, `food-ingredients-dataset`, `indianfoodnet`) via [scripts/download_and_combine_datasets.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/download_and_combine_datasets.py).
4. **Plate-Level Augmentations:** Full $360^\circ$ rotational invariance (`degrees: 180.0`), scale jitter (`scale: 0.2`), zero perspective distortion (`perspective: 0.0`), horizontal flip (`fliplr: 0.5`), vertical flip (`flipud: 0.5`), mosaic (`mosaic: 1.0`).
5. **Overall Measured Baseline Accuracy (Validation Split, 2,484 imgs):**
   * **Precision (B):** **0.7108 (71.08%)** (Epoch 30)
   * **Recall (B):** **0.5132 (51.32%)** (Epoch 30)
   * **mAP@50 (B):** **0.5878 (58.78%)** (Epoch 30), Peak = **0.5932 (59.32%)** (Epoch 27)
   * **mAP@50-95 (B):** **0.4056 (40.56%)** (Epoch 30)
   * Source File: [runs/nutrix_custom_model-2/results.csv](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.csv)
6. **Class Accuracy Highlights:** 9 classes achieved mAP@50 $> 0.95$ (`jalebi` 0.9914, `onionpakoda` 0.9907, `corn` 0.9824, `lettuce` 0.9801, `poha` 0.9663, `palakpaneer` 0.9636, `cauliflower` 0.9555). Source: [runs/class_accuracies.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/class_accuracies.txt).
7. **Human-in-the-Loop Active Learning:** Working 4-level engine ([ms1_cv/hitl_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/hitl_engine.py)) auto-generating YOLO `.txt` annotations from user corrections and triggering 1-epoch CPU retraining ([ms1_cv/retrain_yolo.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/retrain_yolo.py)).
8. **Hardware Integration:** Implemented ESP32-CAM HTTP image capture and inference pipeline script ([scripts/esp32_inference.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/esp32_inference.py)).

---

## B. MISSING INFORMATION (Required for Paper but Unrecorded in Repository Files)

1. **Exact Model Parameter Count:** Unrecorded in `results.csv` or `args.yaml` (Standard YOLOv8n has 3.15M parameters).
2. **Inference Speed / FPS / Latency Logs:** No benchmark output log recording milliseconds per frame on GPU vs CPU.
3. **Total Bounding Box Count:** Exact total count of annotated bounding box objects across 56,147 files is un-summarized in text logs.
4. **Automated De-duplication / Leakage Log:** No script log file documents a SHA-256 image de-duplication check between `train` and `test` split folders.

---

## C. EXISTING EXPERIMENTS WE CAN SAFELY REPORT

1. **30-Epoch YOLOv8n Fine-Tuning Benchmark:** Full epoch-by-epoch loss (box, cls, dfl) and mAP progression logged in `results.csv`.
2. **123-Class Per-Class Precision, Recall & mAP50 Evaluation:** Complete 123-class accuracy evaluation logged in `class_accuracies.txt`.
3. **Overhead Camera Rotational Augmentation Setup:** Locked-in augmentation parameters (`degrees: 180.0`, `perspective: 0.0`) in `args.yaml`.

---

## D. RECOMMENDED EXPERIMENTS TO RUN FOR WACV PAPER

> [!CAUTION]
> Do NOT run these now (per user directive). These are identified for future execution to strengthen paper submission:

1. **Inference Latency Benchmarking (P0):** Measure frame processing latency (ms) on GPU, CPU, and ESP32-CAM HTTP link.
2. **Semantic Class Consolidation Ablation (P0):** Merge duplicate concept classes (`brinjal` + `eggplant`, `capsicum` + `bell pepper`) in `data.yaml` and re-evaluate mAP50.
3. **Rotational Augmentation Ablation Study (P1):** Compare `degrees: 180.0` vs default `degrees: 0.0` to quantify accuracy gain from overhead plate rotational invariance.
4. **Indian Regional 30-Class Subset Benchmark (P1):** Measure detection performance specifically on the 30 Indian dish classes vs raw produce.

---

## E. RECOMMENDED FIGURES FROM EXISTING ARTIFACTS

1. **Figure 1 (System Architecture):** Mermaid High-Level Architecture Diagram from [docs/ArchitectureDiagrams.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/ArchitectureDiagrams.md).
2. **Figure 2 (Training Convergence):** 8-panel loss and metric progression plot from [runs/nutrix_custom_model-2/results.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.png).
3. **Figure 3 (Visual Confusion Matrix):** 123-class normalized confusion matrix from [runs/nutrix_custom_model-2/confusion_matrix_normalized.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/confusion_matrix_normalized.png).
4. **Figure 4 (Precision-Recall Curve):** PR curve across thresholds from [runs/nutrix_custom_model-2/BoxPR_curve.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/BoxPR_curve.png).
5. **Figure 5 (Qualitative Predictions):** Bounding box predictions on validation images from [runs/nutrix_custom_model-2/val_batch0_pred.jpg](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/val_batch0_pred.jpg).

---

## F. RECOMMENDED TABLES FROM EXISTING ARTIFACTS

1. **Table 1 (Model & Training Hyperparameters):** Constructed from [CV_MODEL_AND_CONFIG.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs3/CV_MODEL_AND_CONFIG.md).
2. **Table 2 (Dataset Split Breakdown & Sources):** Constructed from [CV_DATASET_AND_LEAKAGE.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs3/CV_DATASET_AND_LEAKAGE.md).
3. **Table 3 (Overall Baseline Performance Metrics):** Constructed from [CV_RESULTS_AND_PER_CLASS.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs3/CV_RESULTS_AND_PER_CLASS.md).
4. **Table 4 (Top-10 & Bottom-10 Per-Class Accuracy Comparison):** Constructed from [CV_RESULTS_AND_PER_CLASS.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs3/CV_RESULTS_AND_PER_CLASS.md).
