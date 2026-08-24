# WACV 2027 Technical Audit: Core Computer Vision Module

**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  
**Scope:** Computer Vision Architecture, Models, Training Pipeline, Augmentation, HITL, and Hardware Edge Inference.

---

## 1. Overview & Architectural Role

The Computer Vision engine in this repository serves as the primary visual food identification layer for the NutriX scale and dietary tracking platform. It ingests image feeds from either standard web clients, local image paths, or ESP32-CAM smart scale hardware over Wi-Fi, identifies food items on a plate, generates normalized bounding boxes, and pairs visual confidence scores with incremental weight changes measured by an integrated scale.

---

## 2. Computer Vision Models Inventory

### 2.1 Model 1: Custom Fine-Tuned YOLOv8 Baseline (`nutrix_yolo_custom.pt`)
* **Exact Model:** YOLOv8 (Ultralytics framework)
* **Model Variant:** `yolov8n` (YOLOv8 Nano backbone)
* **Pretrained Weights Source:** `yolov8n.pt` pretrained on COCO dataset, fine-tuned on custom 123-class consolidated dataset
* **Number of Classes:** 123 classes
* **Class Names (Full Inventory):**
  `almond`, `aloogobi`, `aloomasala`, `apple`, `artichoke`, `ash gourd -kubhindo-`, `asparagus`, `avocado`, `bamboo shoots -tama-`, `banana`, `beans`, `beet`, `bell pepper`, `bhatura`, `bhindimasala`, `biryani`, `bitter gourd`, `black beans`, `blackberry`, `blueberry`, `bottle gourd -lauka-`, `bread`, `brinjal`, `broad beans -bakullo-`, `broccoli`, `brussels sprouts`, `buff meat`, `cabbage`, `capsicum`, `carrot`, `cauliflower`, `celery`, `chai`, `cherry`, `chicken`, `chicken gizzards`, `chickpeas`, `chili pepper -khursani-`, `chole`, `coconutchutney`, `corn`, `cucumber`, `dal`, `dosa`, `dumaloo`, `egg`, `eggplant`, `farsi ko munta`, `fiddlehead ferns -niguro-`, `fish`, `fishcurry`, `garlic`, `ghevar`, `grape`, `green bean`, `green brinjal`, `green gram`, `green lentils`, `green onion`, `green peas`, `green soyabean -hariyo bhatmas-`, `greenchutney`, `gulabjamun`, `gundruk`, `hot pepper`, `idli`, `jack fruit`, `jalebi`, `kebab`, `kheer`, `kiwi`, `kulfi`, `lassi`, `lemon`, `lettuce`, `lime`, `long beans -bodi-`, `mandarin`, `masyaura`, `minced meat`, `mushroom`, `mutton`, `muttoncurry`, `onion`, `onionpakoda`, `orange`, `palakpaneer`, `papaya`, `pattypan squash`, `pea`, `peach`, `pear`, `pineapple`, `poha`, `potato`, `pumpkin`, `pumpkin -farsi-`, `radish`, `rahar ko daal`, `rajmacurry`, `rasmalai`, `raspberry`, `red beans`, `red lentils`, `rice -chamal-`, `samosa`, `shahipaneer`, `soyabean-bhatmas-`, `sponge gourd -ghiraula-`, `squash -iskus-`, `stinging nettle -sisnu-`, `strawberry`, `sweet potato -suthuni-`, `tomato`, `tree tomato -rukh tamatar-`, `turnip`, `vegetable marrow`, `wallnut`, `watermelon`, `wheat`, `whiterice`, `yam -pidalu-`, `yellow lentils`.
* **Input Resolution:** $640 \times 640$ pixels (`imgsz: 640`)
* **Preprocessing:** Image normalization, letterbox resizing to $640 \times 640$
* **Augmentation Hyperparameters (Optimized for Fixed Top-Down Camera Settings):**
  * `degrees: 180.0` — $360^\circ$ rotational invariance (food items placed at arbitrary plate rotations)
  * `scale: 0.2` — Portion size scale variation ($\pm 20\%$)
  * `perspective: 0.0` — Disabled perspective distortion (camera fixed overhead)
  * `flipud: 0.5` — Vertical flip probability ($50\%$)
  * `fliplr: 0.5` — Horizontal flip probability ($50\%$)
  * `mosaic: 1.0` — Full mosaic augmentation
* **Confidence Threshold:** `0.80` (80% default threshold in `cv_engine.py` to trigger HITL fallback if under)
* **Training Configuration:**
  * Epochs: 30
  * Batch Size: 16
  * Optimizer: SGD (`lr0: 0.01`, `momentum: 0.937`, `weight_decay: 0.0005`)
  * Hardware: NVIDIA GPU (`device: '0'`)
  * Training Script: [train_custom_model.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/train_custom_model.py)
* **Deployment Location:** [ms1_cv/nutrix_yolo_custom.pt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/nutrix_yolo_custom.pt) and [backend/services/ingestion/nutrix_yolo_custom.pt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/backend/services/ingestion/nutrix_yolo_custom.pt)

---

### 2.2 Model 2: Incremental Human-in-the-Loop Fine-Tuned Model (`yolov8_retrained.pt`)
* **Exact Model:** YOLOv8 (`yolov8n` backbone)
* **Purpose:** Online / incremental retraining engine triggered by Human-in-the-Loop corrections (`retrain_yolo.py` & `hitl_engine.py`)
* **Input Resolution:** $320 \times 320$ pixels (`imgsz: 320` for rapid CPU retraining)
* **Confidence Threshold:** `0.80`
* **Training Configuration:**
  * Device: CPU (`device: "cpu"`)
  * Batch Size: 2
  * Epochs: 1 (fast incremental update)
  * Workers: 0
  * Augmentation: `degrees=180.0`, `scale=0.2`, `perspective=0.0`, `fliplr=0.5`, `flipud=0.5`
* **Deployment Location:** [ms1_cv/yolov8_retrained.pt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/yolov8_retrained.pt)

---

## 3. Human-in-the-Loop (HITL) Workflow Engine

The repository implements a complete, working 4-level active learning & correction pipeline in [ms1_cv/hitl_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/hitl_engine.py) and [ms1_cv/cv_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/cv_engine.py):

1. **High-Confidence Auto-Pass ($\text{Confidence} \ge 0.80$):** Item confirmed automatically and added to active `MealSession`.
2. **Low-Confidence Trigger ($\text{Confidence} < 0.80$ or No Detection):** Image copied to `dataset/pending/`, logged with weight delta.
3. **User Feedback & Correction:** User selects correct label via UI or `run_hitl_interactive.py`.
4. **Auto-Annotation Generation:** `NutriXHitlEngine.apply_user_correction()` converts bounding box to normalized YOLO format (`class_id x_center y_center width height`), writes `.txt` file, updates `classes.txt`, and moves image to `dataset/trained/`.
5. **Model Retraining:** Execution of `retrain_yolo.py` fine-tunes `yolov8n.pt` on newly verified samples and outputs updated weights to `yolov8_retrained.pt`.

---

## 4. Hardware Edge & Smart Scale Integration

* **Hardware Module:** ESP32-S3 / ESP32-CAM module
* **Network Protocol:** HTTP GET requests over local Wi-Fi network (`http://192.168.29.134/capture`)
* **Implementation Code:** [scripts/esp32_inference.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/esp32_inference.py)
* **Functionality:** Downloads live plate snapshot from ESP32 camera, executes YOLO model inference (`nutrix_yolo_custom.pt` / `yolov8_retrained.pt`), extracts bounding boxes, overlays confidence scores, and saves `annotated_esp32.jpg`.
