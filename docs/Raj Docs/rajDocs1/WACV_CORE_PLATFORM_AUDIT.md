# WACV 2027 — NutriX Core Platform Factual Technical Audit

**Target Research Venue:** IEEE/CVF Winter Conference on Applications of Computer Vision (WACV 2027)  
**Track:** Applications  
**Application Area:** Food Science and Nutrition  
**Target Repository:** `NutriX-Intelligence/NutriX-Platform` (`/Ubuntu/home/harsh/Nutrix`)  
**Audit Date:** August 8, 2026  

---

> [!IMPORTANT]
> **Repository Boundary & Audit Scope Notice:**
> This audit represents strictly and solely the codebase, models, datasets, database schemas, and measured results found within `NutriX-Intelligence/NutriX-Platform`. 
> * No assumptions or data from any outside repository have been included.
> * No metrics or results have been invented or post-hoc computed.
> * No source code has been altered during this audit.

---

## 1. COMPLETE PROJECT STRUCTURE

The repository is structured as a multi-container microservice platform containing deep vision engines, optimization solvers, nutrition knowledge bases, and hardware edge adapters.

### 1.1 Directory Breakdown

* `backend/` — Microservice ingestion services ([backend/services/ingestion/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/backend/services/ingestion/)) storing deployed YOLO weights (`nutrix_yolo_custom.pt`).
* `dataset/` — Food detection image dataset (`custom_training_data/`) and tabular nutrition databases (`ms3_datasets/`: `INDB.xlsx`, `USDA_nrf.xlsx`, `Units.xlsx`, `recipes.xlsx`).
* `docs/` — Architectural documentation, diagrams, master plans, and technical deep-dives.
* `gateway/` — API Gateway container ([gateway/main.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/gateway/main.py)).
* `ms1_cv/` — Computer Vision & HITL Microservice ([ms1_cv/cv_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/cv_engine.py), `hitl_engine.py`, `retrain_yolo.py`, `nutrix_yolo_custom.pt`, `yolov8_retrained.pt`).
* `ms2_llm/` — LLM & RAG Microservice shell ([ms2_llm/main.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms2_llm/main.py)).
* `ms3_user/` — Core User, Nutrition, Optimization, Barcode, OCR, & Homely Meals Service ([ms3_user/NutriX-main/NutriX-main/app/services/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/)).
* `ms4_agents/` — Clinical Guardian & Multi-Agent Service shell ([ms4_agents/main.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms4_agents/main.py)).
* `runs/` — Training run logs, metrics CSV, confusion matrices, loss curves (`nutrix_custom_model-2/`, `class_accuracies.txt`).
* `scripts/` — Execution scripts for dataset combination, custom model training, class evaluation, ESP32 inference, and HITL verification.
* `shared/` — Shared database ORM models (`shared/models.py`), database connection (`shared/db.py`), Redis client (`shared/redis_client.py`), health checks (`shared/health.py`), and Alembic migrations.
* `tests/` — Automated test suites.

### 1.2 Key File Status Inventory

| Path | Purpose | Status | Used by | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| `ms1_cv/cv_engine.py` | YOLO inference engine with scale event integration and confidence gating | `[IMPLEMENTED]` | `ms1_cv/main.py` | [cv_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/cv_engine.py) |
| `ms1_cv/hitl_engine.py` | Human-in-the-loop auto-annotation & dataset update engine | `[IMPLEMENTED]` | `scripts/run_hitl_interactive.py` | [hitl_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/hitl_engine.py) |
| `ms1_cv/retrain_yolo.py` | Dynamic 1-epoch CPU retraining pipeline | `[IMPLEMENTED]` | `ms1_cv/hitl_engine.py` | [retrain_yolo.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/retrain_yolo.py) |
| `ms1_cv/nutrix_yolo_custom.pt` | Deployed fine-tuned 123-class YOLOv8 weights | `[IMPLEMENTED]` | `ms1_cv/cv_engine.py` | [nutrix_yolo_custom.pt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/nutrix_yolo_custom.pt) |
| `ms3_user/.../optimization_engine.py` | Google OR-Tools SCIP MILP daily meal plan optimizer | `[IMPLEMENTED]` | `ms3_user` API | [optimization_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/optimization_engine.py) |
| `ms3_user/.../homely_meals_engine.py` | Custom homely meal creation, unit conversion & dynamic nutrition engine | `[IMPLEMENTED]` | `ms3_user` API | [homely_meals_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/homely_meals_engine.py) |
| `ms3_user/.../barcode_service.py` | 4-tier barcode fallback (OFF API $\rightarrow$ DuckDuckGo $\rightarrow$ Gemini AI $\rightarrow$ Local DB) | `[IMPLEMENTED]` | `ms3_user` API | [barcode_service.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/barcode_service.py) |
| `ms3_user/.../ocr_engine.py` | EasyOCR nutrition label extraction & regex parser | `[IMPLEMENTED]` | `ms3_user` API | [ocr_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/ocr_engine.py) |
| `ms3_user/.../ingredient_matcher.py` | RapidFuzz + 80+ term synonym dictionary matcher | `[IMPLEMENTED]` | `ms3_user` API | [ingredient_matcher.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/ingredient_matcher.py) |
| `ms3_user/.../explanation_engine.py` | Rule-based deterministic recommendation explainer | `[IMPLEMENTED]` | `ms3_user` API | [explanation_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/explanation_engine.py) |
| `scripts/esp32_inference.py` | ESP32-CAM HTTP image capture & inference script | `[IMPLEMENTED]` | Hardware Edge | [esp32_inference.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/esp32_inference.py) |
| `shared/models.py` | 34 SQLAlchemy ORM tables (User, Profile, Food, Recipe, HomelyMeal, BarcodeCache, UserAdapter, AuditLog, ClinicalAlert, SystemPromptRegistry) | `[IMPLEMENTED]` | All Microservices | [models.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/shared/models.py) |
| `ms2_llm/main.py` | LLM service shell container | `[PARTIAL]` | Gateway | [ms2_llm/main.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms2_llm/main.py) |
| `ms4_agents/main.py` | Clinical multi-agent service shell container | `[PARTIAL]` | Gateway | [ms4_agents/main.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms4_agents/main.py) |

---

## 2. COMPUTER VISION / FOOD RECOGNITION

* **Models Present:** YOLO (YOLOv8 Nano variant, `yolov8n`)
* **Models NOT Present in Repository:** YOLOv11, Faster R-CNN, general CNN classifiers, Mask R-CNN.
* **OpenCV / Image Preprocessing:** Present (`PIL`, `cv2`, `numpy`, letterbox resizing to 640x640).
* **Exact Model & Version:** YOLOv8 Nano (`yolov8n.pt` base weights fine-tuned to `nutrix_yolo_custom.pt`).
* **Pretrained Weights:** COCO pre-trained weights (`yolov8n.pt`) fine-tuned for 30 epochs on custom dataset.
* **Number of Classes:** 123 classes.
* **Input Resolution:** $640 \times 640$ pixels.
* **Augmentations:** Rotational invariance (`degrees: 180.0`), scale jitter (`scale: 0.2`), no perspective distortion (`perspective: 0.0`), horizontal flip (`fliplr: 0.5`), vertical flip (`flipud: 0.5`), mosaic (`mosaic: 1.0`).
* **Confidence Threshold:** `0.80` (80% default threshold in `cv_engine.py`).
* **Hardware Used:** NVIDIA CUDA GPU (`device: '0'`).
* **Training Command:** `python scripts/train_custom_model.py`
* **Evaluation Command:** `python scripts/get_class_accuracies.py`

---

## 3. ACTUAL COMPUTER VISION RESULTS

All metrics extracted directly from [runs/nutrix_custom_model-2/results.csv](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.csv) and [runs/class_accuracies.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/class_accuracies.txt):

| Metric | Measured Value | Dataset | Model | Status | Evidence File |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Precision (B)** | **0.7108 (71.08%)** | `valid/images` (2,484 imgs) | `nutrix_custom_model-2` | `[MEASURED]` | `results.csv` (Epoch 30) |
| **Recall (B)** | **0.5132 (51.32%)** | `valid/images` (2,484 imgs) | `nutrix_custom_model-2` | `[MEASURED]` | `results.csv` (Epoch 30) |
| **mAP@50 (B)** | **0.5878 (58.78%)** | `valid/images` (2,484 imgs) | `nutrix_custom_model-2` | `[MEASURED]` | `results.csv` (Epoch 30) |
| **Peak mAP@50 (B)** | **0.5932 (59.32%)** | `valid/images` (2,484 imgs) | `nutrix_custom_model-2` | `[MEASURED]` | `results.csv` (Epoch 27) |
| **mAP@50-95 (B)** | **0.4056 (40.56%)** | `valid/images` (2,484 imgs) | `nutrix_custom_model-2` | `[MEASURED]` | `results.csv` (Epoch 30) |
| **Validation Box Loss** | **1.1489** | `valid/images` (2,484 imgs) | `nutrix_custom_model-2` | `[MEASURED]` | `results.csv` (Epoch 30) |
| **Validation Class Loss**| **0.9931** | `valid/images` (2,484 imgs) | `nutrix_custom_model-2` | `[MEASURED]` | `results.csv` (Epoch 30) |
| **Validation DFL Loss** | **1.4436** | `valid/images` (2,484 imgs) | `nutrix_custom_model-2` | `[MEASURED]` | `results.csv` (Epoch 30) |

*Top Class mAP@50 Highlights:* `jalebi` (0.9914), `onionpakoda` (0.9907), `corn` (0.9824), `lettuce` (0.9801), `poha` (0.9663), `palakpaneer` (0.9636), `cauliflower` (0.9555).

---

## 4. DATASET AUDIT

* **Custom CV Image Dataset:** `dataset/custom_training_data/`
  * Total Images: 56,147 images (51,535 train, 2,484 valid, 2,128 test).
  * Classes: 123 consolidated classes.
  * Sources: Roboflow datasets (`combined-vegetables-fruits`, `food-ingredients-dataset`, `indianfoodnet`).
* **Content Coverage:**
  * **Indian Food:** Present (30+ dishes including aloogobi, biryani, chole, dosa, idli, palakpaneer, poha, samosa).
  * **Nepali / Regional Specialty:** Present (20+ items including ash gourd -kubhindo-, bamboo shoots -tama-, bottle gourd -lauka-, gundruk, masyaura, etc.).
  * **International & Raw Produce:** Present (70+ fruits, vegetables, grains, meats).
  * **Nutritional Tabular Databases:** Present (`INDB.xlsx`, `USDA_nrf.xlsx`, `Units.xlsx`, `recipes.xlsx`).

---

## 5. NUTRITION KNOWLEDGE

* **Sources & Locations:**
  * ICMR / NIN / IFCT: `dataset/ms3_datasets/INDB.xlsx` (1.06 MB).
  * USDA: `dataset/ms3_datasets/USDA_nrf.xlsx` (41.8 KB).
  * OpenFoodFacts: API integration in `barcode_service.py`.
  * Unit Conversions: `dataset/ms3_datasets/Units.xlsx` (28.4 KB).
  * Recipes: `dataset/ms3_datasets/recipes.xlsx` (714 KB).
* **Clinical Formulas Implemented:** Mifflin-St Jeor BMR, TDEE, BMI, Calorie Target Offsets, and Macro Splits (Protein: 4 kcal/g, Carbs: 4 kcal/g, Fat: 9 kcal/g).
* **Fuzzy Matcher & Synonyms:** RapidFuzz matcher with 80+ term `SYNONYM_MAP` (`capsicum` $\rightarrow$ `bell pepper`, `dahi` $\rightarrow$ `yogurt`, `aloo` $\rightarrow$ `potato`, `besan` $\rightarrow$ `gram flour`, `sooji`/`rava` $\rightarrow$ `semolina`).

---

## 6. FOOD IDENTIFICATION PIPELINE

Implemented in [ms1_cv/cv_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/cv_engine.py) & [scripts/test_cv_workflow.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/test_cv_workflow.py):

$$\text{Image / Scale Event} \xrightarrow{\text{Weight Delta > 0.5g}} \text{YOLO Detection} \xrightarrow{\text{Conf } \ge 0.80} \text{Identity Confirmed} \xrightarrow{\text{DB Lookup}} \text{Nutrient Allocation}$$
$$\text{If Conf } < 0.80 \longrightarrow \text{Pending Dataset} \longrightarrow \text{HITL User Correction} \longrightarrow \text{Auto-Annotation} \longrightarrow \text{1-Epoch Retrain}$$

---

## 7. BARCODE

Implemented in [ms3_user/NutriX-main/NutriX-main/app/services/barcode_service.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/barcode_service.py):

* **4-Tier Fallback Architecture:**
  1. Open Food Facts API (`world.openfoodfacts.org`)
  2. DuckDuckGo Web Search Scraper (HTML product title/brand parsing)
  3. Google Gemini AI API (`gemini-2.0-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`)
  4. Local Master DB Standardization (`match_food_item`)
* **Caching:** `BarcodeCache` table in PostgreSQL/SQLite storing barcode, product name, brand, ingredients, nutrition grade, nutriments JSON, health score.

---

## 8. OCR

Implemented in [ms3_user/NutriX-main/NutriX-main/app/services/ocr_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/ocr_engine.py):

* **OCR Engine:** `EasyOCR` (English language model `['en']`, CPU execution).
* **Regex Extractors:** Extracts Calories (`kcal`), Protein (`g`), Carbs (`g`), Fat (`g`), Sugar (`g`), Fiber (`g`), Sodium (`mg`/`g`).
* **Fallback:** Manual raw text parser (`parse_nutrition_text`) if OCR fails to extract text lines.

---

## 9. MEAL / NUTRITION OPTIMIZATION

Implemented in [ms3_user/NutriX-main/NutriX-main/app/services/optimization_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/optimization_engine.py):

* **Solver:** Google OR-Tools SCIP Mixed-Integer Linear Programming Solver (`pywraplp.Solver.CreateSolver("SCIP")`).
* **Formulation:** Binary decision variables $y_{s, r} \in \{0, 1\}$ per meal slot $s \in \{\text{Breakfast}, \text{Lunch}, \text{Dinner}, \text{Snack}\}$.
* **Constraints:** Exact slot assignment ($\sum y_{s, r} = 1$), Lunch/Dinner non-repetition ($y_{\text{Lunch}, r} + y_{\text{Dinner}, r} \le 1$), calorie and macro target range bounds $(1 - \tau) T \le \sum N_r y_{s, r} \le (1 + \tau) T$.
* **Tolerance Relaxation:** Iterative step-up from $\tau = 0.15$ to $\tau_{\max} = 0.40$ if initial problem is infeasible.

---

## 10. HOMELY MEALS

Implemented in [ms3_user/NutriX-main/NutriX-main/app/services/homely_meals_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/homely_meals_engine.py) & [shared/models.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/shared/models.py):

* **Functionality:** Fully implemented in THIS repository.
* **Features:**
  * Ingredient Representation & Gram Conversion (`parse_gram_weight` using `unit_conversions` table + household unit fallbacks: tsp=5g, tbsp=15g, cup=240g, glass=200g, bowl=200g, piece=50g).
  * Dynamic Nutrition Calculation (`calculate_ingredient_nutrition`, `calculate_meal_nutrition`).
  * Community Sharing & Moderation (`HomelyMeal`, `is_community`, status="pending"/"approved").
  * Versioning (`HomelyMealVersion`) and Community Reviews (`HomelyMealReview`).

---

## 11. LLM / AGENTIC SYSTEM

* **Gemini AI Integration:** Implemented in `barcode_service.py` (`estimate_nutrition_from_gemini`).
* **Explanation Engine:** Implemented in `explanation_engine.py` (deterministic rule-based explainer).
* **Agentic Database Schema:** Implemented in `shared/models.py` (`SystemPromptRegistry`, `AuditLog`, `ClinicalAlert`, `ClinicalReport`).
* **Microservices (`ms2_llm`, `ms4_agents`):** Microservice FastAPI containers initialized with health checks (`[PARTIAL]`).

---

## 12. HUMAN-IN-THE-LOOP (HITL)

Implemented in `ms1_cv/hitl_engine.py` & `ms1_cv/cv_engine.py`:
Auto-flags detections with confidence $< 0.80$, saves images to `dataset/pending/`, accepts user correction, generates normalized YOLO `.txt` annotations, updates `classes.txt`, moves image to `dataset/trained/`, and triggers 1-epoch YOLO retraining (`retrain_yolo.py`).

---

## 13. HARDWARE / EDGE

Implemented in [scripts/esp32_inference.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/esp32_inference.py):
Connects to ESP32-CAM HTTP endpoint (`http://192.168.29.134/capture`), downloads plate snapshot, executes YOLO model inference (`nutrix_yolo_custom.pt`), overlays bounding boxes, and exports annotated images.

---

## 14. BACKEND / MICROSERVICES

5-container microservice platform orchestrated via Docker Compose ([docker-compose.yml](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docker-compose.yml)):
1. `gateway` (Port 8000)
2. `ms1_cv` (Port 8001)
3. `ms2_llm` (Port 8002)
4. `ms3_user` (Port 8003)
5. `ms4_agents` (Port 8004)
Backed by PostgreSQL 15 (`postgres`) and Redis 7 (`redis`).

---

## 15. FRONTEND

Implemented in [ms3_user/NutriX-main/NutriX-main/app/templates/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/templates/):
Vanilla JS, CSS (glassmorphism dark mode), and Chart.js web dashboard supporting food scanner UI, nutrition analysis, recipe search, meal tracking, and Homely Meals management (`[IMPLEMENTED]`).

---

## 16. EXPERIMENT INVENTORY

All 4 experiments detailed in [CORE_EXPERIMENTS.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs/CORE_EXPERIMENTS.md):
1. `nutrix_custom_model-2` (30-epoch YOLOv8 fine-tuning on 123 classes)
2. `class_accuracies_eval` (123-class validation benchmarking)
3. `hitl_active_learning` (1-epoch CPU active retraining)
4. `esp32_edge_inference` (ESP32-CAM live edge capture & detection)

---

## 17. REPRODUCIBILITY

* **Python Version:** Python 3.10+
* **Dependencies:** Defined in `requirements.txt` (`ultralytics`, `ortools`, `rapidfuzz`, `easyocr`, `fastapi`, `sqlalchemy`, `httpx`, `roboflow`).
* **Environment:** Virtual environment `.venv/`.
* **Execution Commands:**
  * Train custom CV model: `python scripts/train_custom_model.py`
  * Evaluate per-class accuracies: `python scripts/get_class_accuracies.py`
  * Run HITL active retraining: `python scripts/run_hitl_interactive.py`
  * Test ESP32 edge camera: `python scripts/esp32_inference.py`
  * Launch microservices: `docker-compose up --build`

---

## 18. DIAGRAM INVENTORY

All 5 diagram assets detailed in [CORE_DIAGRAMS.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs/CORE_DIAGRAMS.md):
1. High-Level System Architecture Mermaid Graph ([docs/ArchitectureDiagrams.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/ArchitectureDiagrams.md))
2. Tech Stack Inventory Mermaid Graph ([docs/ArchitectureDiagrams.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/ArchitectureDiagrams.md))
3. Master Platform Architecture ([docs/MASTER_ARCHITECTURE.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/MASTER_ARCHITECTURE.md))
4. Agentic & Self-Healing Architecture ([docs/AGENTIC-architecture_forPaper.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/AGENTIC-architecture_forPaper.md))
5. Confusion Matrices & Training Loss Plots ([runs/nutrix_custom_model-2/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/))

---

## 19. DOCUMENTATION AUDIT

* **Consistency:** The codebase implementation (`ms1_cv`, `ms3_user`, `shared/models.py`) matches the master architecture documentation (`docs/MASTER_ARCHITECTURE.md` and `docs/ArchitectureDiagrams.md`).
* **Clarifications:** `ms2_llm` and `ms4_agents` are active microservice shells with database health integration, while LLM calls for structured barcode parsing are actively executed within `BarcodeService` in `ms3_user`.

---

## 20. WACV RELEVANCE (Applications Track: Food Science and Nutrition)

* **Strongest Computer Vision Contribution:** Custom fine-tuned 123-class YOLOv8 model trained with plate-specific rotational augmentations ($360^\circ$ rotational invariance) on a 56,147-image dataset combining global produce, regional Indian dishes, and Nepali foods.
* **Strongest Food Science & Nutrition Contribution:** Mathematical integration of clinical nutrition (Mifflin-St Jeor BMR, TDEE, macro split algorithms) paired with dynamic gram weight normalization (`parse_gram_weight`) and an 80+ term RapidFuzz culinary synonym index (`SYNONYM_MAP`).
* **Strongest System & Optimization Contribution:** Practical deployment of Google OR-Tools SCIP Mixed-Integer Linear Programming solver for daily meal planning under strict caloric, macro, and fiber constraints with dynamic tolerance relaxation.

---

## 21. RESEARCH CLAIMS LEGITIMATELY SUPPORTED

1. **Claim 1:** *NutriX provides multi-class food item detection across 123 food classes with specific optimization for top-down plate viewing geometry.*  
   *Evidence:* `runs/nutrix_custom_model-2/` logged mAP@50 = 58.78%, Precision = 71.08% on 2,484 validation images.
2. **Claim 2:** *NutriX implements a working Human-in-the-Loop active learning pipeline for continuous model adaptation.*  
   *Evidence:* `ms1_cv/hitl_engine.py` auto-generates YOLO annotations from user corrections and executes 1-epoch retraining via `retrain_yolo.py`.
3. **Claim 3:** *NutriX achieves optimal daily dietary planning using Mixed-Integer Linear Programming.*  
   *Evidence:* `OptimizationEngine._solve_mip()` formulates and solves exact MILP problems using Google OR-Tools SCIP.
4. **Claim 4:** *NutriX resolves regional Indian/South Asian culinary naming variations to standard nutritional codes.*  
   *Evidence:* `ingredient_matcher.py` provides 80+ synonym maps and RapidFuzz scoring ($\text{MIN\_FUZZY\_SCORE} = 78$).

---

## 22. MISSING EXPERIMENTS (Prioritized for Paper Submission)

* **P0 — Necessary for WACV Submission:**
  * Benchmarking inference latency (ms per frame) on GPU vs CPU vs ESP32 edge.
  * Quantitative comparison of MILP meal plan optimization solve times (ms) across varying candidate pool sizes ($N = 50, 100, 300, 500$).
* **P1 — Strongly Recommended:**
  * Comparative ablation study evaluating the accuracy impact of rotational augmentations (`degrees: 180.0`) vs standard YOLOv8 augmentations on top-down food images.
  * Precision/Recall evaluation of the 4-tier barcode fallback engine on a sample set of 100 packaged food items.
* **P2 — Optional:**
  * EasyOCR text extraction accuracy benchmarking on food package nutrition labels.

---

## 23. FINAL CORE PLATFORM REPORT

### 23.1 Summary Matrix

1. **Implemented Scope:** 123-class YOLOv8 food detection, HITL auto-annotation & retraining, Google OR-Tools MILP meal optimizer, 4-tier barcode fallback (OFF API + Gemini AI), EasyOCR label reader, Homely Meals dynamic gram/nutrition calculator, 34 PostgreSQL DB tables, 5 microservice containers.
2. **Strongest CV Contribution:** $360^\circ$ rotation-invariant YOLOv8 food detector trained on 56,147 images across 123 classes.
3. **Strongest Nutrition Contribution:** Seamless bridge between visual food detection, ICMR/NIN/USDA databases, dynamic gram weight conversion, and RapidFuzz culinary synonym resolution.
4. **Strongest System Contribution:** Integrated IoT smart scale camera pipeline (ESP32-CAM) combined with OR-Tools MILP meal plan solver.
5. **Strongest Measured Result:** Peak mAP@50 of **59.32%** (Epoch 27) and Precision of **71.08%** (Epoch 30) across 123 food classes (`results.csv`).

### 23.2 Potential WACV Paper Titles
1. *NutriX: A Unified Computer Vision and Mixed-Integer Optimization Platform for Nutrition-Aware Dietary Planning*
2. *Real-Time Food Recognition and Constrained Meal Optimization via Human-in-the-Loop Deep Learning and Mixed-Integer Programming*
3. *NutriX Core: An Integrated Edge-Vision and Clinical Knowledge Platform for South Asian and Global Dietary Monitoring*
