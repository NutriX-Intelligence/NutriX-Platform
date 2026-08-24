# WACV 2027 Audit: Dataset Structure, Splits & Leakage Inspection

**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  
**Scope:** Verification of Dataset Image Counts, Split Distribution, Sources, Annotations, and Leakage Risk Audit.

---

## 1. DATASET METRICS & SPLIT BREAKDOWN

All image count metrics were verified directly from directory file counts inside `dataset/custom_training_data/`:

| Dataset Metric | Verified Count / Value | Source File / Directory Path |
| :--- | :--- | :--- |
| **Total Image Count** | **56,147 images** | Sum of `train`, `valid`, and `test` image directories |
| **Number of Classes** | **123 classes** (IDs 0–122) | [dataset/custom_training_data/data.yaml](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/data.yaml) |
| **Train Image Count** | **51,535 images** | [dataset/custom_training_data/train/images/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/train/images/) |
| **Validation Image Count**| **2,484 images** | [dataset/custom_training_data/valid/images/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/valid/images/) |
| **Test Image Count** | **2,128 images** | [dataset/custom_training_data/test/images/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/test/images/) |
| **Total Annotation Files**| **56,147 text files** | `train/labels/` (51,535), `valid/labels/` (2,484), `test/labels/` (2,128) |
| **Total Bounding Box Count**| `NOT FOUND` | Exact box count across 56,147 files is not pre-computed in summary log files |
| **Min/Max/Mean Per Class**| `NOT FOUND` | Per-class image count distribution summary is visual only (`labels.jpg`) |
| **Dataset Creation Date** | August 2026 | System file timestamps in `dataset/custom_training_data/` |

---

## 2. DATASET SOURCES & COMBINATION PIPELINE

Created programmatically by [scripts/download_and_combine_datasets.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/download_and_combine_datasets.py) by merging 3 Roboflow dataset repositories:

```python
# Source: scripts/download_and_combine_datasets.py lines 110-120
proj1 = rf.workspace("yolo-jpkho").project("combined-vegetables-fruits")
proj2 = rf.workspace("food-recipe-ingredient-images-0gnku").project("food-ingredients-dataset")
proj3 = rf.workspace("indianfoodnet").project("indianfoodnet")
```

The script parses the local `data.yaml` from each Roboflow project, constructs a global 123-class index mapping (`all_class_names`), remaps the class IDs inside each bounding box `.txt` file, and outputs the combined structure to `dataset/custom_training_data/`.

---

## 3. DIRECTORY STRUCTURE

```
dataset/custom_training_data/
├── data.yaml                     # Unified 123-class configuration
├── train/
│   ├── images/                  # 51,535 JPEG/PNG images
│   ├── labels/                  # 51,535 YOLO annotation text files
│   └── labels.cache             # Ultralytics pre-parsed cache (19.6 MB)
├── valid/
│   ├── images/                  # 2,484 JPEG/PNG images
│   └── labels/                  # 2,484 YOLO annotation text files
└── test/
    ├── images/                  # 2,128 JPEG/PNG images
    └── labels/                  # 2,128 YOLO annotation text files
```

---

## 4. DATASET LEAKAGE & DUPLICATION AUDIT

1. **Train/Val/Test Leakage Verification Status:** `NOT FOUND`  
   No log file or script documents an automated image hash de-duplication check between `train/images`, `valid/images`, and `test/images`.
2. **Multi-Source Combination Risk:**  
   `download_and_combine_datasets.py` merged `train`, `valid`, and `test` splits from 3 independent Roboflow projects directly. If the underlying Roboflow projects shared common web-scraped images, cross-split image duplication could exist.
3. **Verified Concept Duplication (Class ID Noise):**  
   Inspection of `data.yaml` confirms exact visual concept duplication assigned to separate Class IDs:
   * **`brinjal` (ID 22) vs `eggplant` (ID 46):** Exact semantic and visual duplicate.
   * **`capsicum` (ID 12) vs `bell pepper` (ID 28):** Exact semantic and visual duplicate.
   * *Impact:* Evaluating a model on these un-consolidated labels creates artificial evaluation penalties during validation when the model detects an `eggplant` on an image annotated as `brinjal`.
