# WACV 2027 Technical Audit: Core Datasets Module

**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  
**Scope:** Computer Vision Datasets, Nutrition Databases, Recipe Data, and Unit Conversion Tables.

---

## 1. Overview of Repository Datasets

This repository contains both image-based computer vision datasets and structured tabular nutrition/recipe databases. All datasets are located inside the `dataset/` directory.

---

## 2. Computer Vision Dataset: `custom_training_data`

### 2.1 General Metadata
* **Dataset Name:** NutriX Custom Consolidated Food Detection Dataset
* **Location Path:** [dataset/custom_training_data/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/)
* **Configuration File:** [dataset/custom_training_data/data.yaml](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/data.yaml)
* **Total Image Count:** 56,147 images
* **Split Breakdown:**
  * **Train Set:** 51,535 images ([dataset/custom_training_data/train/images](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/train/images))
  * **Validation Set:** 2,484 images ([dataset/custom_training_data/valid/images](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/valid/images))
  * **Test Set:** 2,128 images ([dataset/custom_training_data/test/images](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/test/images))
* **Number of Classes:** 123 classes
* **Annotation Format:** YOLO standard text files (`class_id x_center y_center width height` normalized coordinates)

### 2.2 Dataset Sources & Combination Pipeline
Generated programmatically via [scripts/download_and_combine_datasets.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/download_and_combine_datasets.py) using the Roboflow SDK by merging 3 distinct repositories and remapping local class IDs into a single consolidated global 123-class space:
1. `yolo-jpkho/combined-vegetables-fruits` (YOLOv8 format)
2. `food-recipe-ingredient-images-0gnku/food-ingredients-dataset` (YOLOv8 format)
3. `indianfoodnet/indianfoodnet` (YOLOv8 format)

### 2.3 Regional & Cultural Breakdown
* **Indian Dishes (30+ classes):** `aloogobi`, `aloomasala`, `bhatura`, `bhindimasala`, `biryani`, `chole`, `coconutchutney`, `dal`, `dosa`, `dumaloo`, `fishcurry`, `ghevar`, `greenchutney`, `gulabjamun`, `idli`, `jalebi`, `kebab`, `kheer`, `kulfi`, `lassi`, `muttoncurry`, `onionpakoda`, `palakpaneer`, `poha`, `rahar ko daal`, `rajmacurry`, `rasmalai`, `samosa`, `shahipaneer`, `whiterice`.
* **Nepali & Regional Specialty Items (20+ classes):** `ash gourd -kubhindo-`, `bamboo shoots -tama-`, `bottle gourd -lauka-`, `broad beans -bakullo-`, `chili pepper -khursani-`, `farsi ko munta`, `fiddlehead ferns -niguro-`, `green soyabean -hariyo bhatmas-`, `gundruk`, `long beans -bodi-`, `masyaura`, `pumpkin -farsi-`, `rice -chamal-`, `soyabean-bhatmas-`, `sponge gourd -ghiraula-`, `squash -iskus-`, `stinging nettle -sisnu-`, `sweet potato -suthuni-`, `tree tomato -rukh tamatar-`, `yam -pidalu-`.
* **Global Fruits & Vegetables (70+ classes):** `almond`, `apple`, `artichoke`, `asparagus`, `avocado`, `banana`, `beans`, `beet`, `bell pepper`, `bitter gourd`, `black beans`, `blackberry`, `blueberry`, `bread`, `brinjal`, `broccoli`, `brussels sprouts`, `cabbage`, `capsicum`, `carrot`, `cauliflower`, `celery`, `cherry`, `chicken`, `chickpeas`, `corn`, `cucumber`, `egg`, `eggplant`, `garlic`, `grape`, `green bean`, `green peas`, `lemon`, `lettuce`, `lime`, `mushroom`, `onion`, `orange`, `papaya`, `peach`, `pear`, `pineapple`, `potato`, `pumpkin`, `radish`, `raspberry`, `strawberry`, `tomato`, `turnip`, `watermelon`, etc.

---

## 3. Nutrition & Recipe Tabular Databases: `ms3_datasets`

Located in [dataset/ms3_datasets/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/ms3_datasets/):

| File Name | File Size | Primary Purpose & Contents | Database Mapping |
| :--- | :--- | :--- | :--- |
| **`INDB.xlsx`** | 1,063,585 bytes (~1.06 MB) | Indian Food Composition Tables (IFCT / ICMR / NIN) containing macro & micronutrient profiles for Indian raw ingredients. | Seeded into `foods` and `food_nutrients` DB tables. |
| **`USDA_nrf.xlsx`** | 41,888 bytes (~41.8 KB) | USDA National Nutrient Database reference entries for international food items and raw produce. | Seeded into `foods` and `food_nutrients` DB tables. |
| **`Units.xlsx`** | 28,353 bytes (~28.4 KB) | Gram conversions and portion size mappings for standard household measurement units (tsp, tbsp, cup, bowl, piece, etc.). | Seeded into `unit_conversions` and `food_portions` DB tables. |
| **`recipes.xlsx`** | 714,393 bytes (~714 KB) | Comprehensive Indian recipe database featuring ingredient breakdowns, cooking instructions, and per-serving macronutrients. | Seeded into `recipes`, `recipe_ingredients`, `recipe_nutrition`, and `servings` DB tables. |

---

## 4. Dataset Evidence & Usage Summary

* **Active Usage in Training:** `custom_training_data` was actively used to train the 123-class YOLOv8 model (`runs/nutrix_custom_model-2`), achieving a validated dataset execution logged in `results.csv`.
* **Active Usage in Ingestion:** `INDB.xlsx`, `USDA_nrf.xlsx`, `Units.xlsx`, and `recipes.xlsx` are read and loaded into PostgreSQL/SQLite database tables via Alembic migrations and seeders (`shared/seeders/`).
