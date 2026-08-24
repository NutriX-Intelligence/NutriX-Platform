import os
import shutil
import cv2
import yaml
import torch
import numpy as np
import pandas as pd
from ultralytics import YOLO

def rotate_image_and_boxes(img, boxes, angle):
    h_img, w_img = img.shape[:2]
    
    if angle == 0:
        return img.copy(), boxes
    elif angle == 90:
        rotated_img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        new_boxes = []
        for box in boxes:
            cls_id, xc, yc, w, h = box
            new_boxes.append([cls_id, 1.0 - yc, xc, h, w])
        return rotated_img, new_boxes
    elif angle == 180:
        rotated_img = cv2.rotate(img, cv2.ROTATE_180)
        new_boxes = []
        for box in boxes:
            cls_id, xc, yc, w, h = box
            new_boxes.append([cls_id, 1.0 - xc, 1.0 - yc, w, h])
        return rotated_img, new_boxes
    elif angle == 270:
        rotated_img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        new_boxes = []
        for box in boxes:
            cls_id, xc, yc, w, h = box
            new_boxes.append([cls_id, yc, 1.0 - xc, h, w])
        return rotated_img, new_boxes
    else:
        raise ValueError("Angle must be 0, 90, 180, or 270")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(script_dir, "../.."))
    weights_path = os.path.join(base_dir, "runs", "nutrix_custom_model-2", "weights", "best.pt")
    data_yaml_path = os.path.join(base_dir, "dataset", "custom_training_data", "data.yaml")
    output_dir = script_dir
    rot_temp_dir = os.path.join(output_dir, "temp_rotational_eval")

    if os.path.exists(rot_temp_dir):
        shutil.rmtree(rot_temp_dir)
    os.makedirs(rot_temp_dir, exist_ok=True)

    with open(data_yaml_path, "r", encoding="utf-8") as f:
        data_config = yaml.safe_load(f)

    val_img_dir = os.path.join(base_dir, "dataset", "custom_training_data", "valid", "images")
    val_lbl_dir = os.path.join(base_dir, "dataset", "custom_training_data", "valid", "labels")

    val_images = sorted([f for f in os.listdir(val_img_dir) if f.endswith(('.jpg', '.jpeg', '.png'))])
    
    selected_samples = []
    for img_name in val_images:
        base_name = os.path.splitext(img_name)[0]
        lbl_path = os.path.join(val_lbl_dir, f"{base_name}.txt")
        if os.path.exists(lbl_path) and os.path.getsize(lbl_path) > 0:
            selected_samples.append((img_name, lbl_path))
            if len(selected_samples) >= 200:
                break

    print(f"Selected {len(selected_samples)} reproducible validation images for Rotational Robustness Evaluation.")

    print(f"Loading checkpoint: {weights_path}...")
    model = YOLO(weights_path)
    device_val = 0 if torch.cuda.is_available() else 'cpu'

    angles = [0, 90, 180, 270]
    results_rows = []

    for angle in angles:
        print(f"\n--- Evaluating Angle: {angle} Degrees (device={device_val}) ---")
        angle_dir = os.path.join(rot_temp_dir, f"rot_{angle}")
        angle_img_dir = os.path.join(angle_dir, "images")
        angle_lbl_dir = os.path.join(angle_dir, "labels")
        os.makedirs(angle_img_dir, exist_ok=True)
        os.makedirs(angle_lbl_dir, exist_ok=True)

        for img_name, lbl_path in selected_samples:
            img_path = os.path.join(val_img_dir, img_name)
            img = cv2.imread(img_path)
            if img is None:
                continue

            boxes = []
            with open(lbl_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if parts and len(parts) >= 5:
                        boxes.append([int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])])

            rot_img, rot_boxes = rotate_image_and_boxes(img, boxes, angle)

            dest_img_path = os.path.join(angle_img_dir, img_name)
            cv2.imwrite(dest_img_path, rot_img)

            base_name = os.path.splitext(img_name)[0]
            dest_lbl_path = os.path.join(angle_lbl_dir, f"{base_name}.txt")
            with open(dest_lbl_path, "w", encoding="utf-8") as f:
                for box in rot_boxes:
                    f.write(f"{int(box[0])} {box[1]:.6f} {box[2]:.6f} {box[3]:.6f} {box[4]:.6f}\n")

        angle_yaml_path = os.path.join(angle_dir, "data.yaml")
        angle_yaml_config = {
            "path": os.path.abspath(angle_dir),
            "train": "images",
            "val": "images",
            "names": data_config["names"]
        }
        with open(angle_yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(angle_yaml_config, f)

        val_res = model.val(
            data=angle_yaml_path,
            split="val",
            imgsz=640,
            batch=16,
            device=device_val,
            plots=False,
            save=False
        )

        mp = val_res.results_dict["metrics/precision(B)"]
        mr = val_res.results_dict["metrics/recall(B)"]
        map50 = val_res.results_dict["metrics/mAP50(B)"]
        map5095 = val_res.results_dict["metrics/mAP50-95(B)"]

        results_rows.append({
            "Rotation_Angle": f"{angle} degrees",
            "Images_Evaluated": len(selected_samples),
            "Precision": round(float(mp), 4),
            "Recall": round(float(mr), 4),
            "mAP50": round(float(map50), 4),
            "mAP50_95": round(float(map5095), 4)
        })

    df_rot = pd.DataFrame(results_rows)
    csv_path = os.path.join(output_dir, "rotational_robustness_results.csv")
    df_rot.to_csv(csv_path, index=False)
    print(f"\nSaved Rotational Robustness Evaluation results to {csv_path}")

    shutil.rmtree(rot_temp_dir)
    print("Cleaned up temporary rotation directory.")

if __name__ == "__main__":
    main()
