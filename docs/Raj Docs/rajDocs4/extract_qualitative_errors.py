import os
import shutil
import cv2
import yaml
import torch
import pandas as pd
from ultralytics import YOLO

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(script_dir, "../.."))
    weights_path = os.path.join(base_dir, "runs", "nutrix_custom_model-2", "weights", "best.pt")
    data_yaml_path = os.path.join(base_dir, "dataset", "custom_training_data", "data.yaml")
    output_dir = script_dir
    qual_dir = os.path.join(output_dir, "wacv_figures", "qualitative")
    os.makedirs(qual_dir, exist_ok=True)

    with open(data_yaml_path, "r", encoding="utf-8") as f:
        data_config = yaml.safe_load(f)

    raw_names = data_config.get("names", {})
    if isinstance(raw_names, list):
        class_names = {idx: name for idx, name in enumerate(raw_names)}
    else:
        class_names = {int(idx): name for idx, name in raw_names.items()}

    print(f"Loading checkpoint: {weights_path}...")
    model = YOLO(weights_path)
    device_val = 0 if torch.cuda.is_available() else 'cpu'

    val_img_dir = os.path.join(base_dir, "dataset", "custom_training_data", "valid", "images")
    val_lbl_dir = os.path.join(base_dir, "dataset", "custom_training_data", "valid", "labels")

    val_img_files = [os.path.join(val_img_dir, f) for f in os.listdir(val_img_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
    print(f"Iterating over validation images to extract qualitative error categories...")

    categories_found = {}
    analysis_records = []

    for img_path in val_img_files:
        img_name = os.path.basename(img_path)
        base_name = os.path.splitext(img_name)[0]
        lbl_path = os.path.join(val_lbl_dir, f"{base_name}.txt")

        gt_classes = []
        if os.path.exists(lbl_path):
            with open(lbl_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if parts and parts[0].isdigit():
                        gt_classes.append(int(parts[0]))

        # Predict one image at a time
        results = model.predict(img_path, imgsz=640, device=device_val, conf=0.15, verbose=False)
        if not results:
            continue

        res = results[0]
        pred_classes = []
        pred_confs = []
        if res.boxes is not None and len(res.boxes) > 0:
            for box in res.boxes:
                pred_classes.append(int(box.cls[0]))
                pred_confs.append(float(box.conf[0]))

        gt_names = [class_names.get(c, str(c)) for c in gt_classes]
        pred_names = [class_names.get(c, str(c)) for c in pred_classes]

        # 1. High-confidence correct detection
        if "1_high_conf_correct" not in categories_found and len(gt_classes) > 0 and len(pred_classes) > 0:
            if gt_classes[0] in pred_classes and pred_confs[0] >= 0.85:
                categories_found["1_high_conf_correct"] = img_name
                out_path = os.path.join(qual_dir, "1_high_conf_correct.jpg")
                res.save(filename=out_path)
                analysis_records.append({
                    "cat_id": 1,
                    "image_filename": img_name,
                    "saved_file": "1_high_conf_correct.jpg",
                    "ground_truth": ", ".join(gt_names),
                    "prediction": ", ".join(pred_names),
                    "confidence": f"{pred_confs[0]:.4f}",
                    "error_category": "High-Confidence Correct Detection"
                })

        # 2. False positive
        if "2_false_positive" not in categories_found and len(gt_classes) == 0 and len(pred_classes) > 0:
            if pred_confs[0] >= 0.50:
                categories_found["2_false_positive"] = img_name
                out_path = os.path.join(qual_dir, "2_false_positive.jpg")
                res.save(filename=out_path)
                analysis_records.append({
                    "cat_id": 2,
                    "image_filename": img_name,
                    "saved_file": "2_false_positive.jpg",
                    "ground_truth": "None (Background)",
                    "prediction": ", ".join(pred_names),
                    "confidence": f"{pred_confs[0]:.4f}",
                    "error_category": "False Positive Detection"
                })

        # 3. Missed detection (False Negative)
        if "3_missed_detection" not in categories_found and len(gt_classes) > 0 and len(pred_classes) == 0:
            categories_found["3_missed_detection"] = img_name
            out_path = os.path.join(qual_dir, "3_missed_detection.jpg")
            res.save(filename=out_path)
            analysis_records.append({
                "cat_id": 3,
                "image_filename": img_name,
                "saved_file": "3_missed_detection.jpg",
                "ground_truth": ", ".join(gt_names),
                "prediction": "No Detection",
                "confidence": "N/A",
                "error_category": "Missed Detection (False Negative)"
            })

        # 4. Visually similar food confusion
        if "4_visually_similar_confusion" not in categories_found and len(gt_classes) > 0 and len(pred_classes) > 0:
            if gt_classes[0] != pred_classes[0] and set(gt_classes).isdisjoint(set(pred_classes)):
                categories_found["4_visually_similar_confusion"] = img_name
                out_path = os.path.join(qual_dir, "4_visually_similar_confusion.jpg")
                res.save(filename=out_path)
                analysis_records.append({
                    "cat_id": 4,
                    "image_filename": img_name,
                    "saved_file": "4_visually_similar_confusion.jpg",
                    "ground_truth": ", ".join(gt_names),
                    "prediction": ", ".join(pred_names),
                    "confidence": f"{pred_confs[0]:.4f}",
                    "error_category": "Visually Similar Food Confusion"
                })

        # 5. Duplicate semantic label confusion
        if "5_duplicate_semantic_confusion" not in categories_found and len(gt_classes) > 0 and len(pred_classes) > 0:
            dup_pairs = [(22, 46), (12, 28)]
            for c1, c2 in dup_pairs:
                if (c1 in gt_classes and c2 in pred_classes) or (c2 in gt_classes and c1 in pred_classes):
                    categories_found["5_duplicate_semantic_confusion"] = img_name
                    out_path = os.path.join(qual_dir, "5_duplicate_semantic_confusion.jpg")
                    res.save(filename=out_path)
                    analysis_records.append({
                        "cat_id": 5,
                        "image_filename": img_name,
                        "saved_file": "5_duplicate_semantic_confusion.jpg",
                        "ground_truth": ", ".join(gt_names),
                        "prediction": ", ".join(pred_names),
                        "confidence": f"{pred_confs[0]:.4f}",
                        "error_category": "Duplicate Semantic Label Confusion"
                    })

        # 6. Crowded plate / multi-object detection
        if "6_crowded_plate" not in categories_found and len(gt_classes) >= 3 and len(pred_classes) >= 3:
            categories_found["6_crowded_plate"] = img_name
            out_path = os.path.join(qual_dir, "6_crowded_plate.jpg")
            res.save(filename=out_path)
            analysis_records.append({
                "cat_id": 6,
                "image_filename": img_name,
                "saved_file": "6_crowded_plate.jpg",
                "ground_truth": ", ".join(gt_names),
                "prediction": ", ".join(pred_names),
                "confidence": f"{pred_confs[0]:.4f}",
                "error_category": "Crowded Plate Multi-Object Detection"
            })

        # 7. Low-confidence detection
        if "7_low_confidence" not in categories_found and len(pred_confs) > 0:
            if 0.15 <= pred_confs[0] < 0.40:
                categories_found["7_low_confidence"] = img_name
                out_path = os.path.join(qual_dir, "7_low_confidence.jpg")
                res.save(filename=out_path)
                analysis_records.append({
                    "cat_id": 7,
                    "image_filename": img_name,
                    "saved_file": "7_low_confidence.jpg",
                    "ground_truth": ", ".join(gt_names) if gt_names else "None",
                    "prediction": ", ".join(pred_names),
                    "confidence": f"{pred_confs[0]:.4f}",
                    "error_category": "Low-Confidence Detection"
                })

        if len(categories_found) >= 7:
            print("Found examples for all 7 qualitative error categories!")
            break

    # Sort records by Category ID
    analysis_records.sort(key=lambda x: x["cat_id"])

    md_path = os.path.join(output_dir, "WACV_QUALITATIVE_ANALYSIS.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# WACV 2027 Qualitative Error Analysis Report\n\n")
        f.write("**Evaluated Checkpoint:** `runs/nutrix_custom_model-2/weights/best.pt`  \n")
        f.write("**Validation Dataset Path:** `dataset/custom_training_data/valid/images`  \n\n")
        f.write("## Qualitative Error Category Breakdown\n\n")
        f.write("| Category ID | Image Filename | Saved Visual Image | Ground Truth | Prediction | Confidence | Error Category |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        for rec in analysis_records:
            f.write(f"| {rec['cat_id']} | `{rec['image_filename']}` | `docs/rajDocs4/wacv_figures/qualitative/{rec['saved_file']}` | {rec['ground_truth']} | {rec['prediction']} | {rec['confidence']} | {rec['error_category']} |\n")

    print(f"Saved qualitative error analysis markdown report to {md_path}")

if __name__ == "__main__":
    main()
