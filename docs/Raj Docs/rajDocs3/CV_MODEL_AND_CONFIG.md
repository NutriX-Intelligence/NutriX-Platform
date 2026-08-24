# WACV 2027 Audit: Computer Vision Model & Training Configuration

**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  
**Scope:** Verification of Model Architecture, Checkpoints, Input Resolution, Class Taxonomy, and Training Hyperparameters.

---

## 1. MODEL ARCHITECTURE & CHECKPOINTS

| Attribute | Verified Value | Evidence Source / File Path |
| :--- | :--- | :--- |
| **Exact YOLO Version** | YOLOv8 | [scripts/train_custom_model.py#L2](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/train_custom_model.py#L2)<br/>[ms1_cv/retrain_yolo.py#L3](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/retrain_yolo.py#L3) |
| **Exact Model Variant** | `yolov8n` (YOLOv8 Nano) | [scripts/train_custom_model.py#L27](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/train_custom_model.py#L27)<br/>[runs/nutrix_custom_model-2/args.yaml#L3](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/args.yaml#L3) |
| **Pretrained Checkpoint** | `yolov8n.pt` (Pretrained on COCO) | [scripts/train_custom_model.py#L27](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/scripts/train_custom_model.py#L27) |
| **Final Evaluation Checkpoint** | `runs/nutrix_custom_model-2/weights/best.pt` | [runs/nutrix_custom_model-2/weights/best.pt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/weights/best.pt)<br/>[ms1_cv/nutrix_yolo_custom.pt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms1_cv/nutrix_yolo_custom.pt) |
| **Model Parameter Count** | `NOT FOUND` in logs (Standard YOLOv8n architecture has 3.15M parameters, but exact value is not logged in `results.csv` or `args.yaml`) | [runs/nutrix_custom_model-2/args.yaml](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/args.yaml) |
| **Input Image Size** | $640 \times 640$ pixels | [runs/nutrix_custom_model-2/args.yaml#L9](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/args.yaml#L9) (`imgsz: 640`) |
| **Number of Classes** | 123 classes (IDs 0 to 122) | [dataset/custom_training_data/data.yaml#L1-L124](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/data.yaml#L1-L124) |
| **Dataset Config Path** | `dataset/custom_training_data/data.yaml` | [dataset/custom_training_data/data.yaml](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/custom_training_data/data.yaml) |

---

## 2. TRAINING HYPERPARAMETER CONFIGURATION

Extracted directly from [runs/nutrix_custom_model-2/args.yaml](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/args.yaml):

```yaml
# Source: runs/nutrix_custom_model-2/args.yaml
task: detect
mode: train
model: runs\nutrix_custom_model-2\weights\last.pt
data: C:\MAIN\Project\CalCount\dataset\custom_training_data\data.yaml
epochs: 30
batch: 16
imgsz: 640
save: true
device: '0'
workers: 4
pretrained: true
optimizer: auto
seed: 0
deterministic: true
close_mosaic: 10
amp: true
val: true
split: val
iou: 0.7
max_det: 300
lr0: 0.01
lrf: 0.01
momentum: 0.937
weight_decay: 0.0005
warmup_epochs: 3.0
warmup_momentum: 0.8
warmup_bias_lr: 0.0
box: 7.5
cls: 0.5
dfl: 1.5
hsv_h: 0.015
hsv_s: 0.7
hsv_v: 0.4
degrees: 180.0
translate: 0.1
scale: 0.2
shear: 0.0
perspective: 0.0
flipud: 0.5
fliplr: 0.5
mosaic: 1.0
mixup: 0.0
copy_paste: 0.0
auto_augment: randaugment
erasing: 0.4
patience: 100
```

### Verified Parameter Table

| Configuration Parameter | Verified Value | Evidence Line in `args.yaml` |
| :--- | :--- | :--- |
| **Epochs** | `30` | Line 5 (`epochs: 30`) |
| **Batch Size** | `16` | Line 8 (`batch: 16`) |
| **Image Resolution** | `640` ($640 \times 640$) | Line 9 (`imgsz: 640`) |
| **Optimizer** | `auto` (Ultralytics SGD/AdamW auto-selector) | Line 19 (`optimizer: auto`) |
| **Initial Learning Rate (`lr0`)** | `0.01` | Line 74 (`lr0: 0.01`) |
| **Final Learning Rate Factor (`lrf`)**| `0.01` | Line 75 (`lrf: 0.01`) |
| **Momentum** | `0.937` | Line 76 (`momentum: 0.937`) |
| **Weight Decay** | `0.0005` | Line 77 (`weight_decay: 0.0005`) |
| **Warmup Epochs** | `3.0` | Line 78 (`warmup_epochs: 3.0`) |
| **Warmup Momentum** | `0.8` | Line 79 (`warmup_momentum: 0.8`) |
| **Mosaic Augmentation** | `1.0` (100% probability) | Line 101 (`mosaic: 1.0`) |
| **Mixup Augmentation** | `0.0` (Disabled) | Line 102 (`mixup: 0.0`) |
| **Copy-Paste Augmentation** | `0.0` (Disabled) | Line 104 (`copy_paste: 0.0`) |
| **Rotation (`degrees`)** | `180.0` ($360^\circ$ rotational invariance) | Line 93 (`degrees: 180.0`) |
| **Scale (`scale`)** | `0.2` ($\pm 20\%$ scale jitter) | Line 95 (`scale: 0.2`) |
| **Translation (`translate`)** | `0.1` ($\pm 10\%$ translation) | Line 94 (`translate: 0.1`) |
| **Shear (`shear`)** | `0.0` (Disabled) | Line 96 (`shear: 0.0`) |
| **Perspective (`perspective`)** | `0.0` (Disabled for fixed overhead camera) | Line 97 (`perspective: 0.0`) |
| **Horizontal Flip (`fliplr`)** | `0.5` (50% probability) | Line 99 (`fliplr: 0.5`) |
| **Vertical Flip (`flipud`)** | `0.5` (50% probability) | Line 98 (`flipud: 0.5`) |
| **HSV Augmentation** | Hue: `0.015`, Saturation: `0.7`, Value: `0.4` | Lines 90–92 |
| **Early Stopping / Patience** | `100` | Line 7 (`patience: 100`) |
| **Random Seed** | `0` | Line 21 (`seed: 0`) |
| **DataLoader Workers** | `4` | Line 14 (`workers: 4`) |
| **Hardware Device** | `0` (NVIDIA GPU CUDA) | Line 13 (`device: '0'`) |
