# NutriX WACV 2027 — Core-to-Regional Compatibility Audit

**Target Research Venue:** IEEE/CVF Winter Conference on Applications of Computer Vision (WACV 2027)  
**Track:** Applications  
**Application Area:** Food Science and Nutrition  
**Target Repository:** `NutriX-Intelligence/NutriX-Platform` (`/Ubuntu/home/harsh/Nutrix`)  
**Audit Date:** August 9, 2026  

---

> [!IMPORTANT]
> **Audit Context & Repository Boundary Directive:**
> * This audit evaluates the technical compatibility between the **Core Platform** repository (`NutriX-Intelligence/NutriX-Platform`) and the separate **Regional Project**.
> * The Regional project is an external repository containing a 217-class food taxonomy across 10 regional cuisines, but **HAS NO IMAGE DATASET and NO TRAINED CV MODEL**.
> * No source code has been altered during this audit. No metrics or regional image data have been invented.

---

## TASK 1 — EXTRACT CORE 123 CLASS LIST

The exact 123 food classes were extracted from [dataset/custom_training_data/data.yaml](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/data.yaml) and verified against [runs/class_accuracies.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/class_accuracies.txt).

The complete class index is compiled in [docs/rajDocs2/CORE_123_CLASSES.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs2/CORE_123_CLASSES.txt).

### Class Distribution Overview:
* **Classes 0 to 122 (123 total classes):**
  * 30 prepared Indian regional dish classes (e.g. `biryani`, `dosa`, `idli`, `chole`, `palakpaneer`, `poha`, `samosa`, `rajmacurry`, `rasmalai`, `ghevar`).
  * 20 regional South Asian / Nepali specialty ingredients (e.g. `gundruk`, `masyaura`, `ash gourd -kubhindo-`, `bamboo shoots -tama-`, `stinging nettle -sisnu-`).
  * 73 global fruits, vegetables, grains, legumes, and meat commodities (e.g. `apple`, `avocado`, `broccoli`, `chicken`, `egg`, `mutton`, `tomato`, `whiterice`).

---

## TASK 2 — BUILD REGIONAL MAPPING TABLE

A comprehensive CSV mapping table has been generated and saved to [docs/rajDocs2/CORE_REGIONAL_MAPPING.csv](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs2/CORE_REGIONAL_MAPPING.csv).

### Mapping Methodology:
Each of the 123 Core classes was evaluated against the 10 regional cuisines of the Regional taxonomy (**Rajasthani, Gujarati/Kathiyawadi, Bengali, Maharashtrian, South Indian, Punjabi, Chinese, Mexican, Italian, Japanese**):

1. **Exact Match / Alias:** Direct semantic equivalence (e.g. `dosa` $\rightarrow$ South Indian, `ghevar` $\rightarrow$ Rajasthani, `brinjal` $\rightarrow$ `eggplant`).
2. **Partial Match:** Dishes or base ingredients associated with specific cuisines (e.g. `aloogobi` $\rightarrow$ Punjabi, `poha` $\rightarrow$ Maharashtrian/Gujarati, `fishcurry` $\rightarrow$ Bengali/South Indian, `black beans` $\rightarrow$ Mexican).
3. **No Match:** Global produce or regional non-Indian specialties with no direct regional dish mapping in the 10 target cuisines (e.g. `apple`, `artichoke`, `stinging nettle -sisnu-`, `gundruk`).

---

## TASK 3 — IDENTIFY OVERLAP

### 3.1 Quantitative Class Overlap Summary

| Metric Category | Count | Percentage of Core (123) | Key Class Examples |
| :--- | :--- | :--- | :--- |
| **Core Classes with Regional Equivalents** | **55 classes** | 44.7% | Prepared dishes (`dosa`, `idli`, `chole`, `ghevar`, `poha`) + shared staple ingredients (`dal`, `rice`, `paneer`). |
| **Core Indian & Regional Classes** | **58 classes** | 47.2% | 30 prepared Indian dishes + 20 Nepali/regional specialties + 8 local staples. |
| **Core International Classes** | **48 classes** | 39.0% | Fruits, vegetables, nuts, western commodities (`apple`, `broccoli`, `avocado`, `celery`). |
| **Directly Overlapping Prepared Dishes** | **22 dishes** | 17.9% | `aloogobi`, `bhindimasala`, `biryani`, `chole`, `coconutchutney`, `dal`, `dosa`, `dumaloo`, `fishcurry`, `ghevar`, `gulabjamun`, `idli`, `jalebi`, `kheer`, `kulfi`, `lassi`, `muttoncurry`, `onionpakoda`, `palakpaneer`, `poha`, `rajmacurry`, `samosa`, `shahipaneer`, `whiterice`. |
| **Classes Unmapped to 10 Cuisines** | **65 classes** | 52.8% | 17 Nepali wild specialties + 48 global produce items. |
| **Classes with Semantic Ambiguity** | **8 classes/pairs** | 6.5% | `brinjal`/`eggplant`, `capsicum`/`bell pepper`, `whiterice`/`rice -chamal-`, `chickpeas`/`chole`, `potato`/`aloomasala`. |

---

## TASK 4 — DATASET REUSABILITY

### 4.1 Dataset Structure Analysis
* **Core Dataset Size:** 56,147 total images in [dataset/custom_training_data/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/) (51,535 train, 2,484 validation, 2,128 test).
* **Annotations:** Standard YOLO normalized bounding box format (`class_id x_center y_center width height`).

### 4.2 Derived Evaluation Capabilities

1. **Can existing Core images support Regional Subset Evaluation?**
   * **YES.** The 56,147 images support benchmark evaluation for a **30-class South Asian / Indian Regional Visual Subset** (covering dishes like `dosa`, `idli`, `biryani`, `chole`, `palakpaneer`, `ghevar`, `poha`).

2. **Can existing Core images support Cuisine-Level Evaluation?**
   * **YES.** Core dish images can be grouped into 5 major regional cuisine buckets:
     * **Punjabi (10 classes):** `chole`, `bhatura`, `palakpaneer`, `rajmacurry`, `shahipaneer`, `lassi`, `kulfi`, `aloogobi`, `bhindimasala`, `kebab`.
     * **South Indian (5 classes):** `dosa`, `idli`, `coconutchutney`, `biryani`, `whiterice`.
     * **Maharashtrian / Gujarati (4 classes):** `poha`, `onionpakoda`, `samosa`, `jalebi`.
     * **Rajasthani (2 classes):** `ghevar`, `jalebi`.
     * **Bengali (3 classes):** `rasmalai`, `fishcurry`, `dumaloo`.

3. **Can existing Core images support Fine-Grained 217-Class Regional Evaluation?**
   * **NO.** The Core dataset lacks images for 187 of the 217 Regional taxonomy classes. Fine-grained 217-class vision evaluation cannot be performed until image data is collected for the remaining 187 regional dishes.

---

## TASK 5 — DATASET LEAKAGE CHECK

Inspection of [scripts/download_and_combine_datasets.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/download_and_combine_datasets.py) and `data.yaml` reveals 3 dataset risks:

1. **Semantic Concept Duplication (Label Leakage):**
   * Class 22 (`brinjal`) and Class 46 (`eggplant`) represent the exact same visual concept.
   * Class 12 (`bell pepper`) and Class 28 (`capsicum`) represent the exact same visual concept.
   * *Impact:* Merging Roboflow datasets created separate class IDs for identical visual concepts, penalizing model precision during evaluation when predicting `eggplant` on an image annotated as `brinjal`.

2. **Raw Ingredient vs Prepared Dish Ambiguity:**
   * Class 36 (`chickpeas`) vs Class 38 (`chole`)
   * Class 102 (`red beans`) vs Class 99 (`rajmacurry`)
   * Class 94 (`potato`) vs Class 2 (`aloomasala`)

3. **Multi-Source Combination Risk:**
   * `download_and_combine_datasets.py` combined 3 Roboflow projects (`combined-vegetables-fruits`, `food-ingredients-dataset`, `indianfoodnet`). Cross-project duplicate images could exist if original Roboflow projects drew from shared public domain web sources.

---

## TASK 6 — PROPOSE REALISTIC WACV EXPERIMENTS

Detailed in [docs/rajDocs2/CORE_REGIONAL_EXPERIMENT_PLAN.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs2/CORE_REGIONAL_EXPERIMENT_PLAN.md):

* **P0 (Necessary for WACV Submission):**
  1. *Core 123-Class Baseline Benchmark:* Report 56,147-image baseline (mAP@50 = 58.78%, Precision = 71.08%, Recall = 51.32%).
  2. *Indian Regional 30-Class Subset Benchmark:* Evaluate detection accuracy on prepared Indian regional dishes vs. raw global produce.
  3. *Semantic Class Consolidation Ablation:* Merge duplicate concept classes (`brinjal` + `eggplant`, `capsicum` + `bell pepper`) and re-evaluate mAP gain.
* **P1 (Strongly Recommended):**
  4. *5-Cuisine Hierarchy Grouping Evaluation:* Group Indian dishes into Punjabi, South Indian, Maharashtrian/Gujarati, Rajasthani, and Bengali buckets to measure macro cuisine classification accuracy.
  5. *Rotational & Overhead Augmentation Ablation:* Compare $360^\circ$ rotation (`degrees: 180.0`) vs standard YOLO augmentations.
* **P2 (Optional):**
  6. *End-to-End Visual Nutrition Prediction Error:* Measure calorie/macronutrient prediction error (MAE) when vision outputs feed into `nutrition_engine.py`.

---

## TASK 7 — NUTRITION GROUNDING

Core food classes are mapped to existing nutrition databases:

1. **ICMR / NIN / IFCT Database (`INDB.xlsx`):** Maps to 58 Indian raw ingredients and dishes (`dal`, `paneer`, `poha`, `idli`, `dosa`, `biryani`, `chole`, `rajmacurry`, `ghee`, `aloo`, `bhindi`, `palak`).
2. **USDA National Nutrient Database (`USDA_nrf.xlsx`):** Maps to 48 global produce items (`apple`, `banana`, `avocado`, `broccoli`, `carrot`, `cucumber`, `tomato`, `chicken`, `egg`, `fish`, `mushroom`).
3. **Master Recipe Database (`recipes.xlsx`):** Contains full recipe ingredient breakdowns and per-serving macronutrient values for 22 prepared Indian regional dishes.

---

## TASK 8 — FINAL RESEARCH RECOMMENDATION

### 1. Can the 217 Regional taxonomy currently be claimed as a CV benchmark?
**NO.** The Regional project has NO image dataset and NO trained CV model. Claiming a 217-class computer vision benchmark without images or evaluations would be scientifically invalid.

### 2. Can it currently be claimed as a nutrition/food knowledge taxonomy?
**YES.** The 217-class regional taxonomy with 10 cuisines, recipe formulations, and nutrient breakdowns represents a structured regional nutrition knowledge ontology.

### 3. How many of the Core 123 visual classes overlap with the Regional taxonomy?
**55 classes total** (22 direct prepared regional dishes + 8 regional condiments/beverages + 25 shared regional ingredients/staples).

### 4. What is the strongest scientifically defensible combined NutriX story?
Position NutriX as a **Dual-Layer Architecture**:
* **Layer 1 (Visual Perception Layer):** 123-class YOLOv8 object detector trained on 56,147 images with Human-in-the-Loop active adaptation.
* **Layer 2 (Knowledge & Optimization Layer):** 217-class Regional nutrition ontology combined with Google OR-Tools Mixed-Integer Linear Programming for daily meal optimization.

### 5. What experiment should be performed next?
Execute the **Semantic Class Consolidation Ablation (P0-3)**: Merge duplicate classes (`brinjal`/`eggplant`, `capsicum`/`bell pepper`) in `data.yaml` and re-evaluate mAP@50 to establish a clean visual benchmark baseline.

### 6. What claims must NOT appear in the WACV paper?
* **DO NOT claim** that a 217-class computer vision detector has been trained or evaluated.
* **DO NOT claim** visual detection coverage for all 10 regional cuisines (images only exist for 5 cuisines).
* **DO NOT claim** images exist for the Regional project.
* **DO NOT omit** reporting concept duplication (`brinjal` / `eggplant`) in dataset baseline discussions.
