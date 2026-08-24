import os
import yaml
import torch
import numpy as np
import pandas as pd
from ultralytics import YOLO

def box_iou(box1, box2):
    # box format: [xc, yc, w, h] normalized
    x1_min, x1_max = box1[0] - box1[2]/2, box1[0] + box1[2]/2
    y1_min, y1_max = box1[1] - box1[3]/2, box1[1] + box1[3]/2
    
    x2_min, x2_max = box2[0] - box2[2]/2, box2[0] + box2[2]/2
    y2_min, y2_max = box2[1] - box2[3]/2, box2[1] + box2[3]/2
    
    inter_xmin = max(x1_min, x2_min)
    inter_ymin = max(y1_min, y2_min)
    inter_xmax = min(x1_max, x2_max)
    inter_ymax = min(y1_max, y2_max)
    
    inter_w = max(0.0, inter_xmax - inter_xmin)
    inter_h = max(0.0, inter_ymax - inter_ymin)
    inter_area = inter_w * inter_h
    
    area1 = box1[2] * box1[3]
    area2 = box2[2] * box2[3]
    union_area = area1 + area2 - inter_area
    
    return inter_area / union_area if union_area > 0 else 0.0

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(script_dir, "../.."))
    weights_path = os.path.join(base_dir, "runs", "nutrix_custom_model-2", "weights", "best.pt")
    data_yaml_path = os.path.join(base_dir, "dataset", "custom_training_data", "data.yaml")
    output_dir = script_dir

    with open(data_yaml_path, "r", encoding="utf-8") as f:
        data_config = yaml.safe_load(f)

    print(f"Loading checkpoint: {weights_path}...")
    model = YOLO(weights_path)
    device_val = 0 if torch.cuda.is_available() else 'cpu'

    orig_metrics = {
        "brinjal": {"precision": 1.0000, "recall": 0.0000, "ap50": 0.0000},
        "eggplant": {"precision": 0.9207, "recall": 0.7141, "ap50": 0.8714},
        "capsicum": {"precision": 1.0000, "recall": 0.0000, "ap50": 0.3961},
        "bell pepper": {"precision": 0.8877, "recall": 0.8627, "ap50": 0.8885}
    }

    print("\n--- Running Semantic Label Normalization Analysis ---")
    valid_img_dir = os.path.join(base_dir, "dataset", "custom_training_data", "valid", "images")
    valid_lbl_dir = os.path.join(base_dir, "dataset", "custom_training_data", "valid", "labels")

    group1_ids = [22, 46] # brinjal + eggplant
    group2_ids = [12, 28] # bell pepper + capsicum

    target_all_ids = set(group1_ids + group2_ids)
    target_img_paths = []
    
    for lbl_name in os.listdir(valid_lbl_dir):
        if lbl_name.endswith(".txt"):
            lbl_path = os.path.join(valid_lbl_dir, lbl_name)
            with open(lbl_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if parts and parts[0].isdigit() and int(parts[0]) in target_all_ids:
                        img_name = os.path.splitext(lbl_name)[0] + ".jpg"
                        img_path = os.path.join(valid_img_dir, img_name)
                        if os.path.exists(img_path):
                            target_img_paths.append(img_path)
                        break

    print(f"Found {len(target_img_paths)} validation images containing target semantic group classes.")
    preds = model.predict(target_img_paths, batch=16, imgsz=640, device=device_val, conf=0.25, verbose=False)

    def eval_combined_group(target_class_ids, canonical_name):
        tp, fp, fn = 0, 0, 0
        total_gt = 0
        total_pred = 0
        
        for res in preds:
            img_name = os.path.basename(res.path)
            base_name = os.path.splitext(img_name)[0]
            lbl_path = os.path.join(valid_lbl_dir, f"{base_name}.txt")
            
            gt_boxes = []
            if os.path.exists(lbl_path):
                with open(lbl_path, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
                        if parts and int(parts[0]) in target_class_ids:
                            gt_boxes.append([float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])])
                            
            pred_boxes = []
            if res.boxes:
                # xywhn gets normalized [xc, yc, w, h]
                boxes_norm = res.boxes.xywhn.cpu().numpy()
                classes_arr = res.boxes.cls.cpu().numpy()
                for box_n, cid in zip(boxes_norm, classes_arr):
                    if int(cid) in target_class_ids:
                        pred_boxes.append(box_n.tolist())
                        
            total_gt += len(gt_boxes)
            total_pred += len(pred_boxes)
            
            matched_gt = set()
            for p_box in pred_boxes:
                matched = False
                for g_idx, g_box in enumerate(gt_boxes):
                    if g_idx not in matched_gt and box_iou(p_box, g_box) >= 0.5:
                        matched_gt.add(g_idx)
                        tp += 1
                        matched = True
                        break
                if not matched:
                    fp += 1
                    
            fn += len(gt_boxes) - len(matched_gt)
            
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return {
            "canonical_name": canonical_name,
            "total_gt_annotations": total_gt,
            "total_predictions": total_pred,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4)
        }

    g1_norm = eval_combined_group(group1_ids, "brinjal/eggplant combined")
    g2_norm = eval_combined_group(group2_ids, "capsicum/bell pepper combined")

    summary_rows = [
        {
            "analysis_type": "Original Class",
            "group_name": "brinjal (ID 22)",
            "precision": orig_metrics["brinjal"]["precision"],
            "recall": orig_metrics["brinjal"]["recall"],
            "ap50": orig_metrics["brinjal"]["ap50"]
        },
        {
            "analysis_type": "Original Class",
            "group_name": "eggplant (ID 46)",
            "precision": orig_metrics["eggplant"]["precision"],
            "recall": orig_metrics["eggplant"]["recall"],
            "ap50": orig_metrics["eggplant"]["ap50"]
        },
        {
            "analysis_type": "Semantically Normalized",
            "group_name": "brinjal / eggplant combined",
            "precision": g1_norm["precision"],
            "recall": g1_norm["recall"],
            "ap50": f"F1 Score: {g1_norm['f1_score']}"
        },
        {
            "analysis_type": "Original Class",
            "group_name": "capsicum (ID 28)",
            "precision": orig_metrics["capsicum"]["precision"],
            "recall": orig_metrics["capsicum"]["recall"],
            "ap50": orig_metrics["capsicum"]["ap50"]
        },
        {
            "analysis_type": "Original Class",
            "group_name": "bell pepper (ID 12)",
            "precision": orig_metrics["bell pepper"]["precision"],
            "recall": orig_metrics["bell pepper"]["recall"],
            "ap50": orig_metrics["bell pepper"]["ap50"]
        },
        {
            "analysis_type": "Semantically Normalized",
            "group_name": "capsicum / bell pepper combined",
            "precision": g2_norm["precision"],
            "recall": g2_norm["recall"],
            "ap50": f"F1 Score: {g2_norm['f1_score']}"
        }
    ]

    df_res = pd.DataFrame(summary_rows)
    csv_path = os.path.join(output_dir, "semantic_label_normalization_results.csv")
    df_res.to_csv(csv_path, index=False)
    print(f"Saved Semantic Label Normalization results to {csv_path}")

if __name__ == "__main__":
    main()
